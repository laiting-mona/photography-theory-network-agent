"""觀看的座標 · Agent v1(可直接 demo)。
設計原則:程式坐駕駛座、LLM 只做第 3 步「抽取判斷」。
一輪 = 規劃 → 檢索 → 抽取(LLM) → 評分分流 → 更新圖 → 監控,會迴圈。

兩種模式:
  --replay(預設,給 demo):對已擷取的資料整輪自動跑,印出 agent 軌跡,零 LLM 成本。
  --live  (實際擴圖):第 3 步改呼叫訂閱版抽取(extract.py 的 prepare/ingest)。
把軌跡印成「思考/行動/觀察」的形式,看起來就是經典 agent。
"""
import csv, json, sys
from pathlib import Path
import authority, metrics

ROOT = Path(__file__).resolve().parent
ents = {}
with open(ROOT / "data/seed_entities.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ents[row["id"]] = row["name_zh"]
nm = lambda i: ents.get(i, i)

rels = [json.loads(l) for l in (ROOT / "data/raw_relations.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
by_src = {}
for r in rels:
    by_src.setdefault(r["source_id"], []).append(r)

# 規劃順序:主線五家(程式用啟發式挑;這裡用固定主線當 demo)
PLAN = ["benjamin", "berger", "sontag", "barthes", "shore"]
WORK = {"benjamin": "〈攝影小史〉/〈機械複製時代的藝術作品〉", "berger": "《觀看的方式》",
        "sontag": "《論攝影》", "barthes": "《明室》", "shore": "《照片的本質》"}
# 涵蓋率分母 = 全部已定義節點(含尚未連邊的館所),與圖的節點數一致
ALL_NODES = set(ents) | {n for r in rels for n in (r["source_id"], r["target_id"])}


def line(c=""):
    print(c)


def run_replay():
    line("═" * 60)
    line("觀看的座標 · Agent v1　[replay 模式 · 零 LLM 成本]")
    line("═" * 60)
    covered, prev_targets = set(), set()
    auto_tot = rev_tot = 0
    for i, seed in enumerate(PLAN, 1):
        batch = by_src.get(seed, [])
        line(f"\n── 第 {i} 輪 ──────────────────────────────")
        line(f"🧠 思考：圖中「{nm(seed)}」是主線核心,目前由它出發的關係 {len(batch)} 條,選它擴充。")
        line(f"🔧 行動：檢索來源「{WORK.get(seed,'')}」,讀取相關段落。")
        line("👁 觀察：取得文字片段(replay:取自已擷取語料)。")
        line(f"🤖 抽取[LLM]：從文字抽出 {len(batch)} 條候選關係(附出處)。")
        a = r = 0
        for rel in batch:
            conf = rel["confidence"]
            route = authority.route(conf)
            tgt = nm(rel["target_id"])
            mark = "✓入圖" if route == "auto" else "⟳待判斷"
            line(f"     · {nm(seed)} {rel['kind']} {tgt}  conf={conf} [{rel['source_tier']}] → {mark}")
            covered.add(rel["source_id"]); covered.add(rel["target_id"])
            if route == "auto": a += 1
            else: r += 1
        auto_tot += a; rev_tot += r
        # 監控
        tgts = {rel["target_id"] for rel in batch}
        rep = len(tgts & prev_targets) / len(tgts) if tgts else 0
        cov = len(covered) / len(ALL_NODES)
        prev_targets |= tgts
        line(f"📊 評分分流：{a} 條入圖、{r} 條進判斷佇列。")
        line(f"📈 監控：重複率 R={rep:.2f}　涵蓋率 C={cov:.2f}　"
             f"→ {'需擴充' if metrics.should_expand(rep, len(batch)) else '續跑下一輪'}")
    line("\n" + "═" * 60)
    line(f"結束:累計入圖 {auto_tot} 條、判斷佇列 {rev_tot} 條,覆蓋 {len(covered)}/{len(ALL_NODES)} 節點。")
    # 推薦 demo
    line("\n🎯 推薦示範(給『已讀桑塔格《論攝影》』的學習者):")
    try:
        import recommend
        G = recommend.load_graph()
        for rec in recommend.recommend(G, ["sontag", "on_photography"], top_n=3):
            line(f"   • {rec['target']}  — {rec['reason'][:46]}…（出處:{rec['source']}）")
    except Exception as e:
        line(f"   (推薦模組需先 python3 graph_build.py;{e})")
    line("═" * 60)


def run_live():
    line("live 模式:第 3 步改用訂閱版抽取。")
    line("流程:python3 extract.py prepare → 把 prompt 貼進 Claude 訂閱版 → 存回 responses/ →")
    line("      python3 extract.py ingest → python3 graph_build.py → 再跑本 agent 檢視。")
    line("(v1 不呼叫付費 API;要全自動無人跑再加 --api,目前依你的決定先不開。)")


if __name__ == "__main__":
    (run_live if "--live" in sys.argv else run_replay)()
