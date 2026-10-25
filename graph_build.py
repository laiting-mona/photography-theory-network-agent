"""讀 raw_relations.jsonl + seed_entities.csv,建圖,算中心性,輸出 build/graph.json。
NetworkX 在這裡是刀刃用對地方:40-50 節點算 centrality 幾乎零成本,
又能當權威訊號之一,比自己手刻圖演算法好讀好維護。"""
import csv, json, sys
from pathlib import Path
import networkx as nx
from schema import Relation, Entity

ROOT = Path(__file__).parent
# 預設只建「正式圖」:auto(公式自動通過)+ approved(查證確認)。
# review(低信心、待回原典查核)隔離在佇列,不進正式圖;rejected 永遠排除。
# 加 --with-review 旗標可把 review 也畫進來(供檢視,非定論)。
WITH_REVIEW = "--with-review" in sys.argv


def load_entities():
    ents = {}
    with open(ROOT / "data/seed_entities.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            e = Entity(**{k: row[k] for k in ("id", "type", "name_zh", "name_en") if row.get(k)})
            ents[e.id] = e
    return ents


def load_relations():
    rels = []
    with open(ROOT / "data/raw_relations.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rels.append(Relation(**json.loads(line)))
    return rels


def build():
    ents = load_entities()
    rels = load_relations()
    IN_GRAPH = ("auto", "approved", "review") if WITH_REVIEW else ("auto", "approved")
    usable = [r for r in rels if r.status in IN_GRAPH]

    # MultiDiGraph:允許同一對節點有多條不同 kind 的邊,不會靜默覆蓋
    G = nx.MultiDiGraph()
    for e in ents.values():
        G.add_node(e.id, **e.model_dump())
    for r in rels:  # 節點即使只出現在關係裡也補進來
        for nid in (r.source_id, r.target_id):
            if nid not in G:
                G.add_node(nid, id=nid, type="concept", name_zh=nid, name_en=None)
    for r in usable:
        # 以 kind 當 edge key:同一對不同 kind 各自保留;同一對同 kind 才覆蓋(去重)
        G.add_edge(r.source_id, r.target_id, key=r.kind, **r.model_dump())

    cent = nx.degree_centrality(G)
    for nid, c in cent.items():
        G.nodes[nid]["centrality"] = round(c, 3)

    out = nx.node_link_data(G, edges="links")
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/graph.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    n_auto = sum(1 for r in rels if r.status == "auto")
    n_appr = sum(1 for r in rels if r.status == "approved")
    n_review = sum(1 for r in rels if r.status == "review")
    n_rej = sum(1 for r in rels if r.status == "rejected")
    print(f"節點 {G.number_of_nodes()}  關係(全) {len(rels)}  "
          f"正式入圖 {len(usable)}(自動 {n_auto} + 查證確認 {n_appr})  "
          f"待查證 {n_review}  已剔除 {n_rej}")
    top = sorted(cent.items(), key=lambda x: -x[1])[:5]
    print("中心性 Top5:", ", ".join(f"{G.nodes[n]['name_zh']}({c:.2f})" for n, c in top))
    return G


if __name__ == "__main__":
    build()
