#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 MoeSnowyFox
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com

from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from app.models.config import AccountData, SettingsData
from app.models.gacha import GachaGame, GachaRecord


class OutBase(BaseModel):
    code: int = Field(default=200, description="状态码")
    status: str = Field(default="success", description="操作状态")
    message: str = Field(default="操作成功", description="操作消息")


class GameSignAccountGroupConfig(BaseModel):
    """游戏社区账号组配置"""

    Name: str | None = Field(default=None, description="账号组名称")
    Enabled: bool | None = Field(default=None, description="是否启用")
    MiyousheToken: str | None = Field(default=None, description="米游社登录凭证")
    MiyousheDeviceId: str | None = Field(
        default=None,
        description="米游社安卓设备 ID，仅用于绝区零便笺",
        repr=False,
    )
    MiyousheDeviceFp: str | None = Field(
        default=None,
        description="米游社安卓设备指纹，仅用于绝区零便笺",
        repr=False,
    )
    CloudGenshinToken: str | None = Field(
        default=None,
        description="云原神 combo token",
    )
    KuroToken: str | None = Field(default=None, description="库街区登录凭证")
    SklandToken: str | None = Field(default=None, description="森空岛登录凭证")
    TaygedoToken: str | None = Field(default=None, description="塔吉多及云异环登录凭证")
    LastSignDate: str | None = Field(default=None, description="账号组上次签到日期")


class CommunityActivityTaskOut(BaseModel):
    """日常活动中的单项任务。"""

    name: str = Field(..., description="任务名称")
    completed: int = Field(..., description="已完成数量")
    target: int = Field(..., description="目标数量")
    status: str = Field(..., description="任务状态")
    period: str = Field(default="daily", description="任务周期")


class CommunityActivityResourceOut(BaseModel):
    """日常活动中的可用资源。"""

    name: str = Field(..., description="资源名称")
    current: int = Field(..., description="当前数量")
    target: int = Field(..., description="容量上限")
    status: str = Field(..., description="资源状态")


class CommunityActivitySnapshotOut(BaseModel):
    """单个游戏角色的日常活动快照。"""

    account: str = Field(..., description="账号组名称")
    accountUid: str = Field(..., description="账号组 UUID")
    game: str = Field(..., description="游戏名称")
    platform: str = Field(..., description="社区平台名称")
    status: Literal["success", "empty", "limited", "unavailable", "failed"] = Field(
        ..., description="活动查询状态"
    )
    completed: int | None = Field(default=None, description="已完成数量")
    target: int | None = Field(default=None, description="目标数量")
    tasks: list[CommunityActivityTaskOut] = Field(
        default_factory=list, description="每日任务"
    )
    resources: list[CommunityActivityResourceOut] = Field(
        default_factory=list, description="可用资源"
    )
    reason: str = Field(default="", description="失败或受限原因")
    updatedAt: str = Field(default="", description="查询时间")
    roleName: str = Field(default="", description="角色名称")
    roleUid: str = Field(default="", description="角色 UID")
    server: str = Field(default="", description="角色区服")
    source: str = Field(default="", description="已确认的数据来源路径")


class CommunityActivityOut(OutBase):
    """游戏社区日常活动查询响应。"""

    data: list[CommunityActivitySnapshotOut] = Field(
        default_factory=list, description="按账号和游戏拆分的活动快照"
    )


class AccountOut(BaseModel):
    uid: str
    data: AccountData


class AccountsOut(OutBase):
    data: list[AccountOut]


class AccountCreateOut(OutBase):
    data: AccountOut


class AccountUpdateIn(BaseModel):
    accountId: str
    data: GameSignAccountGroupConfig


class AccountIdIn(BaseModel):
    accountId: str


class AccountReorderIn(BaseModel):
    order: list[str]


class SettingsOut(OutBase):
    data: SettingsData
    yunmaConfigured: bool = False
    localConnections: bool = Field(default=True, description="是否能连接后端主机的 MAS 与代理；纯 Workers 为 false")


class ActivityQueryIn(BaseModel):
    accountIds: list[str] | None = None


class SignGameOut(BaseModel):
    account: str = ""
    game: str = ""
    status: str = ""
    reward: str = ""
    reason: str = ""
    signedAt: str = Field(default="", description="实际执行时间，ISO 8601 北京时间")


class SignAccountOut(BaseModel):
    account_alias: str = ""
    account_uid: str = ""
    games: list[SignGameOut] = Field(default_factory=list)


