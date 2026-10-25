"""原始擷取紀錄(raw fetched evidence),刻意與策展後的圖分開存,避免互相汙染。
存成純文字 JSONL:可被 git 版控、可 diff;用內容雜湊(hash)做版本與去重。
需要 SQL 查詢時,load_sqlite() 把 JSONL 載進記憶體 sqlite 查,不落地二進位檔。
右尺寸:策展後的圖(40-90 節點)留在 git 版控的 JSONL/CSV 就夠,不進 SQL;
SQL 只服務會長大的原始擷取記錄(需要去重與查詢的地方)。"""
import json, hashlib, sqlite3
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent / "data" / "captures.jsonl"


def append_capture(url, snippet, supports="", note=""):
    """新增一筆擷取;同 url+內容已存在則略過(去重)。回傳 (hash, 是否新增)。"""
    key = (url + "||" + snippet).encode("utf-8")
    h = hashlib.sha256(key).hexdigest()[:16]
    seen = set()
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(json.loads(line)["hash"])
    if h in seen:
        return h, False
    rec = {"hash": h, "url": url,
           "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "snippet": snippet, "supports": supports, "note": note}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return h, True


def load_sqlite():
    """把 captures.jsonl 載成一個可查詢的記憶體資料庫。"""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE captures(hash TEXT PRIMARY KEY, url TEXT, "
                "retrieved_at TEXT, snippet TEXT, supports TEXT, note TEXT)")
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                con.execute("INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?,?)",
                            (r["hash"], r["url"], r["retrieved_at"],
                             r["snippet"], r.get("supports", ""), r.get("note", "")))
    con.commit()
    return con


if __name__ == "__main__":
    con = load_sqlite()
    n = con.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
    print(f"captures: {n} 筆")
    for row in con.execute("SELECT retrieved_at, supports, url FROM captures "
                           "ORDER BY retrieved_at DESC LIMIT 10"):
        print(" ", row)
