"""個人化推薦:走知識前緣,不是主題相似度,也不訓練任何模型。
前緣 = 從已讀節點往外一跳、尚未讀、且 confidence 夠高的鄰居。
排序 = confidence x 來源權重 x 目標節點中心性。附理由與出處。"""
import json, sys
from pathlib import Path
import networkx as nx
from authority import TIER_BASE

ROOT = Path(__file__).parent


def load_graph():
    data = json.loads((ROOT / "build/graph.json").read_text(encoding="utf-8"))
    return nx.node_link_graph(data, edges="links", directed=True, multigraph=True)


def recommend(G, read_ids, top_n=5):
    read = set(read_ids)
    # 讀到一本書(work)時,順著 belongs_to 走到作者(person),用作者的 frontier 一起推薦
    bridges = set()
    for u in list(read):
        if u in G and G.nodes[u].get("type") == "work":
            for p in G.predecessors(u):
                if G.nodes[p].get("type") != "person":
                    continue
                if any(d.get("kind") == "belongs_to"
                       for _, vv, d in G.out_edges(p, data=True) if vv == u):
                    bridges.add(p)
    seeds = read | bridges      # 從書與其作者一起出發
    exclude = read | bridges    # 已讀的書、與當橋樑的作者,都不再推薦
    cands = {}  # target -> 最佳的一條支持邊
    for u in seeds:
        if u not in G:
            continue
        for _, v, d in G.out_edges(u, data=True):
            if v in exclude:
                continue
            w = d.get("confidence", 0) * TIER_BASE.get(d.get("source_tier", "other"), 0.4) \
                * (0.5 + G.nodes[v].get("centrality", 0))
            if v not in cands or w > cands[v][0]:
                cands[v] = (w, u, d)
    ranked = sorted(cands.items(), key=lambda x: -x[1][0])[:top_n]
    out = []
    for v, (w, u, d) in ranked:
        pending = d.get("status") == "review"
        out.append({
            "target": G.nodes[v].get("name_zh", v),
            "reason": f"你已讀「{G.nodes[u].get('name_zh', u)}」,它{_verb(d['kind'])}「"
                      f"{G.nodes[v].get('name_zh', v)}」:{d['claim']}"
                      + ("(待查證,尚未確認)" if pending else ""),
            "source": d.get("source_ref", ""),
            "status": d.get("status", ""),
            "score": round(w, 3),
        })
    return out


def _verb(kind):
    return {"influence": "影響了", "critique": "批判了", "extend": "延伸自",
            "belongs_to": "屬於", "contrast": "對照於", "discusses": "討論了"}.get(kind, "連結到")


if __name__ == "__main__":
    G = load_graph()
    profile = sys.argv[1:] or ["benjamin", "on_photography"]  # 範例:已讀班雅明與論攝影
    for r in recommend(G, profile):
        print(f"• {r['target']}  [{r['score']}]  — {r['reason']}  (出處:{r['source']})")
