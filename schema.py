"""資料結構:每條關係都必附出處與 confidence。
刻意只用 Pydantic,不引任何 agent 框架 — 這規模用 dict + 驗證就夠。"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Tier = Literal["primary", "institution", "critic", "popular", "other"]
Kind = Literal[
    "influence", "critique", "extend", "belongs_to", "contrast", "discusses",
    # 一本著作/一個人可長出的多線連結
    "translate",   # 譯本:譯作→原作、或譯者→譯作
    "study",       # 研究:學術研究/專著探討某作品或概念
    "review",      # 評論:評論/書評針對某作品
    "interpret",   # 詮釋:對某作品或概念提出詮釋
    "exhibit",     # 展覽:展覽展出某作品/攝影家
]


class Entity(BaseModel):
    id: str
    type: Literal["person", "work", "concept", "event", "institution"]
    name_zh: str
    name_en: Optional[str] = None


class Relation(BaseModel):
    source_id: str          # 關係的起點實體
    target_id: str          # 關係的終點實體
    kind: Kind
    claim: str              # 這條關係主張什麼
    evidence: str = ""      # 原文片段或依據,供溯源
    source_ref: str         # 出處:對應 sources.csv 的 id
    source_tier: Tier
    confidence: float = Field(ge=0, le=1)
    status: Literal["auto", "review", "approved", "rejected"] = "review"
