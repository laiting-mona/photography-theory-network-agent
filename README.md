# 觀看的座標 — 攝影論述知識圖譜 Agent

把攝影理論與攝影史裡「誰影響誰、哪本書談哪個概念、哪個流派有哪些成員」
這類關係,建成一張**每條連結都附出處與可信度**的知識圖譜,
並以此做個人化的閱讀推薦。

核心原則:**程式能做的用程式,只有判斷才交給 LLM**。
關係不是請模型「生成」出來的,而是經過結構化抽取 → 權威加權評分 →
(低信心的)人工/上網查證三道關卡,confidence 低於門檻就進佇列,不會被當成定論。

---

## 目前狀態(可重現)

從專案根目錄執行 `python graph_build.py`,會重跑出下列數字:

| 指標 | 數 | 說明 |
|---|---|---|
| 節點 | 298 | 人物 · 著作 · 概念 · 事件 · 館所 |
| 關係(全) | 294 | 每條皆附 claim / evidence / source / confidence |
| **正式入圖** | **251** | 自動通過 99 + 上網查證確認 152 |
| 待查證 | 41 | 低信心,隔離在佇列,需回原典補頁碼後才採用 |
| 已剔除 | 2 | 查證不成立(如 1977 Pictures 展未含辛蒂·雪曼) |

41 條待查證的明細見 `docs/原典查核清單.xlsx`(附書名、待補頁碼欄、決定欄)。
查證來源網址見 `docs/verification-sources.md`。

---

## 目錄結構

```
.
├── schema.py          資料結構:Entity / Relation(每條關係強制附出處)
├── authority.py       權威加權評分:confidence = f(來源層級, 佐證數, 直接程度)
├── graph_build.py     建圖、算中心性 → build/graph.json  ★主入口
├── build_viewer.py    graph.json → 單頁互動圖 build/viewer.html
├── recommend.py       個人化推薦(走知識前緣,非熱門)
├── query.py           自然語言問句 → 圖查詢
├── agent.py           Agent v1(可直接 demo)
├── metrics.py         覆蓋率/可信度指標
├── extract.py         抽取管線(訂閱制、不亂猜)
├── captures.py        原始擷取紀錄
├── review_queue.py    把 status=review 的關係輸出成待審清單
├── test_core.py       最小回歸測試(純 assert,13 項)
│
├── data/              正典資料(唯一事實來源)
│   ├── seed_entities.csv      節點
│   ├── sources.csv            書目/來源
│   ├── raw_relations.jsonl    ★所有關係 + status + 出處
│   ├── captures.jsonl         擷取紀錄
│   ├── review_notes.json      人工註記
│   └── test_prompts.json      測試題庫
│
├── tools/             一次性/輔助工具(非核心流程)
│   ├── make_checklist.py      產生 docs/原典查核清單.{md,xlsx}
│   └── build_reflection.js    產生學習反思 docx(需 Node + docx)
│
├── prompts/extract.txt        抽取用 prompt
├── experiments/               權重敏感度實驗
├── docs/                      文件、查證來源、查核清單、投稿文件
└── build/                     產出(graph.json / viewer.html,可重建)
```

---

## 怎麼跑

```bash
pip install -r requirements.txt       # pydantic, networkx

python graph_build.py                 # 建正式圖(251 條)→ build/graph.json
python graph_build.py --with-review   # 連 41 條待查證一起畫(供檢視,非定論)
python build_viewer.py                # 產生 build/viewer.html,瀏覽器開即可
python test_core.py                   # 跑 13 項回歸測試
python agent.py                       # Agent demo
```

輔助工具(需額外套件):

```bash
pip install openpyxl && python tools/make_checklist.py    # 更新查核清單
npm install docx && node tools/build_reflection.js        # 重建反思 docx
```

---

## 關係的生命週期(status)

| status | 意思 | 進正式圖? |
|---|---|---|
| `auto` | confidence ≥ 0.70,公式自動通過 | ✓ |
| `approved` | 人工/上網查證確認,evidence 附來源網址 | ✓ |
| `review` | confidence < 0.70,待回原典查核 | ✗(在佇列) |
| `rejected` | 查證不成立 | ✗(永遠排除) |

可信度公式:`confidence = min(1.0, 來源層級權重 + 0.10 × (佐證數−1)) × 直接程度`。
`graph_build.py` 預設只納入 `auto` + `approved`;`rejected` 任何情況都不進圖。
