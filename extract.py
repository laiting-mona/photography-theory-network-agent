"""抽取管線:刻意走「訂閱制、不碰 API」的最省路線。
  1) prepare 模式:對每個尚未處理的來源,產生一份 prompt 檔(含你貼進去的段落)。
     你把 prompt 貼進 Claude 訂閱版、把回傳的 JSON 存到 build/responses/<id>.json。
  2) ingest 模式:讀回那些 JSON,用 schema 驗證、算 confidence、分流 auto / review,
     併進 data/raw_relations.jsonl。
這樣抽取的「agent」就是 Claude 本人,不需要付費 API,也符合著作權(只貼你讀到的段落)。
"""
import csv, json, sys
from pathlib import Path
from schema import Relation
from authority import auto_confidence, route

ROOT = Path(__file__).parent
PROMPTS, RESP = ROOT / "build/prompts", ROOT / "build/responses"
TEMPLATE = (ROOT / "prompts/extract.txt").read_text(encoding="utf-8")


def prepare():
    PROMPTS.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/sources.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        p = PROMPTS / f"{row['id']}.txt"
        p.write_text(TEMPLATE + f"\n\n# 來源:{row['name_zh']}（{row.get('author','')}）"
                     f"\n# tier: {row['tier']}  ref: {row['id']}\n"
                     f"# 在下面貼入你讀到的相關段落,再送進 Claude:\n\n<<貼段落>>\n",
                     encoding="utf-8")
    print(f"已產生 {len(rows)} 份 prompt 於 {PROMPTS}")


def ingest():
    out = ROOT / "data/raw_relations.jsonl"
    seen = set()  # 以 (source,target,kind) 做正規化去重,不受 JSON 格式差異影響
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                seen.add((o["source_id"], o["target_id"], o["kind"]))
    n = 0
    with open(out, "a", encoding="utf-8") as fout:
        for jf in sorted(RESP.glob("*.json")):
            data = json.loads(jf.read_text(encoding="utf-8"))
            for r in data.get("relations", []):
                r.setdefault("confidence",
                             auto_confidence(r.get("source_tier", "other"),
                                             r.get("n_sources", 1),
                                             r.get("directness", 1.0)))
                r["status"] = route(r["confidence"])
                rel = Relation(**{k: r[k] for k in Relation.model_fields if k in r})
                key = (rel.source_id, rel.target_id, rel.kind)
                if key not in seen:
                    fout.write(rel.model_dump_json() + "\n")
                    seen.add(key)
                    n += 1
    print(f"併入 {n} 條新關係 → {out}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    {"prepare": prepare, "ingest": ingest}.get(mode, prepare)()
