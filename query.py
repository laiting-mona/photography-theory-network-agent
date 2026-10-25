"""v2 查詢層:自然語言問句 → 圖檢索 → 結構化結果 → 格式化輸出。
設計原則:全程式(字串比對 + difflib 容錯 + networkx),不呼叫 LLM。

輸出分兩層(方便之後交給 LLM 潤稿,即「調 AI 輸出格式」那一步):
  1) 每個 handler 回傳一個結構化 dict(帶 'type' 欄),是機器可讀的答案骨架。
  2) render(result) 依 type 把骨架格式化成文字;--json 則直接吐 dict。

用法:
  python3 query.py "問句"            # 格式化文字
  python3 query.py --json "問句"      # 結構化 dict(給介面或 LLM 潤稿)
  python3 query.py --test            # 用 test_prompts.json 掃穩定性
"""
import json, sys, difflib
from pathlib import Path
import networkx as nx
import recommend
from authority import TIER_BASE

ROOT = Path(__file__).resolve().parent
G = recommend.load_graph()
NAME = {n: G.nodes[n].get("name_zh", n) for n in G.nodes}

ALIASES = {
    "索引": "krauss", "index": "krauss",
    "新地誌": "new_topographics_1975", "new topographics": "new_topographics_1975",
    "庶民": "vernacular", "冷面": "deadpan",
    "布列松": "cartier_bresson", "cartier-bresson": "cartier_bresson", "cartier bresson": "cartier_bresson",
    "布迪厄": "bourdieu", "bourdieu": "bourdieu", "伯格": "berger", "berger": "berger",
    "克萊因": "klein", "柯特茲": "kertesz", "阿巴斯": "arbus",
    "馬格南": "magnum", "magnum": "magnum", "泰特": "tate", "tate": "tate",
    "大都會": "met", "現代美術館": "moma", "moma": "moma", "伊士曼": "eastman", "阿爾勒": "arles",
    "觀看的方式": "ways_of_seeing", "ways of seeing": "ways_of_seeing",
    "論攝影": "on_photography", "on photography": "on_photography",
    "明室": "camera_lucida", "camera lucida": "camera_lucida",
}


def _forms(nid):
    out = [NAME.get(nid, nid)]
    en = G.nodes[nid].get("name_en")
    if en:
        out.append(en)
    return out


def resolve(q):
    ql = q.lower().replace(" ", "")
    score = {}
    for surf, nid in ALIASES.items():
        if surf.lower().replace(" ", "") in ql:
            score[nid] = max(score.get(nid, 0), 0.95)
    for nid in G.nodes:
        for form in _forms(nid):
            f = form.lower().replace(" ", "")
            if len(f) < 2:
                continue
            if f in ql:
                score[nid] = max(score.get(nid, 0), 1.0)
            elif len(f) >= 3:
                best = 0.0
                for L in (len(f), len(f) + 1, len(f) - 1):
                    for i in range(0, max(0, len(ql) - L) + 1):
                        best = max(best, difflib.SequenceMatcher(None, f, ql[i:i + L]).ratio())
                if best >= 0.75:
                    score[nid] = max(score.get(nid, 0), round(best, 2))
    return [nid for nid, _ in sorted(score.items(), key=lambda x: -x[1])]


def classify(q):
    has = lambda ws: any(w in q for w in ws)
    if has(["出處", "根據", "來源", "可信", "真的假的", "查核", "文獻", "腦補", "求證", "依據", "哪來", "憑"]):
        return "provenance"
    if has(["權威", "平台", "podcast", "網站", "算數", "夠格", "在紅", "有料", "評論來源"]):
        return "authority"
    if has(["路線", "順序", "三週", "三禮拜", "清單", "讀書計畫", "備課", "循序"]):
        return "path"
    if has(["推薦", "下一本", "接下來", "讀什麼", "讀啥", "下一步", "該讀", "然後呢", "救救"]):
        return "recommend"
    if has(["演變", "之後", "接手", "後來", "怎麼變", "反駁", "繼續講", "發展", "怎麼來", "消逝之後"]):
        return "lineage"
    if has(["關係", "關聯", "批判", "對話", "差在哪", "差別", "vs", "比起來", "兜", "理一下", "反什麼", "有關", "分不清"]):
        return "relation"
    return "default"