class StatusOut(OutBase):
    running: bool = False
    activityRunning: bool = False
    revision: int = 0
    today: str = Field(default="", description="服务端北京时间日期")
    results: dict[str, list[SignAccountOut]] = Field(default_factory=dict)


class QrCreateOut(OutBase):
    ticket: str = ""
    qr_url: str = ""
    device: str = ""


class QrCheckIn(BaseModel):
    ticket: str
    device: str


class QrCheckOut(OutBase):
    cookies_str: str = Field(default="", repr=False)
    scan_code: str = Field(default="", repr=False)


class QrSaveIn(BaseModel):
    account_uid: str
    cookie: str = Field(default="", repr=False)
    scan_code: str = Field(default="", repr=False)


class TaygedoLoginIn(BaseModel):
    accountId: str
    phone: str = Field(min_length=1, repr=False)
    password: SecretStr = Field(min_length=1)


class KuroSmsCreateIn(BaseModel):
    accountId: str
    phone: SecretStr = Field(min_length=11, max_length=11)


class KuroSmsCreateOut(OutBase):
    sessionId: str
    captchaId: str
    expiresIn: int = 600


class KuroSmsSessionIn(BaseModel):
    sessionId: str = Field(min_length=1, max_length=100, repr=False)


class GeetestV4Data(BaseModel):
    captcha_id: str = Field(min_length=1, max_length=100)
    lot_number: str = Field(min_length=1, max_length=200, repr=False)
    pass_token: str = Field(min_length=1, max_length=4096, repr=False)
    gen_time: str = Field(min_length=1, max_length=100)
    captcha_output: str = Field(min_length=1, max_length=8192, repr=False)


class KuroSmsSendIn(KuroSmsSessionIn):
    verification: GeetestV4Data


class KuroSmsAutomaticOut(OutBase):
    sent: bool = False


class KuroSmsLoginIn(KuroSmsSessionIn):
    smsCode: SecretStr = Field(min_length=6, max_length=6)


class MiyousheVerificationOut(BaseModel):
    sessionId: str
    accountId: str
    label: str
    gt: str
    challenge: str = Field(repr=False)


class MiyousheVerificationsOut(OutBase):
    data: list[MiyousheVerificationOut] = Field(default_factory=list)


class GeetestV3Data(BaseModel):
    geetest_challenge: str = Field(min_length=1, max_length=300, repr=False)
    geetest_validate: str = Field(min_length=1, max_length=4096, repr=False)
    geetest_seccode: str = Field(min_length=1, max_length=4096, repr=False)


class MiyousheVerificationIn(BaseModel):
    sessionId: str = Field(min_length=1, max_length=100, repr=False)
    verification: GeetestV3Data


class GachaFetchIn(BaseModel):
    game: GachaGame
    source: SecretStr = Field(default=SecretStr(""), max_length=16000)
    accountId: str = ""
    playerUid: str = Field(default="", max_length=120)
    timezone: int = Field(default=8, ge=-12, le=14)
    maxPages: int = Field(default=100, ge=1, le=500)


class GachaImportIn(BaseModel):
    game: GachaGame
    payload: SecretStr = Field(min_length=2, max_length=20_000_000)


class GachaUpdateOut(OutBase):
    added: int = 0
    fetched: int = 0
    warnings: list[str] = Field(default_factory=list)


class GachaPoolOut(BaseModel):
    poolType: str
    poolName: str
    total: int
    topRarity: int
    topCount: int
    sinceTop: int


class GachaRecordsOut(OutBase):
    data: list[GachaRecord] = Field(default_factory=list)
    total: int = 0
    players: list[str] = Field(default_factory=list)
    pools: list[GachaPoolOut] = Field(default_factory=list)


class GachaExportOut(OutBase):
    filename: str
    content: str


class MasQueueOut(BaseModel):
    id: str
    name: str


class MasTaskOut(BaseModel):
    id: str
    mode: str
    stopping: bool = False


class MasSnapshotOut(OutBase):
    baseUrl: str
    queues: list[MasQueueOut] = Field(default_factory=list)
    tasks: list[MasTaskOut] = Field(default_factory=list)


class MasStartIn(BaseModel):
    taskId: str = Field(min_length=1, max_length=120)
    mode: Literal["AutoProxy", "CycleRun"] = "AutoProxy"


class MasStopIn(BaseModel):
    taskId: str = Field(min_length=1, max_length=120)


class MasStartOut(OutBase):
    taskId: str


class SessionLoginIn(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=512)


class SessionOut(OutBase):
    key: str = Field(default="", repr=False)
    loginRequired: bool = False
