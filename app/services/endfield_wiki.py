"""终末地资料库与活动日历的本机存储与编排。

索引、状态与活动日历缓存在 BMT 现有的本机数据目录下（与 state.json 同级）：

* <data_dir>/wiki/index.json   紧凑索引，schema 见 akedata_client.INDEX_SCHEMA
* <data_dir>/wiki/state.json   同步状态：版本、时间、体检结果
* <data_dir>/wiki/arknights.json  明日方舟活动与卡池缓存（运行时下载，不入库）
* <data_dir>/wiki/calendar-<game>.json  各游戏的活动日历缓存（SRA / 本机解包索引）

活动日历由 `app/services/game_calendar.py` 负责取数与缓存，这里只做编排：终末地优先用
本机解包索引里的日历，SRA 只在索引还没有活动时补位；明日方舟在 SRA 之后还有本机解包
游戏表可用。任何一环取不到都只是那一个游戏降级，不影响其它游戏。

落盘一律先写同目录临时文件再 os.replace，避免中断留下半份索引；读取走内存缓存，
文件被外部改动（mtime / 大小变化）时自动重载。

同步失败只抛出可读原因（akedata_client.AkedataError 的文案），绝不把上游响应体交给
调用方；status() 始终可用，没有索引时 ready=false 并给出提示。本模块不发通知、不做
轮询，前端点"同步"即可。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.services import game_calendar
from app.tools import (
    akedata_client,
    endfield_changes,
    endfield_view,
    game_calendar_arknights,
)
from app.tools.akedata_client import AkedataError
from app.tools.endfield_lookup import load_aliases
from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("终末地资料库")

__all__ = [
    "INDEX_FILE_NAME",
    "INDEX_SCHEMA",
    "WikiError",
    "WikiStore",
    "WikiStorage",
    "data_directory",
    "wiki",
]

INDEX_SCHEMA = akedata_client.INDEX_SCHEMA
WIKI_DIR_NAME = "wiki"
INDEX_FILE_NAME = "index.json"
STATE_FILE_NAME = "state.json"
ARKNIGHTS_FILE_NAME = "arknights.json"
TABLE_DIR_NAME = "tables_tmp"
MAX_PROBLEMS = 50  # status 只回传前若干条体检结果，避免响应过长
# 日历覆盖的游戏枚举由 services 层单一维护（含 SRA 标识映射），接口契约照它生成。
CALENDAR_GAMES = game_calendar.CALENDAR_GAMES
# 与上游 ENDFIELD_KINDS 一致：活动 id 前缀 -> 分类标签。
ENDFIELD_KINDS = (
    ("activity_high_difficulty", "高难"),
    ("activity_stamina", "理智"),
    ("activity_checkin", "签到"),
    ("activity_char_trial", "试用"),
    ("characterguide", "干员"),
    ("web_", "网页"),
    ("activity_map", "探索"),
    ("activity_limited_formula", "制造"),
    ("activity_submit", "物资"),
    ("activity_contingency", "合约"),
    ("activity_seasontower", "回响"),
)
ENDFIELD_MOMENTS = ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M")
SPRITE_NAME = re.compile(r"[A-Za-z0-9_]+")
ACTIVITY_KEEP_ENDED = 7 * 86400  # 已结束更久的活动不再出现在日历里
UPCOMING_DAYS = 30  # 日历往后看的天数


class WikiError(ValueError):
    """本机索引不可用或不完整。

    继承 ValueError：应用已把 ValueError 映射为 400 与可读文案，用户看到的是原因而
    不是"操作未完成"。消息里不含上游响应体或凭据。
    """


class WikiStorage(Protocol):
    """跨运行时保存资料库 JSON 的最小异步接口。"""

    async def read(self, name: str) -> str | None: ...

    async def write(self, name: str, text: str) -> None: ...


def data_directory() -> Path:
    """本机数据目录；服务层不反向导入 core.state。"""
    configured = os.environ.get("COMMUNITY_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / "data"


def _atomic_write(path: Path, text: str) -> None:
    """同目录临时文件 + os.replace，中断不会留下半份文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_moment(value: Any) -> datetime | None:
    """索引里的开闭时间字符串 -> 北京时间；无法解析时返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("T", " ")
    for fmt in ENDFIELD_MOMENTS:
        try:
            return datetime.strptime(text[: len(fmt) + 5], fmt).replace(tzinfo=UTC8)
        except ValueError:
            continue
    return None


def calendar_status(start: datetime | None, end: datetime | None, now: datetime) -> str:
    """日历行的状态文案：进行中 / 即将开始 / 已结束 / 常驻。"""
    if start is None:
        return ""
    if start > now:
        return "即将开始"
    if end is None:
        return "常驻"
    return "进行中" if now < end else "已结束"


def iso_moment(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


class WikiStore:
    """索引的读写、缓存与同步编排；一个进程用一个实例。"""

    _PERSISTED_FILES = (
        "wiki/index.json",
        "wiki/state.json",
        "wiki/arknights.json",
    )

    def __init__(
        self, directory: Path | None = None, storage: WikiStorage | None = None
    ) -> None:
        if directory is not None and storage is not None:
            raise ValueError("资料库不能同时指定目录和平台存储")
        self._directory = Path(directory) if directory else None
        self._storage = storage
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._initialized = storage is None
        self._index: dict | None = None
        self._stamp: tuple[int, int] | None = None
        self._aliases: dict | None = None
        self.lock = asyncio.Lock()
        self.last_error = ""
        self.last_message = ""

    # ── 路径 ──────────────────────────────────────────────────────────
    @property
    def directory(self) -> Path:
        if self._directory is not None:
            return self._directory
        if self._temporary_directory is not None:
            return Path(self._temporary_directory.name)
        if self._storage is not None:
            self._temporary_directory = tempfile.TemporaryDirectory(
                prefix="better-mas-wiki-"
            )
            return Path(self._temporary_directory.name)
        return data_directory()

    @property
    def wiki_directory(self) -> Path:
        return self.directory / WIKI_DIR_NAME

    @property
    def index_file(self) -> Path:
        return self.wiki_directory / INDEX_FILE_NAME

    @property
    def state_file(self) -> Path:
        return self.wiki_directory / STATE_FILE_NAME

    @property
    def arknights_file(self) -> Path:
        return self.wiki_directory / ARKNIGHTS_FILE_NAME

    async def initialize(self) -> None:
        """把平台持久化 JSON 装载到本次运行的工作目录。"""
        if self._storage is None or self._initialized:
            return
        self.wiki_directory.mkdir(parents=True, exist_ok=True)
        for name in self._PERSISTED_FILES:
            try:
                payload = await self._storage.read(name)
            except Exception:
                logger.warning(f"资料库缓存读取失败：{name}")
                continue
            if payload is None:
                continue
            target = self.directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.write_text(payload, encoding="utf-8")
            except OSError:
                logger.warning(f"资料库缓存装载失败：{name}")
        # 日历文件是按游戏动态生成的，单独读取已知游戏键。
        for game in CALENDAR_GAMES:
            name = f"wiki/calendar-{game}.json"
            try:
                payload = await self._storage.read(name)
            except Exception:
                logger.warning(f"活动日历缓存读取失败：{game}")
                continue
            if payload is not None:
                target = self.directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_text(payload, encoding="utf-8")
                except OSError:
                    logger.warning(f"活动日历缓存装载失败：{game}")
        self._initialized = True

    async def _write_storage(
        self, path: Path, text: str, *, required: bool = False
    ) -> None:
        """先写平台持久层；日历缓存失败时允许降级。"""
        if self._storage is None:
            return
        try:
            relative = path.relative_to(self.directory).as_posix()
            await self._storage.write(relative, text)
        except Exception as error:
            if required:
                raise WikiError("资料库索引保存失败，请检查平台存储") from error
            logger.warning(f"资料库缓存写入失败：{path.name}")

    async def _persist_file(self, path: Path) -> None:
        """将工作目录中已有的 JSON 同步到平台存储。"""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            logger.warning(f"资料库缓存读取失败：{path.name}（{type(error).__name__}）")
            return
        await self._write_storage(path, text)

    async def _persist_calendar(self, game: str) -> None:
        await self._persist_file(game_calendar.cache_file(self.wiki_directory, game))

    # ── 读取 ──────────────────────────────────────────────────────────
    def index(self) -> dict:
        """内存缓存里的索引；文件被改动或尚未读取时重新加载。"""
        path = self.index_file
        try:
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            self._index, self._stamp = {}, None
            return {}
        if self._index is None or self._stamp != stamp:
            loaded = _read_json(path)
            self._index, self._stamp = loaded, stamp
        return self._index or {}

    def aliases(self) -> dict:
        if self._aliases is None:
            self._aliases = load_aliases()
        return self._aliases

    def state(self) -> dict:
        return _read_json(self.state_file)

    def ready(self) -> bool:
        """索引存在、schema 匹配且至少有一类资料，才算可用。"""
        index = self.index()
        if not index or index.get("schema") != INDEX_SCHEMA:
            return False
        return any(akedata_client.index_counts(index).values())

    def counts(self) -> dict[str, int]:
        return akedata_client.index_counts(self.index())

    def status(self) -> dict:
        """契约 GET /api/wiki/status 的 data。"""
        index = self.index()
        state = self.state()
        ready = self.ready()
        problems = [str(item) for item in (index.get("problems") or state.get("problems") or [])]
        version = str(index.get("version") or state.get("version") or "")
        updated = ""
        synced = state.get("synced_at")
        if isinstance(synced, (int, float)) and synced > 0:
            updated = datetime.fromtimestamp(synced, tz=UTC8).isoformat(timespec="seconds")
        elif index:
            try:
                updated = datetime.fromtimestamp(
                    self.index_file.stat().st_mtime, tz=UTC8
                ).isoformat(timespec="seconds")
            except OSError:
                updated = ""
        if self.last_error:
            message = f"同步未完成：{self.last_error}"
            if index:
                message += f"；仍在使用本机索引 {version or '（无版本）'}"
        elif ready:
            message = self.last_message or f"索引版本 {version or '（无版本）'}"
        elif index:
            message = "本机索引与当前程序版本不一致，请同步"
        else:
            message = "本机还没有终末地资料索引，请点击同步"
        return {
            "ready": ready,
            "version": version,
            "updatedAt": updated,
            "schema": int(index.get("schema") or 0),
            "counts": self.counts(),
            "problems": problems[:MAX_PROBLEMS],
            "message": message,
        }

    # ── 同步 ──────────────────────────────────────────────────────────
    async def sync(
        self, force: bool = False, transport: httpx.AsyncBaseTransport | None = None
    ) -> dict:
        """拉 manifest，版本或索引 schema 变化时重建；返回与 status 同形的结果。

        失败不抛出：原因写进返回值的 message（同时记入日志），已有索引继续可用。
        """
        async with self.lock:
            self.last_error = ""
            self.last_message = ""
            try:
                self.last_message = await self._rebuild(force=force, transport=transport)
            except (AkedataError, WikiError) as error:
                self.last_error = str(error)
                logger.warning(f"终末地资料库同步失败：{self.last_error}")
            except Exception as error:  # 兜底：不把内部异常交给接口层
                self.last_error = f"内部错误（{type(error).__name__}）"
                logger.exception("终末地资料库同步异常")
            return self.status()

    async def _rebuild(
        self, *, force: bool, transport: httpx.AsyncBaseTransport | None
    ) -> str:
        index = self.index()
        state = self.state()
        outdated = bool(index) and index.get("schema") != INDEX_SCHEMA
        async with akedata_client.http_client(transport=transport) as client:
            manifest = await akedata_client.fetch_manifest(client)
            version = akedata_client.latest_version(manifest)
            version_id = str(version.get("id") or "")
            if not version_id:
                raise AkedataError("数据源版本清单缺少版本号")
            if (
                not force
                and not outdated
                and version_id == state.get("version")
                and self.ready()
            ):
                return f"已是最新版本 {version_id}"
            tabledir = self.wiki_directory / TABLE_DIR_NAME
            akedata_client.remove_tree(tabledir)
            try:
                await akedata_client.download_tables(
                    client, str(version.get("tableCfgPath") or ""), tabledir
                )
                new_index = await asyncio.to_thread(
                    akedata_client.build_index, tabledir, version
                )
            finally:
                akedata_client.remove_tree(tabledir)
        problems = endfield_changes.problems(new_index)
        new_index["problems"] = problems
        counts = akedata_client.index_counts(new_index)
        stage = akedata_client.stage_stats(new_index)
        index_text = json.dumps(new_index, ensure_ascii=False)
        await self._write_storage(self.index_file, index_text, required=True)
        _atomic_write(self.index_file, index_text)
        self._index, self._stamp = None, None
        state_text = json.dumps(
            {
                "version": version_id,
                "published_at": new_index.get("published_at", ""),
                "schema": INDEX_SCHEMA,
                "synced_at": time.time(),
                "counts": counts,
                "stages": stage,
                "problems": problems,
            },
            ensure_ascii=False,
        )
        await self._write_storage(self.state_file, state_text, required=True)
        _atomic_write(self.state_file, state_text)
        added = endfield_changes.added(index, new_index)
        fresh = sum(len(names) for names in added.values())
        logger.info(
            f"终末地资料库已同步 {version_id}：干员 {counts['characters']}，"
            f"武器 {counts['weapons']}，套装 {counts['equipSuits']}，"
            f"关卡 {counts['dungeons']}，敌人 {counts['enemies']}，新增 {fresh}"
        )
        if problems:
            logger.warning(f"终末地资料库体检发现 {len(problems)} 处问题")
        summary = (
            f"已同步 {version_id}（干员 {counts['characters']}，武器 {counts['weapons']}，"
            f"关卡 {counts['dungeons']}）"
        )
        if fresh:
            summary += f"，新增 {fresh} 条"
        return summary

    async def ensure_ready(self) -> bool:
        """本机没有可用索引时同步一次；返回是否已经可用。"""
        if self.ready():
            return True
        await self.sync()
        return self.ready()

    async def startup_sync(self) -> None:
        """应用启动时的后台检查：只在没有索引时同步，失败只记日志。"""
        await asyncio.sleep(0)  # 让启动流程先完成，不阻塞生命周期
        if self.ready():
            return
        logger.info("本机还没有终末地资料索引，开始后台同步")
        status = await self.sync()
        if status["ready"]:
            logger.info(status["message"])
        else:
            logger.warning(f"终末地资料库后台同步未完成：{status['message']}")

    # ── 查询 ──────────────────────────────────────────────────────────
    def search(self, query: str, limit: int) -> list[dict]:
        return endfield_view.search(self.index(), self.aliases(), query, limit)

    def entry(self, kind: str, entry_id: str) -> dict:
        found = endfield_view.entry(self.index(), kind, entry_id)
        if found is None:
            if kind not in endfield_view.ENTRY_KINDS:
                raise WikiError(f"不支持的资料类型：{kind}")
            if not self.ready():
                raise WikiError("本机还没有终末地资料索引，请先同步")
            raise WikiError("没有找到这条资料，请重新检索")
        return found

    # ── 活动日历 ──────────────────────────────────────────────────────
    async def calendar(
        self, game: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> list[dict]:
        """活动日历的行；game 取 CALENDAR_GAMES 里的标识。

        上游失败一律降级成空列表，原因写在 calendar_outcomes 的 message 里。
        """
        outcome = await self.calendar_outcomes(game, transport=transport)
        return outcome.rows

    async def calendar_outcomes(
        self, game: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> game_calendar.CalendarOutcome:
        """单个游戏的日历与降级说明；取不到数据时 rows 为空，不上抛。"""
        if game not in CALENDAR_GAMES:
            raise WikiError(f"不支持的日历：{game}（可用：{'、'.join(CALENDAR_GAMES)}）")
        if game == "endfield":
            return await self.endfield_calendar_outcome(transport=transport)
        if game == "arknights":
            return await self.arknights_calendar_outcome(transport=transport)
        outcome = await game_calendar.fetch(game, self.wiki_directory, transport=transport)
        await self._persist_calendar(game)
        return outcome

    async def calendar_outcomes_all(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        games: Sequence[str] | None = None,
    ) -> list[game_calendar.CalendarOutcome]:
        """一次取回全部游戏（或指定若干游戏）的日历。

        并发取数，顺序与 CALENDAR_GAMES 一致；每个游戏各自失败互不影响：某个游戏取不到
        只让它自己的 rows 为空、message 有说明，不会让整个请求失败。
        """
        selected = CALENDAR_GAMES if games is None else tuple(games)
        unknown = [game for game in selected if game not in CALENDAR_GAMES]
        if unknown:
            raise WikiError(f"不支持的日历：{'、'.join(unknown)}")
        return list(
            await asyncio.gather(
                *(self.calendar_outcomes(game, transport=transport) for game in selected)
            )
        )

    async def endfield_calendar_outcome(
        self, transport: httpx.AsyncBaseTransport | None = None
    ) -> game_calendar.CalendarOutcome:
        """终末地日历：本机解包索引为准，索引里没有活动时才用 SRA 补位。

        AKEData 是解包数据、比 SRA 权威，所以只要索引里有活动就以索引为准，避免同一
        个活动出现两份；索引还没同步或确实没有活动时再用 SRA，两处都取不到返回空列表。
        """
        local = self.endfield_calendar()
        if local:
            index = self.index()
            version = str(index.get("version") or "")
            published = str(index.get("published_at") or "")
            message = f"来自本机解包索引 {version}" if version else "来自本机解包索引"
            if published:
                message += f"（{published}）"
            return game_calendar.CalendarOutcome(
                game="endfield",
                rows=local,
                message=message,
                source="local",
                version=version,
            )
        fallback = await game_calendar.fetch(
            "endfield", self.wiki_directory, transport=transport
        )
        await self._persist_calendar("endfield")
        if fallback.rows:
            return fallback._replace(message=f"本机索引暂无活动，改用 SRA：{fallback.message}")
        return fallback._replace(message=f"本机索引暂无活动，且{fallback.message}")

    async def arknights_calendar_outcome(
        self, transport: httpx.AsyncBaseTransport | None = None
    ) -> game_calendar.CalendarOutcome:
        """明日方舟日历：SRA 优先，其次本机解包游戏表。

        SRA 与它的缓存都拿不到时回退到 game_calendar_arknights（游戏表 + 本机缓存），
        那条路自己也会静默降级；两条都没有数据时返回空列表，不抛错。
        """
        outcome = await game_calendar.fetch(
            "arknights", self.wiki_directory, transport=transport
        )
        await self._persist_calendar("arknights")
        if outcome.rows or outcome.source == "cache":
            return outcome
        local = await self.arknights_calendar(transport=transport)
        if not local:
            return outcome
        message = "SRA 暂不可用，改用本机解包游戏表"
        if outcome.message:
            message += f"（{outcome.message}）"
        return game_calendar.CalendarOutcome("arknights", local, message, "local")

    def endfield_calendar(self) -> list[dict]:
        """终末地活动与卡池：正在开放、即将开始与刚结束的。"""
        calendar = self.index().get("calendar") or {}
        now = datetime.now(tz=UTC8)
        horizon = now.timestamp() + UPCOMING_DAYS * 86400
        rows = []
        for activity in calendar.get("activities") or []:
            start, end = parse_moment(activity.get("open")), parse_moment(activity.get("close"))
            if start is None:
                continue
            if end and end.timestamp() < now.timestamp() - ACTIVITY_KEEP_ENDED:
                continue
            if start.timestamp() > horizon:
                continue
            tab = activity.get("tab") or ""
            rows.append(
                {
                    "game": "endfield",
                    "kind": "activity",
                    "title": activity.get("name", ""),
                    "subtitle": self._activity_kind(activity.get("id", "")),
                    "startsAt": iso_moment(start),
                    "endsAt": iso_moment(end),
                    "banner": (
                        akedata_client.activity_banner_url(tab)
                        if SPRITE_NAME.fullmatch(tab)
                        else ""
                    ),
                    "status": calendar_status(start, end, now),
                }
            )
        for pool in calendar.get("pools") or []:
            start, end = parse_moment(pool.get("open")), parse_moment(pool.get("close"))
            if start is None or end is None or end.timestamp() < now.timestamp():
                if end is None or (end and end.timestamp() < now.timestamp()):
                    continue
            up = pool.get("up") or []
            rows.append(
                {
                    "game": "endfield",
                    "kind": "gacha",
                    "title": pool.get("name", ""),
                    "subtitle": f'UP：{"、".join(up)}' if up else "",
                    "startsAt": iso_moment(start),
                    "endsAt": iso_moment(end),
                    "banner": "",
                    "status": calendar_status(start, end, now),
                }
            )
        return sorted(rows, key=lambda row: (row["startsAt"], row["kind"]))

    @staticmethod
    def _activity_kind(activity_id: str) -> str:
        lowered = activity_id.lower()
        return next(
            (label for prefix, label in ENDFIELD_KINDS if lowered.startswith(prefix)), ""
        )

    async def arknights_calendar(
        self, transport: httpx.AsyncBaseTransport | None = None
    ) -> list[dict]:
        """明日方舟日历：首次访问或缓存过期时下载游戏表，失败静默降级为空列表。"""
        cached = game_calendar_arknights.load(self.arknights_file)
        if not cached.get(game_calendar_arknights.GAME_ACTIVITIES_KEY):
            try:
                if transport is None:
                    outcome = await game_calendar_arknights.refresh(self.arknights_file)
                else:
                    outcome = await game_calendar_arknights.refresh(
                        self.arknights_file, transport=transport
                    )
                logger.info(f"明日方舟日历：{outcome}")
                cached = game_calendar_arknights.load(self.arknights_file)
                await self._persist_file(self.arknights_file)
            except (AkedataError, OSError) as error:
                # 日历是附带信息：拿不到就返回空列表，不影响终末地资料库与其它接口。
                logger.warning(f"明日方舟日历暂不可用：{error}")
                return []
        return game_calendar_arknights.to_calendar_rows(cached)


wiki = WikiStore()