# ── handlers:回傳結構化 dict(機器可讀骨架)──
def out_to(u, v):
    """u→v 的所有邊資料(對 DiGraph / MultiDiGraph 都適用)。"""
    return [d for _, vv, d in G.out_edges(u, data=True) if vv == v]


def _edge(u, v, d):
    return {"from": NAME.get(u, u), "to": NAME.get(v, v), "kind": d.get("kind"),
            "claim": d.get("claim"), "evidence": d.get("evidence") or "",
            "source": d.get("source_ref"), "tier": d.get("source_tier"),
            "confidence": d.get("confidence"), "status": d.get("status")}


def h_recommend(ids):
    if not ids:
        return {"type": "recommend", "resolved": False}
    recs = recommend.recommend(G, ids, top_n=3)
    return {"type": "recommend", "resolved": True, "seed": NAME.get(ids[0], ids[0]),
            "items": [{"target": r["target"], "reason": r["reason"], "source": r["source"]} for r in recs]}


def h_provenance(ids):
    if len(ids) < 2:
        return {"type": "provenance", "resolved": False, "nodes": [NAME.get(i, i) for i in ids]}
    u, v = ids[0], ids[1]
    es = [_edge(u, v, d) for d in out_to(u, v)] + [_edge(v, u, d) for d in out_to(v, u)]
    if not es:
        return {"type": "provenance", "resolved": True, "found": False,
                "a": NAME.get(u, u), "b": NAME.get(v, v)}
    return {"type": "provenance", "resolved": True, "found": True, "edges": es}


def h_lineage(ids):
    if not ids:
        return {"type": "lineage", "resolved": False}
    c = ids[0]
    origin = [_edge(u, c, d) for u in list(G.predecessors(c))[:3] for d in out_to(u, c)]
    follow = []
    for u in list(G.predecessors(c))[:1]:
        follow = [_edge(a, u, d) for a in list(G.predecessors(u))[:4] for d in out_to(a, u)]
    return {"type": "lineage", "resolved": True, "concept": NAME.get(c, c),
            "origin": origin, "followups": follow}


def h_relation(ids):
    if len(ids) < 2:
        return h_default(ids)
    u, v = ids[0], ids[1]
    es = [_edge(u, v, d) for d in out_to(u, v)] + [_edge(v, u, d) for d in out_to(v, u)]
    if es:
        return {"type": "relation", "direct": True, "edges": es}
    try:
        path = nx.shortest_path(G.to_undirected(), u, v)
        return {"type": "relation", "direct": False, "path": [NAME.get(x, x) for x in path]}
    except Exception:
        return {"type": "relation", "direct": False, "path": [],
                "a": NAME.get(u, u), "b": NAME.get(v, v)}


def h_authority(_ids):
    pop = [_edge(u, v, d) for u, v, d in G.edges(data=True) if d.get("source_tier") == "popular"]
    return {"type": "authority",
            "tiers": sorted(TIER_BASE.items(), key=lambda x: -x[1]),
            "popular_examples": pop}


def h_path(_ids):
    return {"type": "path", "weeks": [
        ["第1週", "伯格《觀看的方式》", "建立『觀看受意識形態形塑』的問題意識"],
        ["第2週", "桑塔格《論攝影》", "採集與觀看倫理"],
        ["第3週", "巴特《明室》", "刺點/此曾在的現象學;行有餘力接蕭爾《照片的本質》"]]}


def h_default(ids):
    if not ids:
        return {"type": "unresolved"}
    c = ids[0]
    return {"type": "default", "node": NAME.get(c, c),
            "out": [_edge(u, v, d) for u, v, d in list(G.out_edges(c, data=True))[:6]],
            "in": [_edge(u, v, d) for u, v, d in list(G.in_edges(c, data=True))[:4]]}


HANDLERS = {"recommend": h_recommend, "provenance": h_provenance, "lineage": h_lineage,
            "relation": h_relation, "authority": h_authority, "path": h_path, "default": h_default}


# ── renderer:依 type 格式化成文字 ──
def _e_line(e):
    tag = "入圖" if e["status"] == "auto" else "待判斷"
    return f"{e['from']} {e['kind']} {e['to']}(可信度 {e['confidence']}、{e['tier']}層、出處 {e['source']}、{tag})"


