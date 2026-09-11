"""抽卡记录的持久化字段；授权链接及 token 不属于记录。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GachaGame = Literal["genshin", "starrail", "zzz", "wuthering", "arknights", "endfield"]


class GachaRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game: GachaGame
    playerUid: str = Field(min_length=1, max_length=120)
    id: str = Field(min_length=1, max_length=200)
    poolType: str = Field(min_length=1, max_length=120)
    poolName: str = Field(default="", max_length=180)
    name: str = Field(min_length=1, max_length=180)
    itemId: str = Field(default="", max_length=100)
    itemType: str = Field(default="", max_length=80)
    rarity: int = Field(ge=1, le=6)
    time: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$")
    timezone: int = Field(default=8, ge=-12, le=14)
    lang: str = Field(default="zh-cn", max_length=20)
    isFree: bool = False
    kind: str = Field(default="", max_length=60)
