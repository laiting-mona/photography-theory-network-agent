"""權威加權:因為攝影論述沒有引用圖譜,無法用引用次數判斷權威。
改用三個可查證訊號:來源分級(tier)、跨來源佐證數、以及關係陳述的直接程度。
刻意保持成一條簡單公式,方便在報告裡解釋,也方便審查。"""

TIER_BASE = {"primary": 0.85, "institution": 0.75, "critic": 0.6, "popular": 0.30, "other": 0.4}
AUTO = 0.7  # confidence >= AUTO 自動入圖;否則進人工佇列 review


def auto_confidence(tier: str, n_sources: int = 1, directness: float = 1.0) -> float:
    """pipeline 自動抽取時用的預設分數。
    directness:關係在來源中被陳述的直接程度(1.0 明說 / 0.7 隱含 / 0.5 詮釋)。
    多一個獨立佐證 +0.1。"""
    base = TIER_BASE.get(tier, 0.4)
    corroboration = 0.1 * max(0, n_sources - 1)
    return round(min(1.0, base + corroboration) * directness, 2)


def route(confidence: float) -> str:
    return "auto" if confidence >= AUTO else "review"
