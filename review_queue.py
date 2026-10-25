"""把 status=review(待人工判斷)的關係,連同調查紀錄,輸出成一份你隨時能讀的檔案。
程式只做組裝,判斷留給你。來源:raw_relations.jsonl(status=review)+ review_notes.json。
這就是你要的「留給我判斷的關係都接到一個檔案」的 pipeline 出口。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rels = [json.loads(l) for l in (ROOT / "data/raw_relations.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
notes_path = ROOT / "data/review_notes.json"
notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}

import csv
ents = {}
with open(ROOT / "data/seed_entities.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ents[row["id"]] = row["name_zh"]


def nm(i):
    return ents.get(i, i)


review = [r for r in rels if r.get("status") == "review"]
out = ["# 待人工判斷佇列（review queue）", "",
       f"共 {len(review)} 條。程式自動彙整,判斷與決定由你填。", "",
       "> 每條的「你的決定」欄預設空白。你確認後填 approved / rejected / 重構,我再據此更新圖。", ""]
for r in review:
    key = f"{r['source_id']}->{r['target_id']}:{r['kind']}"
    n = notes.get(key, {})
    out += [f"## {nm(r['source_id'])} → {nm(r['target_id'])}（{r['kind']}）",
            f"- 可信度:{r['confidence']}　來源層:{r['source_tier']}　出處:{r.get('source_ref', '')}",
            f"- 主張:{r['claim']}",
            f"- 調查紀錄:{n.get('investigation', '(待補)')}",
            f"- 參考來源:{'; '.join(n.get('sources', [])) or '(無)'}",
            f"- 我的建議:{n.get('recommendation', '(待補)')}",
            f"- **你的決定:** {n.get('decision') or '________'}", ""]
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/review-queue.md").write_text("\n".join(out), encoding="utf-8")
print(f"寫出 {len(review)} 條待判斷關係 → docs/review-queue.md")
