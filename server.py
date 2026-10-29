"""server.py — ВОЛК ТАП: статика, топ, персы с ценой, разблокировки, регистрация"""
import os, time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_SECRET = "wolftap2026secret"
app = FastAPI(title="WolfTap")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {"users": {}, "chars": [], "next_char": 1, "unlocks": {}}

def conn():
    if not DB_URL:
        return None
    import psycopg
    return psycopg.connect(DB_URL, autocommit=True)

def check_secret(r: Request):
    if r.headers.get("X-Admin-Secret") != ADMIN_SECRET:
        raise HTTPException(403, "no")

def init_db():
    c = conn()
    if not c:
        return
    with c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS wolves(
            id TEXT PRIMARY KEY, name TEXT, balance BIGINT DEFAULT 0, taps BIGINT DEFAULT 0,
            phone TEXT, registered BOOLEAN DEFAULT FALSE, updated BIGINT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS chars(
            id SERIAL PRIMARY KEY, name TEXT, mult REAL DEFAULT 1, image TEXT DEFAULT '',
            price BIGINT DEFAULT 0, cur TEXT DEFAULT 'taps', active BOOLEAN DEFAULT TRUE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS char_unlocks(
            id TEXT, char_id INT, PRIMARY KEY(id, char_id))""")
        cur.execute("ALTER TABLE wolves ADD COLUMN IF NOT EXISTS phone TEXT")
        cur.execute("ALTER TABLE wolves ADD COLUMN IF NOT EXISTS registered BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE chars ADD COLUMN IF NOT EXISTS image TEXT DEFAULT ''")
        cur.execute("ALTER TABLE chars ADD COLUMN IF NOT EXISTS price BIGINT DEFAULT 0")
        cur.execute("ALTER TABLE chars ADD COLUMN IF NOT EXISTS cur TEXT DEFAULT 'taps')".replace("')", "'"))
    c.close()

class Sync(BaseModel):
    id: str
    name: str = "волк-аноним"
    balance: int = 0
    taps: int = 0

class Reg(BaseModel):
    id: str
    phone: str = ""
    name: str = "волк"

class CharIn(BaseModel):
    name: str
    mult: float = 1.0
    image: str = ""
    price: int = 0
    cur: str = "taps"

class UnlockIn(BaseModel):
    id: str
    char_id: int

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def index():
    return FileResponse("frontend/index.html")

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/me")
def me(id: str):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT registered FROM wolves WHERE id=%s", (id,))
            row = cur.fetchone()
        c.close()
        return {"registered": bool(row and row[0])}
    u = MEM["users"].get(id)
    return {"registered": bool(u and u.get("registered"))}

@app.post("/api/register")
def register(u: Reg):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO wolves(id,name,phone,registered,updated) VALUES(%s,%s,%s,TRUE,%s)
                ON CONFLICT(id) DO UPDATE SET phone=EXCLUDED.phone, registered=TRUE, name=EXCLUDED.name, updated=EXCLUDED.updated""",
                        (u.id, u.name[:40], u.phone, now))
        c.close()
    else:
        m = MEM["users"].setdefault(u.id, {"id": u.id, "name": u.name[:40], "balance": 0, "taps": 0})
        m.update(phone=u.phone, registered=True, name=u.name[:40])
    return {"ok": True}

@app.post("/api/sync")
def sync(u: Sync):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO wolves(id,name,balance,taps,updated) VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name, balance=EXCLUDED.balance, taps=EXCLUDED.taps, updated=EXCLUDED.updated""",
                        (u.id, u.name[:40], u.balance, u.taps, now))
        c.close()
    else:
        m = MEM["users"].setdefault(u.id, {"id": u.id, "name": u.name[:40], "balance": 0, "taps": 0})
        m.update(name=u.name[:40], balance=u.balance, taps=u.taps)
    return {"ok": True}

@app.get("/api/top")
def top(limit: int = 50):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT id,name,balance FROM wolves ORDER BY balance DESC LIMIT %s", (limit,))
            rows = [{"id": r[0], "name": r[1], "balance": int(r[2])} for r in cur.fetchall()]
        c.close()
        return {"users": rows}
    return {"users": sorted(MEM["users"].values(), key=lambda x: -x["balance"])[:limit]}

@app.get("/api/chars")
def chars():
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT id,name,mult,image,price,cur FROM chars WHERE active ORDER BY id")
            rows = [{"id": r[0], "name": r[1], "mult": r[2], "image": r[3] or "", "price": int(r[4] or 0), "cur": r[5] or 'taps'} for r in cur.fetchall()]
        c.close()
        return {"chars": rows}
    return {"chars": [x for x in MEM["chars"] if x["active"]]}

@app.get("/api/unlocks")
def unlocks(id: str):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT char_id FROM char_unlocks WHERE id=%s", (id,))
            rows = [r[0] for r in cur.fetchall()]
        c.close()
        return {"unlocks": rows}
    return {"unlocks": MEM["unlocks"].get(id, [])}

@app.post("/api/unlock")
def unlock(u: UnlockIn):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT price,cur,active FROM chars WHERE id=%s", (u.char_id,))
            ch = cur.fetchone()
            if not ch or not ch[2]:
                raise HTTPException(404, "char")
            price, curr = int(ch[0] or 0), ch[1] or 'taps'
            cur.execute("SELECT taps,balance FROM wolves WHERE id=%s", (u.id,))
            w = cur.fetchone()
            if not w:
                raise HTTPException(404, "user")
            taps, balance = int(w[0] or 0), int(w[1] or 0)
            if curr == 'taps':
                if taps < price:
                    raise HTTPException(400, "need more taps")
            else:
                if balance < price:
                    raise HTTPException(400, "need more balance")
                cur.execute("UPDATE wolves SET balance=balance-%s WHERE id=%s", (price, u.id))
                balance -= price
            cur.execute("INSERT INTO char_unlocks(id,char_id) VALUES(%s,%s) ON CONFLICT DO NOTHING", (u.id, u.char_id))
        c.close()
        return {"ok": True, "balance": balance}
    ch = next((x for x in MEM["chars"] if x["id"] == u.char_id and x["active"]), None)
    if not ch:
        raise HTTPException(404, "char")
    m = MEM["users"].get(u.id)
    if not m:
        raise HTTPException(404, "user")
    if ch["cur"] == 'taps':
        if m.get("taps", 0) < ch["price"]:
            raise HTTPException(400, "need more taps")
    else:
        if m.get("balance", 0) < ch["price"]:
            raise HTTPException(400, "need more balance")
        m["balance"] -= ch["price"]
    MEM["unlocks"].setdefault(u.id, [])
    if u.char_id not in MEM["unlocks"][u.id]:
        MEM["unlocks"][u.id].append(u.char_id)
    return {"ok": True, "balance": m["balance"]}

@app.get("/api/admin/chars")
def admin_chars(r: Request):
    check_secret(r)
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT id,name,mult,image,price,cur,active FROM chars ORDER BY id")
            rows = [{"id": r0[0], "name": r0[1], "mult": r0[2], "image": r0[3] or "", "price": int(r0[4] or 0), "cur": r0[5] or 'taps', "active": r0[6]} for r0 in cur.fetchall()]
        c.close()
        return {"chars": rows}
    return {"chars": MEM["chars"]}

@app.post("/api/admin/chars")
def add_char(ch: CharIn, r: Request):
    check_secret(r)
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO chars(name,mult,image,price,cur) VALUES(%s,%s,%s,%s,%s)",
                        (ch.name[:20], ch.mult, ch.image, ch.price, ch.cur))
        c.close()
    else:
        MEM["chars"].append({"id": MEM["next_char"], "name": ch.name[:20], "mult": ch.mult,
                             "image": ch.image, "price": ch.price, "cur": ch.cur, "active": True})
        MEM["next_char"] += 1
    return {"ok": True}

@app.post("/api/admin/chars/{cid}/delete")
def del_char(cid: int, r: Request):
    check_secret(r)
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("UPDATE chars SET active=FALSE WHERE id=%s", (cid,))
        c.close()
    else:
        for x in MEM["chars"]:
            if x["id"] == cid:
                x["active"] = False
    return {"ok": True}

@app.get("/api/admin/users")
def admin_users(r: Request):
    check_secret(r)
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT id,name FROM wolves WHERE registered")
            rows = [{"id": r0[0], "name": r0[1]} for r0 in cur.fetchall()]
        c.close()
        return {"users": rows}
    return {"users": [u for u in MEM["users"].values() if u.get("registered")]}

@app.get("/api/admin/stats")
def admin_stats(r: Request):
    check_secret(r)
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE registered), COALESCE(SUM(taps),0), COALESCE(SUM(balance),0) FROM wolves")
            row = cur.fetchone()
        c.close()
        return {"users": row[0], "registered": row[1], "taps": int(row[2]), "balance": int(row[3])}
    us = list(MEM["users"].values())
    return {"users": len(us), "registered": sum(1 for u in us if u.get("registered")),
            "taps": sum(u.get("taps", 0) for u in us), "balance": sum(u.get("balance", 0) for u in us)}

app.mount("/static", StaticFiles(directory="frontend"), name="static")