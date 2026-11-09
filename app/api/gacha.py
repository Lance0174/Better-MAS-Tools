"""抽卡接口：凭据输入不回显，分页结果由模型描述。"""

from typing import Literal

from fastapi import APIRouter, Query

from app.core import gacha
from app.models.gacha import GachaGame
from app.models.schema import (
    GachaCookieFetchIn,
    GachaExportOut,
    GachaFetchIn,
    GachaHeyboxIn,
    GachaHeyboxOut,
    GachaImportIn,
    GachaRecordsOut,
    GachaUpdateOut,
)

router = APIRouter(prefix="/api/gacha", tags=["Gacha"])


@router.get("", response_model=GachaRecordsOut, operation_id="listGachaRecords")
async def list_records(
    game: GachaGame,
    playerUid: str = "",
    pool: str = "",
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
) -> GachaRecordsOut:
    return GachaRecordsOut(
        **gacha.query(
            game, player_uid=playerUid, pool=pool, page=page, page_size=pageSize
        )
    )


@router.post("/fetch", response_model=GachaUpdateOut, operation_id="fetchGachaRecords")
async def fetch_records(body: GachaFetchIn) -> GachaUpdateOut:
    try:
        added, fetched, warnings = await gacha.fetch(
            body.game,
            body.source.get_secret_value(),
            account_id=body.accountId,
            player_uid=body.playerUid,
            timezone=body.timezone,
            max_pages=body.maxPages,
        )
    except ValueError:
        # Pydantic/JSON 等内部验证不能把原始条目或授权材料回显。
        raise ValueError(
            "记录读取未完成，请检查官方链接、游戏 UID 与所选账号"
        ) from None
    except Exception:
        raise ValueError("抽卡记录请求未完成，请检查网络或授权时效") from None
    return GachaUpdateOut(
        added=added,
        fetched=fetched,
        warnings=warnings,
        status="partial" if warnings else "success",
    )


@router.post(
    "/fetch-cookie",
    response_model=GachaUpdateOut,
    operation_id="fetchGachaRecordsByCookie",
)
async def fetch_records_by_cookie(body: GachaCookieFetchIn) -> GachaUpdateOut:
    """用米游社登录态换 authkey 读取官方记录；cookie 留空则用账号组已绑定的凭据。"""

    try:
        added, fetched, warnings = await gacha.fetch_mihoyo_by_cookie(
            body.game,
            player_uid=body.playerUid,
            account_id=body.accountId,
            cookie=body.cookie.get_secret_value(),
            region=body.region,
            timezone=body.timezone,
            max_pages=body.maxPages,
        )
    except gacha.GachaAuthkeyError as error:
        # 核心层构造的文案只描述规则与 retcode，不含 Cookie/authkey，可以直接回显。
        raise ValueError(str(error)) from None
    except ValueError:
        # 其它失败（含内部模型校验）统一回脱敏文案，绝不外带响应原文。
        raise ValueError("记录读取未完成，请检查游戏 UID 与所选账号") from None
    except Exception:
        raise ValueError("抽卡记录请求未完成，请检查网络或米游社登录状态") from None
    return GachaUpdateOut(
        added=added,
        fetched=fetched,
        warnings=warnings,
        status="partial" if warnings else "success",
    )


@router.post(
    "/import", response_model=GachaUpdateOut, operation_id="importGachaRecords"
)
async def import_records(body: GachaImportIn) -> GachaUpdateOut:
    try:
        added, fetched, warnings = await gacha.import_records(
            body.game, body.payload.get_secret_value()
        )
    except Exception:
        raise ValueError(
            "导入未完成，请检查文件格式、字段及存储空间；原记录已保留"
        ) from None
    # 与 /fetch 的契约保持一致：有告警即部分成功。status 只描述本次调用结果，
    # 客户端（含生成的 OutBase.code 判断）仍按 code 与 warnings 决定提示。
    return GachaUpdateOut(
        added=added,
        fetched=fetched,
        warnings=warnings,
        status="partial" if warnings else "success",
    )


@router.post("/heybox", response_model=GachaHeyboxOut, operation_id="importGachaHeybox")
async def import_heybox(body: GachaHeyboxIn) -> GachaHeyboxOut:
    try:
        added, replaced, warnings, skipped = await gacha.import_heybox(
            body.game, body.heyboxId, body.playerUid, body.payload.get_secret_value()
        )
    except gacha.HeyboxError as error:
        # 协议层的校验文案只描述规则，不含响应原文与凭据，可以直接给用户看。
        raise ValueError(str(error)) from None
    except Exception:
        # 其它失败（含内部模型校验）统一回脱敏文案，绝不外带原始响应。
        raise ValueError(
            "小黑盒数据未导入，请检查小黑盒 ID、游戏 UID 与响应内容；原记录已保留"
        ) from None
    # 与 /fetch、/import 同一口径：有告警或跳过的卡池即部分成功。
    return GachaHeyboxOut(
        added=added,
        replaced=replaced,
        skipped=skipped,
        warnings=warnings,
        status="partial" if warnings or skipped else "success",
    )


@router.delete("/heybox", response_model=GachaUpdateOut, operation_id="revokeGachaHeybox")
async def revoke_heybox(
    game: Literal["endfield"] = "endfield",
    playerUid: str = Query(..., min_length=1, max_length=120),
) -> GachaUpdateOut:
    try:
        removed = await gacha.revoke_heybox(playerUid, game)
    except Exception:
        raise ValueError("撤销未完成，请稍后重试；记录已保留") from None
    # 只删派生行（标记为补录的四星占位与五星补名），官方六星记录不受影响。
    return GachaUpdateOut(
        added=0, message=f"已撤销 {removed} 条小黑盒补录记录"
    )


@router.get("/export", response_model=GachaExportOut, operation_id="exportGachaRecords")
async def export_records(
    game: GachaGame, playerUid: str = "", fileFormat: Literal["bmasc", "uigf"] = "bmasc"
) -> GachaExportOut:
    filename, content = gacha.export(game, playerUid, fileFormat)
    return GachaExportOut(filename=filename, content=content)
