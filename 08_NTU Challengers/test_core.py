"""最小回歸測試(純 assert,不需 pytest)。確保核心行為不走樣。
跑法:python3 test_core.py"""
import sys
import networkx as nx
from pydantic import ValidationError
import schema, authority, metrics, graph_build

# Windows 主控台預設 cp950,印不出 ✓/中文會崩;統一改走 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ok = 0


def check(name, cond):
    global ok
    assert cond, "FAIL: " + name
    ok += 1
    print("  ✓", name)


# 1 schema 擋壞資料
try:
    schema.Relation(source_id="a", target_id="b", kind="influence",
                    source_ref="x", source_tier="BADTIER", confidence=0.5)
    raise SystemExit("schema 應擋掉錯誤 tier")
except ValidationError:
    check("schema 擋掉非法 source_tier", True)
try:
    schema.Relation(source_id="a", target_id="b", kind="influence",
                    source_ref="x", source_tier="primary", confidence=5)
    raise SystemExit("schema 應擋掉 confidence>1")
except ValidationError:
    check("schema 擋掉 confidence 超範圍", True)

# 2 權重分流門檻(AUTO=0.7)
check("route 0.70 → auto", authority.route(0.70) == "auto")
check("route 0.69 → review", authority.route(0.69) == "review")

# 3 metrics
check("repetition_rate 抓重複", metrics.repetition_rate(["a", "a", "b"]) == round(1 / 3, 3))
check("coverage 正確", metrics.coverage(["a"], ["a", "b"]) == 0.5)

# 4 建圖 + MultiDiGraph 平行邊不被覆蓋
G = graph_build.build()
check("圖至少 60 節點", G.number_of_nodes() >= 60)
H = nx.MultiDiGraph()
H.add_edge("x", "y", key="influence")
H.add_edge("x", "y", key="critique")
check("MultiDiGraph 保留同對不同 kind 的平行邊", H.number_of_edges() == 2)

# graph.json 已重建成新格式,之後才載入下游模組
import recommend, query

# 5 推薦:讀到書會橋接到作者;且帶 status 欄
Gq = recommend.load_graph()
recs = recommend.recommend(Gq, ["on_photography"], top_n=3)
check("只給書名也能推薦(書→作者橋接)", len(recs) > 0)
check("推薦帶 status 欄", all("status" in r for r in recs))

# 6 查核:對不存在的關係不編造
intent, ids, res = query.answer("班雅明 馬格南 有關係嗎 出處在哪")
check("provenance 意圖判對", intent == "provenance")
check("對不存在關係回 not found(不編造)", res.get("found") is False)
_, _, res2 = query.answer("隨便亂打一個不存在的 xyz 出處")
check("無法解析時不爆、仍回 dict", isinstance(res2, dict))

print(f"\n全部通過:{ok} 項 ✓")
