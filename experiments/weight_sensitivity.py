"""權重敏感度實驗(右尺寸,純 stdlib,不用 ML)。
量兩件事:top-5 集合重疊(Jaccard,換權重後推薦清單變多少),
以及完整候選的排序相關(Spearman,換權重後名次變多少)。
集合不變、但名次會變時,Spearman 比 Jaccard 敏感,適合看 popular 權重的細微影響。
隔離:只讀 ../build/graph.json,結果寫 results/,不改動圖或來源。"""
import json, csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from authority import TIER_BASE  # baseline 權重只有一份來源,不會兩邊不同步

ROOT = Path(__file__).resolve().parent.parent
G = json.loads((ROOT / "build/graph.json").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in G["nodes"]}
OUT = {}
for e in G["links"]:
    OUT.setdefault(e["source"], []).append(e)

BASE = {k: TIER_BASE[k] for k in ("primary", "institution", "critic", "popular")}
WEIGHTS = {
    "baseline":  dict(BASE),
    "flat":      {"primary": 0.70, "institution": 0.70, "critic": 0.70, "popular": 0.70},
    "steep":     {"primary": 0.95, "institution": 0.70, "critic": 0.40, "popular": 0.15},
    "swapped":   {"primary": 0.50, "institution": 0.60, "critic": 0.85, "popular": 0.30},
    "pop_0.30":  {**BASE, "popular": 0.30},
    "pop_0.15":  {**BASE, "popular": 0.15},
    "pop_0.10":  {**BASE, "popular": 0.10},
}
PROFILES = {
    "讀過班雅明": ["benjamin"], "讀過巴特": ["barthes"], "讀過桑塔格": ["sontag"],
    "讀過薩考斯基": ["szarkowski"], "讀過伯格": ["berger"], "讀過蕭爾": ["shore"],
}


def ranked(profile, w):
    read = set(profile)
    cand = {}
    for u in profile:
        for e in OUT.get(u, []):
            v = e["target"]
            if v in read:
                continue
            cent = NODES[v].get("centrality", 0)
            score = e["confidence"] * w.get(e["source_tier"], 0.4) * (0.5 + cent)
            cand[v] = max(cand.get(v, 0), score)
    return [v for v, _ in sorted(cand.items(), key=lambda x: -x[1])]


def jaccard(a, b):
    sa, sb = set(a[:5]), set(b[:5])
    return round(len(sa & sb) / len(sa | sb), 3) if (sa | sb) else 1.0


def spearman(order_a, order_b):
    """對兩份排序共同的候選算 Spearman rho(名次相關)。"""
    common = [x for x in order_a if x in order_b]
    n = len(common)
    if n < 2:
        return 1.0
    ra = {x: i for i, x in enumerate(order_a)}
    rb = {x: i for i, x in enumerate(order_b)}
    d2 = sum((ra[x] - rb[x]) ** 2 for x in common)
    return round(1 - 6 * d2 / (n * (n * n - 1)), 3)


base = {p: ranked(ids, WEIGHTS["baseline"]) for p, ids in PROFILES.items()}
(ROOT / "experiments/results").mkdir(parents=True, exist_ok=True)
rows = []
print(f"{'權重向量':<10}{'top5 Jaccard':<16}{'Spearman 名次相關':<18}")
for name, w in WEIGHTS.items():
    js, sp = [], []
    for p, ids in PROFILES.items():
        r = ranked(ids, w)
        js.append(jaccard(base[p], r))
        sp.append(spearman(base[p], r))
    aj, asp = round(sum(js) / len(js), 3), round(sum(sp) / len(sp), 3)
    rows.append({"weights": name, "avg_top5_jaccard": aj, "avg_spearman": asp})
    print(f"{name:<10}{aj:<16}{asp:<18}")

with open(ROOT / "experiments/results/weight_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print("\n結果寫入 experiments/results/weight_sensitivity.csv")
print("讀法:Jaccard=1 表 top-5 名單沒換;Spearman<1 表名次有變。兩者越低代表對權重越敏感。")