def render(r):
    t = r.get("type")
    if t == "recommend":
        if not r.get("resolved"):
            return "沒抓到你讀過的作者或書,換個講法?"
        if not r["items"]:
            return f"以「{r['seed']}」為起點,鄰居都讀過了,可能要擴充來源。"
        return f"📚 你讀過「{r['seed']}」,沿知識前緣建議下一步:\n" + \
            "\n".join(f"  • {i['target']} — {i['reason']}（出處:{i['source']}）" for i in r["items"])
    if t == "provenance":
        if not r.get("resolved"):
            return "說清楚你要查哪兩者的關係,我把出處調出來。"
        if not r["found"]:
            return f"🔎 圖上目前沒有「{r['a']}」和「{r['b']}」的關係,所以我不會編一個給你。"
        blocks = []
        for e in r["edges"]:
            tag = "已入圖(可信度達標)" if e["status"] == "auto" else "⚠ 待人工判斷(尚未確認,不可當定論)"
            blocks.append(f"🔎 查核:{e['from']} {e['kind']} {e['to']}\n  主張:{e['claim']}\n"
                          f"  證據:{e['evidence'] or '(無)'}\n  出處:{e['source']}　來源層:{e['tier']}"
                          f"　可信度:{e['confidence']}\n  狀態:{tag}")
        return "\n".join(blocks)
    if t == "lineage":
        if not r.get("resolved"):
            return "沒抓到要追的概念,換個講法?"
        out = [f"🧬「{r['concept']}」的脈絡:"]
        for e in r["origin"]:
            out.append(f"  源頭:{_e_line(e)}")
        for e in r["followups"]:
            out.append(f"  後續:{_e_line(e)}")
        if len(out) == 1:
            out.append("  圖上還沒有指向它的關係。")
        return "\n".join(out)
    if t == "relation":
        if r["direct"]:
            return "🔗 有直接關係:\n" + "\n".join("  " + _e_line(e) for e in r["edges"])
        if r.get("path"):
            return "🔗 沒有直接關係,但有間接連結:" + " → ".join(r["path"])
        return f"🔗「{r['a']}」和「{r['b']}」目前在圖上還沒連起來。"
    if t == "authority":
        out = ["🏛 權威分層與權重(越上面越權威):"]
        out += [f"  {t2}:{w}" for t2, w in r["tiers"]]
        out.append("大眾/推廣型(podcast、評論平台)歸 popular、權重最低,看『現在在討論什麼』用,不當建立正典的依據。")
        for e in r["popular_examples"]:
            out.append(f"  • {e['source']}:{e['from']} {e['kind']} {e['to']}(待查證)")
        return "\n".join(out)
    if t == "path":
        return "🗓 三週入門路線(從『觀看的政治』進,循主線遞進):\n" + \
            "\n".join(f"  {w[0]}:{w[1]} —— {w[2]}" for w in r["weeks"])
    if t == "default":
        out = [f"ℹ 關於「{r['node']}」,圖上的關係:"]
        out += [f"  → {_e_line(e)}" for e in r["out"]]
        out += [f"  ← {_e_line(e)}" for e in r["in"]]
        return "\n".join(out)
    return "我沒抓到你問的是哪個人、概念或作品,可以講得具體一點。"


def answer(q):
    ids = resolve(q)
    intent = classify(q)
    return intent, ids, HANDLERS[intent](ids)


def run_test():
    data = json.loads((ROOT / "data/test_prompts.json").read_text(encoding="utf-8"))
    print("穩定性掃描:同一題的多個變體應導到相同意圖與節點\n" + "─" * 60)
    for q in data:
        print(f"\n【{q['id']}】{q['persona']}")
        seen = set()
        for v in q["variants"]:
            intent, ids, _ = answer(v)
            seen.add((intent, tuple(ids[:2])))
            print(f"  [{intent:<10}] {','.join(NAME.get(i,i) for i in ids[:2]) or '(未解析)':<14} ｜ {v[:24]}")
        print(f"  → 一致性:{'✓ 全一致' if len(seen)==1 else f'✗ {len(seen)} 種結果'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--test" in sys.argv:
        run_test()
    elif args:
        intent, ids, res = answer(" ".join(args))
        if "--json" in sys.argv:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"[意圖:{intent}　解析:{','.join(NAME.get(i,i) for i in ids[:3]) or '無'}]\n{render(res)}")
    else:
        print("用法:python3 query.py \"問句\"  /  --json \"問句\"  /  --test")
