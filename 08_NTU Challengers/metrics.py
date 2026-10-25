"""兩個指標,回應評審第二點:觀察推薦何時開始重複,據此決定擴充。
刻意只用計數,不上任何分析套件。"""


def repetition_rate(recommended_ids):
    """R = 重複出現數 / 總推薦數。0 表示完全沒重複。"""
    total = len(recommended_ids)
    if total == 0:
        return 0.0
    seen, repeats = set(), 0
    for rid in recommended_ids:
        if rid in seen:
            repeats += 1
        seen.add(rid)
    return round(repeats / total, 3)


def coverage(recommended_ids, all_node_ids):
    """C = 曾被推薦到的節點 / 全部節點。看推薦是否只在小圈子打轉。"""
    if not all_node_ids:
        return 0.0
    return round(len(set(recommended_ids) & set(all_node_ids)) / len(set(all_node_ids)), 3)


def should_expand(R, frontier_size, r_threshold=0.4):
    """R 超門檻,或知識前緣已空,就觸發 Agent 自主擴充來源。"""
    return R > r_threshold or frontier_size == 0
