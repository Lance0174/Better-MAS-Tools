"""终末地资料库与活动日历的 HTTP 契约；整理由 core/services 负责。

同步与查询都只做契约转换：索引缺失、版本不一致或上游取不到数据时，交由 services
转成可读的错误文案，本模块不接触任何上游响应体。

日历有两种读法：`/calendar?game=<一个游戏>` 与 `/calendar-all`（一次返回全部游戏）。
后者是给活动日历页用的：那里八个游戏要同时展示，逐个请求会串行等待、首屏变慢，而
`game=all` 这种"魔法值"会把枚举参数变成半开放参数（类型上不再是 Literal，OpenAPI
生成的客户端也拿不到每个游戏的取值提示）。各游戏的失败互相隔离，取不到数据的那一个
只返回空列表加 message，不会让整个请求变成错误。
"""

from fastapi import APIRouter, Query, Request

from app.models.schema import (
    WikiCalendarAllOut,
    WikiCalendarGame,
    WikiCalendarGameOut,
    WikiCalendarOut,
    WikiEntryKind,
    WikiEntryOut,
    WikiSearchOut,
    WikiStatusDataOut,
    WikiStatusOut,
    WikiSyncIn,
)
from app.services.endfield_wiki import wiki

router = APIRouter(prefix="/api/wiki", tags=["Wiki"])


def _get_wiki(request: Request):
    """优先使用运行时注入的资料库，桌面测试保留模块级回退。"""
    return getattr(request.app.state, "wiki", wiki)


@router.get("/status", response_model=WikiStatusOut, operation_id="getWikiStatus")
async def get_status(request: Request) -> WikiStatusOut:
    current = _get_wiki(request)
    return WikiStatusOut(data=WikiStatusDataOut(**current.status()))


@router.post("/sync", response_model=WikiStatusOut, operation_id="syncWikiData")
async def sync(request: Request, body: WikiSyncIn | None = None) -> WikiStatusOut:
    outcome = await _get_wiki(request).sync(force=bool(body and body.force))
    return WikiStatusOut(
        data=WikiStatusDataOut(**outcome), message=outcome.get("message", "")
    )


@router.get("/search", response_model=WikiSearchOut, operation_id="searchWikiEntries")
async def search(
    request: Request,
    q: str = Query("", max_length=100, description="关键词：名称、昵称或简称"),
    limit: int = Query(20, ge=1, le=50),
) -> WikiSearchOut:
    return WikiSearchOut(data=_get_wiki(request).search(q, limit))


@router.get("/entry", response_model=WikiEntryOut, operation_id="getWikiEntry")
async def get_entry(
    request: Request, kind: WikiEntryKind, id: str = Query(..., min_length=1)
) -> WikiEntryOut:
    return WikiEntryOut(data=_get_wiki(request).entry(kind, id), message="")


@router.get("/calendar", response_model=WikiCalendarOut, operation_id="getWikiCalendar")
async def get_calendar(request: Request, game: WikiCalendarGame) -> WikiCalendarOut:
    # 取不到数据不是错误：data 为空列表，message 里说明是缓存兜底还是上游不可用。
    outcome = await _get_wiki(request).calendar_outcomes(game)
    return WikiCalendarOut(data=outcome.rows, message=outcome.message or "操作成功")


@router.get(
    "/calendar-all", response_model=WikiCalendarAllOut, operation_id="getWikiCalendarAll"
)
async def get_calendar_all(request: Request) -> WikiCalendarAllOut:
    outcomes = await _get_wiki(request).calendar_outcomes_all()
    return WikiCalendarAllOut(data=[WikiCalendarGameOut(**item.contract()) for item in outcomes])
