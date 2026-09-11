"""抽卡接口：凭据输入不回显，分页结果由模型描述。"""

from typing import Literal

from fastapi import APIRouter, Query

from app.core import gacha
from app.models.gacha import GachaGame
from app.models.schema import (
    GachaExportOut,
    GachaFetchIn,
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
    return GachaUpdateOut(added=added, fetched=fetched, warnings=warnings)


@router.get("/export", response_model=GachaExportOut, operation_id="exportGachaRecords")
async def export_records(
    game: GachaGame, playerUid: str = "", fileFormat: Literal["bmasc", "uigf"] = "bmasc"
) -> GachaExportOut:
    filename, content = gacha.export(game, playerUid, fileFormat)
    return GachaExportOut(filename=filename, content=content)
