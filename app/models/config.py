"""独立项目的持久化数据定义，不携带 MAS 专项任务配置。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.gacha import GachaRecord


class AccountData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    Name: str = Field(default="新账号", max_length=80)
    Enabled: bool = True
    MiyousheToken: str = Field(default="", repr=False)
    MiyousheDeviceId: str = Field(default="", repr=False)
    MiyousheDeviceFp: str = Field(default="", repr=False)
    CloudGenshinToken: str = Field(default="", repr=False)
    KuroToken: str = Field(default="", repr=False)
    SklandToken: str = Field(default="", repr=False)
    TaygedoToken: str = Field(default="", repr=False)
    LastSignDate: str = ""


class SettingsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    Enabled: bool = True
    ActivityEnabled: bool = True
    MiyousheBbsEnabled: bool = True
    RunOnStartup: bool = False
    ScheduledRun: bool = False
    ScheduledTime: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    LowPerformanceMode: bool = False
    Theme: Literal["light", "dark", "system"] = "system"
    Proxy: str = Field(default="", repr=False)
    CaptchaMode: Literal["manual", "local", "local_yunma"] = "local"
    YunmaToken: str | None = Field(default=None, repr=False)
    MasBaseUrl: str = Field(default="http://127.0.0.1:36163", max_length=200)


class SavedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    settings: SettingsData = Field(default_factory=SettingsData)
    accounts: dict[str, AccountData] = Field(default_factory=dict)
    results: list[dict[str, object]] = Field(default_factory=list)
    lastScheduledDate: str = ""
    gacha: list[GachaRecord] = Field(default_factory=list)
