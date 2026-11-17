"""server.py — GRAM: регистрация (контакт+юзернейм), нули, 24h lock, адресные демо-офферы"""
import os, re, time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "8062748340")
MARKET_AGE_SEC = 24 * 3600
app = FastAPI(title="GRAM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {"users": {}, "offers": [], "next_offer": 1}
LINK_RE = re.compile(r"t\.me/nft/[A-Za-z0-9_-]+-\d+", re.I)

def conn():
    if not DB_URL:
        return None
    import psycopg
    return psycopg.connect(DB_URL, autocommit=True)

def init_db():
    c = conn()
    if not c:
        return
    with c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS gram_users(
            id TEXT PRIMARY KEY, name TEXT, phone TEXT, username TEXT,
            balance REAL DEFAULT 0, stars BIGINT DEFAULT 0,
            registered BOOLEAN DEFAULT FALSE, registered_at BIGINT DEFAULT 0, updated BIGINT)""")
        cur.execute("ALTER TABLE gram_users ADD COLUMN IF NOT EXISTS username TEXT")
        cur.execute("ALTER TABLE gram_users ADD COLUMN IF NOT EXISTS stars BIGINT DEFAULT 0")
        cur.execute("ALTER TABLE gram_users ADD COLUMN IF NOT EXISTS registered_at BIGINT DEFAULT 0")
        cur.execute("""CREATE TABLE IF NOT EXISTS gram_offers(
            id SERIAL PRIMARY KEY, to_username TEXT, gift_name TEXT, gift_num TEXT,
            price BIGINT, buyer TEXT, status TEXT DEFAULT 'new', created BIGINT)""")
    c.close()

def parse_gift(link):
    m = LINK_RE.search(link or "")
    if not m:
        return "Gift", "0"
    tail = m.group(0).split("nft/", 1)[1]
    name_part, _, num = tail.rpartition("-")
    return (name_part.replace("-", " ").title() or "Gift"), num

class Reg(BaseModel):
    id: str
    phone: str = ""
    name: str = "user"
    username: str = ""

class OfferIn(BaseModel):
    to_username: str
    gift_link: str
    price: int
    buyer: str

class AcceptIn(BaseModel):
    username: str

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def index():
    return FileResponse("frontend/index.html")

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/gram/me")
def me(id: str):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT registered, balance, stars, registered_at, username FROM gram_users WHERE id=%s", (id,))
            row = cur.fetchone()
        if not row:
            c.close()
            return {"registered": False, "balance": 0, "stars": 0, "registered_at": 0, "username": "", "market_unlocks_in": MARKET_AGE_SEC}
        reg_at = int(row[3] or 0)
        if row[0] and reg_at == 0:  # backfill: старый аккаунт без метки — ставим сейчас и держим 24h
            reg_at = now
            with c.cursor() as cur:
                cur.execute("UPDATE gram_users SET registered_at=%s, updated=%s WHERE id=%s", (now, now, id))
        c.close()
        left = max(0, MARKET_AGE_SEC - (now - reg_at)) if reg_at else MARKET_AGE_SEC
        return {"registered": bool(row[0]), "balance": float(row[1] or 0), "stars": int(row[2] or 0),
                "registered_at": reg_at, "username": row[4] or "", "market_unlocks_in": left}
    u = MEM["users"].get(id)
    if not u:
        return {"registered": False, "balance": 0, "stars": 0, "registered_at": 0, "username": "", "market_unlocks_in": MARKET_AGE_SEC}
    left = max(0, MARKET_AGE_SEC - (now - u["registered_at"])) if u["registered_at"] else MARKET_AGE_SEC
    return {"registered": bool(u.get("registered")), "balance": float(u.get("balance", 0)), "stars": int(u.get("stars", 0)),
            "registered_at": u.get("registered_at", 0), "username": u.get("username", ""), "market_unlocks_in": left}

@app.post("/api/gram/register")
def register(u: Reg):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO gram_users(id,name,phone,username,registered,balance,stars,registered_at,updated)
                           VALUES(%s,%s,%s,%s,TRUE,0,0,%s,%s)
                           ON CONFLICT(id) DO UPDATE SET phone=EXCLUDED.phone, registered=TRUE, name=EXCLUDED.name,
                           username=EXCLUDED.username, updated=EXCLUDED.updated,
                           registered_at=CASE WHEN gram_users.registered_at=0 THEN %s ELSE gram_users.registered_at END""",
                        (u.id, u.name[:40], u.phone, u.username[:32].lstrip('@').lower(), now, now, now))
        c.close()
    else:
        m = MEM["users"].setdefault(u.id, {"id": u.id, "name": u.name[:40], "balance": 0, "stars": 0})
        m.update(phone=u.phone, registered=True, name=u.name[:40], username=u.username[:32].lstrip('@').lower())
        if not m.get("registered_at"):
            m["registered_at"] = now
    return {"ok": True}

@app.get("/api/gram/offers")
def offers(username: str):
    uname = username.lstrip('@').lower()
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT id,to_username,gift_name,gift_num,price,buyer,status FROM gram_offers WHERE lower(to_username)=%s ORDER BY id DESC", (uname,))
            rows = [{"id": r[0], "to_username": r[1], "gift_name": r[2], "gift_num": r[3], "price": int(r[4]), "buyer": r[5], "status": r[6]} for r in cur.fetchall()]
        c.close()
        return {"offers": rows}
    return {"offers": [o for o in MEM["offers"] if o["to_username"] == uname]}

@app.post("/api/gram/offers")
def create_offer(o: OfferIn, r: Request):
    if r.headers.get("X-Admin-Id") != ADMIN_ID:
        raise HTTPException(403, "admin only")
    if not LINK_RE.search(o.gift_link):
        raise HTTPException(400, "bad link")
    name, num = parse_gift(o.gift_link)
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO gram_offers(to_username,gift_name,gift_num,price,buyer,status,created) VALUES(%s,%s,%s,%s,%s,'new',%s)",
                        (o.to_username.lstrip('@').lower(), name, num, o.price, o.buyer[:40], now))
        c.close()
    else:
        MEM["offers"].append({"id": MEM["next_offer"], "to_username": o.to_username.lstrip('@').lower(),
                              "gift_name": name, "gift_num": num, "price": o.price, "buyer": o.buyer[:40], "status": "new"})
        MEM["next_offer"] += 1
    return {"ok": True}

@app.post("/api/gram/offers/{oid}/accept")
def accept_offer(oid: int, a: AcceptIn):
    uname = a.username.lstrip('@').lower()
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("UPDATE gram_offers SET status='accepted' WHERE id=%s AND lower(to_username)=%s", (oid, uname))
        c.close()
    else:
        for o in MEM["offers"]:
            if o["id"] == oid and o["to_username"] == uname:
                o["status"] = "accepted"
    return {"ok": True}

app.mount("/static", StaticFiles(directory="frontend"), name="static")