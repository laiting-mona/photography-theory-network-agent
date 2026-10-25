# -*- coding: utf-8 -*-
"""把目前仍待查證(status==review)的關係,整理成一份『原典查核清單』。
輸出(皆在專案 docs/ 下):
  docs/原典查核清單.md    版本控管用
  docs/原典查核清單.xlsx  可填:頁碼、決定(approved / rejected / 重構)
每條附:關係、類型、主張、建議查核原典(由 source_ref 對應 sources.csv)、
空白的頁碼欄與決定欄。
用法(從專案根目錄):python tools/make_checklist.py"""
import json, csv
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent   # tools/ 的上一層 = 專案根
OUT_XLSX = ROOT / "docs/原典查核清單.xlsx"
OUT_MD = ROOT / "docs/原典查核清單.md"

nm = {r["id"]: r["name_zh"] for r in csv.DictReader(open(ROOT/"data/seed_entities.csv", encoding="utf-8"))}
src = {r["id"]: (r["name_zh"], r.get("author", "")) for r in csv.DictReader(open(ROOT/"data/sources.csv", encoding="utf-8"))}
KZH = {"influence": "影響", "critique": "批判", "extend": "延伸", "belongs_to": "屬於",
       "contrast": "對照", "discusses": "討論", "translate": "譯本", "study": "研究",
       "review": "評論", "interpret": "詮釋", "exhibit": "展覽"}
# 對 source_ref 無對應書目者,給建議查核方向
OVERRIDE = {
    "interpretation": "蕭爾《The Nature of Photographs》與相關評論(需指定具體文本)",
    "asx": "American Suburb X 評論平台(需找到具體文章)",
    "cphmag": "Conscientious 等評論平台(需找到具體文章)",
}
# 已查到、據實保留待查的備註
NOTE = {
    ("sherman", "pictures_1977", "belongs_to"): "查證發現:1977 Pictures 展原始五人不含雪曼(1979 才被加入),建議 reject 或改記為『圖景世代』",
    ("sontag", "weston", "discusses"): "查證發現:桑塔格《論攝影》具名清單中未見威斯頓,建議 reject 或待原文確認",
}

rows = [json.loads(l) for l in open(ROOT/"data/raw_relations.jsonl", encoding="utf-8") if l.strip()]
rev = [r for r in rows if r["status"] == "review"]
# 以 target 群聚、再依 source 排序,方便一次查同一主題
rev.sort(key=lambda r: (r["target_id"], r["source_id"]))


def book_for(r):
    sref = r.get("source_ref", "")
    if sref in OVERRIDE:
        return OVERRIDE[sref]
    if sref in src:
        n, a = src[sref]
        return f"{n}（{a}）" if a else n
    return "(需自行指定原典)"


# ---- Markdown ----
md = ["# 原典查核清單（觀看的座標）", "",
      f"待查證關係共 **{len(rev)}** 條。建議回對應原典補上頁碼級出處後,把『決定』填為 approved / rejected / 重構;",
      "確認後,把對應關係在 `data/raw_relations.jsonl` 的 `status` 改為 approved / rejected,並於 evidence 補上頁碼與來源,再執行 `python graph_build.py` 重建圖。", "",
      "| # | 關係 | 類型 | 主張 | 建議查核原典 | 頁碼(待補) | 決定 | 備註 |",
      "|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rev, 1):
    rel = f"{nm.get(r['source_id'],r['source_id'])} → {nm.get(r['target_id'],r['target_id'])}"
    note = NOTE.get((r["source_id"], r["target_id"], r["kind"]), "")
    md.append(f"| {i} | {rel} | {KZH.get(r['kind'],r['kind'])} | {r['claim']} | {book_for(r)} |  |  | {note} |")
OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

# ---- XLSX ----
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "原典查核清單"
headers = ["#", "關係(來源→目標)", "類型", "主張", "建議查核原典", "頁碼(待補)", "決定", "備註"]
widths = [5, 26, 8, 46, 34, 14, 14, 40]
hfill = PatternFill("solid", fgColor="1E2329")
hfont = Font(bold=True, color="FFFFFF", size=11)
thin = Side(style="thin", color="BBBBBB")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical="top")
ws.append(headers)
for c, w in enumerate(widths, 1):
    ws.column_dimensions[chr(64+c)].width = w
    cell = ws.cell(row=1, column=c)
    cell.fill = hfill; cell.font = hfont; cell.alignment = Alignment(vertical="center")
    cell.border = border
for i, r in enumerate(rev, 1):
    rel = f"{nm.get(r['source_id'],r['source_id'])} → {nm.get(r['target_id'],r['target_id'])}"
    note = NOTE.get((r["source_id"], r["target_id"], r["kind"]), "")
    ws.append([i, rel, KZH.get(r["kind"], r["kind"]), r["claim"], book_for(r), "", "", note])
    for c in range(1, 9):
        ws.cell(row=i+1, column=c).alignment = wrap
        ws.cell(row=i+1, column=c).border = border
# 決定欄下拉:approved / rejected / 重構
dv = DataValidation(type="list", formula1='"approved,rejected,重構"', allow_blank=True)
ws.add_data_validation(dv)
dv.add(f"G2:G{len(rev)+1}")
ws.freeze_panes = "A2"
OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT_XLSX)
print(f"產出:{OUT_MD.name}（{len(rev)} 條）、{OUT_XLSX}")
