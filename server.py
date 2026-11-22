"""server.py — sTONks Shop: регистрация, заказы менеджеру, кейсы/колесо, админ %, moveid"""
import os, re, time, random
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "@sTONks_shopuzb")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ADMIN_ID = os.getenv("ADMIN_ID", "8062748340")
FREE_CD = 24 * 3600

CONF = {
    "case_free": [{"prize": 100, "chance": 20}, {"prize": 50, "chance": 20},
                  {"prize": 25, "chance": 20}, {"prize": 0, "chance": 20}],
    "case_50":   [{"prize": 1000, "chance": 20}, {"prize": 500, "chance": 20},
                  {"prize": 200, "chance": 20}, {"prize": 150, "chance": 20},
                  {"prize": 15, "chance": 20}],
    "case_50_cost": 50,
    "wheel":     [{"prize": "NFT", "chance": 20}, {"prize": 1000, "chance": 20},
                  {"prize": 200, "chance": 20}, {"prize": 150, "chance": 20},
                  {"prize": 15, "chance": 20}],
    "wheel_cost": 50,
}

app = FastAPI(title="sTONks Shop")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {"users": {}, "meta": {}, "conf": {k: [dict(x) for x in v] if isinstance(v, list) else v for k, v in CONF.items()}}

def conn():
    if not DB_URL: return None
    try:
        import psycopg
        return psycopg.connect(DB_URL, autocommit=True)
    except Exception:
        return None

def init_db():
    c = conn()
    if not c: return
    with c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_users(
            id TEXT PRIMARY KEY, name TEXT, phone TEXT, username TEXT,
            registered BOOLEAN DEFAULT FALSE,
            stars BIGINT DEFAULT 0, free_ready_at BIGINT DEFAULT 0, updated BIGINT)""")
        cur.execute("ALTER TABLE shop_users ADD COLUMN IF NOT EXISTS name TEXT")
        cur.execute("ALTER TABLE shop_users ADD COLUMN IF NOT EXISTS phone TEXT")
        cur.execute("ALTER TABLE shop_users ADD COLUMN IF NOT EXISTS username TEXT")
        cur.execute("ALTER TABLE shop_users ADD COLUMN IF NOT EXISTS registered BOOLEAN DEFAULT FALSE")
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_meta(key TEXT PRIMARY KEY, value TEXT)""")
    c.close()

class IdIn(BaseModel): id: str
class AddIn(BaseModel): id: str; amount: int
class ProbIn(BaseModel): key: str; chances: list
class RegIn(BaseModel): id: str; phone: str = ""; name: str = "user"; username: str = ""
class OrderIn(BaseModel): id: str; product: str; comment: str = ""
class MoveIn(BaseModel): old: str; new: str

@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        print("init_db failed, MEM mode:", e)

@app.get("/")
def index(): return FileResponse("frontend/index.html")

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/shop/config")
def config():
    return {"case_free": MEM["conf"]["case_free"], "case_50": MEM["conf"]["case_50"],
            "case_50_cost": MEM["conf"]["case_50_cost"], "wheel": MEM["conf"]["wheel"],
            "wheel_cost": MEM["conf"]["wheel_cost"], "channel": CHANNEL, "free_cd": FREE_CD}

def get_meta(key):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT value FROM shop_meta WHERE key=%s", (key,))
            row = cur.fetchone()
        c.close()
        return row[0] if row else None
    return MEM["meta"].get(key)

def set_meta(key, val):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO shop_meta(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (key, val))
        c.close()
    else:
        MEM["meta"][key] = val

async def check_sub(uid: str):
    if not BOT_TOKEN: return {"subscribed": False, "error": "BOT_TOKEN не задан", "status": "?"}
    chat = CHANNEL_ID or CHANNEL
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                             params={"chat_id": chat, "user_id": int(uid)}) as r:
                d = await r.json()
        if not d.get("ok"):
            return {"subscribed": False, "error": d.get("description", "API error"), "status": "?"}
        status = d.get("result", {}).get("status", "")
        return {"subscribed": status in ("member", "administrator", "creator", "restricted"), "status": status}
    except Exception as e:
        return {"subscribed": False, "error": str(e), "status": "?"}

EMPTY_USER = {"stars": 0, "free_ready_at": 0, "registered": False, "phone": "", "username": "", "name": ""}

def get_user(uid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at, registered, phone, username, name FROM shop_users WHERE id=%s", (uid,))
            row = cur.fetchone()
        c.close()
        if row:
            return {"stars": int(row[0] or 0), "free_ready_at": int(row[1] or 0), "registered": bool(row[2]),
                    "phone": row[3] or "", "username": row[4] or "", "name": row[5] or ""}
        return None
    return MEM["users"].get(uid)

def save_user(uid, u):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO shop_users(id,name,phone,username,registered,stars,free_ready_at,updated)
                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name, phone=EXCLUDED.phone, username=EXCLUDED.username,
                           registered=EXCLUDED.registered, stars=EXCLUDED.stars, free_ready_at=EXCLUDED.free_ready_at, updated=EXCLUDED.updated""",
                        (uid, u.get("name", ""), u.get("phone", ""), u.get("username", ""), u.get("registered", False),
                         u["stars"], u["free_ready_at"], now))
        c.close()
    else:
        MEM["users"][uid] = u

@app.get("/api/shop/me")
async def me(id: str):
    u = get_user(id) or dict(EMPTY_USER)
    sub = await check_sub(id)
    now = int(time.time())
    return {"stars": u["stars"], "subscribed": sub["subscribed"], "registered": bool(u["registered"]),
            "free_in": max(0, u["free_ready_at"] - now), "sub_diag": sub}

@app.post("/api/shop/register")
def register(r: RegIn):
    u = get_user(r.id) or dict(EMPTY_USER)
    u.update(phone=r.phone, username=r.username.lstrip('@').lower(), name=r.name[:40], registered=True)
    save_user(r.id, u)
    return {"ok": True}

@app.post("/api/shop/setmanager")
def setmanager(r: IdIn, req: Request):
    if req.headers.get("X-Admin-Id") != ADMIN_ID:
        raise HTTPException(403, "admin only")
    set_meta("manager_id", r.id)
    return {"ok": True}

@app.post("/api/shop/order")
async def order(o: OrderIn):
    u = get_user(o.id)
    if not u or not u.get("registered"):
        raise HTTPException(400, "not registered")
    manager = get_meta("manager_id")
    if not manager:
        raise HTTPException(400, "manager not connected")
    now = time.strftime("%d.%m.%Y %H:%M")
    text = (f"🟢 <b>Новый заказ</b>\n\n"
            f"🛒 Товар: <b>{o.product}</b>\n"
            f"👤 От: {u.get('name', '?')} (@{u.get('username', 'без_юза')})\n"
            f"🆔 id: <code>{o.id}</code>\n"
            f"📱 Контакт: <code>{u.get('phone', 'нет')}</code>\n"
            f"💬 Комментарий: {o.comment or '—'}\n"
            f"🕐 {now}")
    async with aiohttp.ClientSession() as s:
        async with s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": int(manager), "text": text, "parse_mode": "HTML"}) as r:
            d = await r.json()
    if not d.get("ok"):
        raise HTTPException(500, d.get("description", "send failed"))
    return {"ok": True}

def roll(table):
    total = sum(x["chance"] for x in table)
    if total <= 0: return table[-1]["prize"]
    r = random.randint(1, total)
    acc = 0
    for item in table:
        acc += item["chance"]
        if r <= acc: return item["prize"]
    return table[-1]["prize"]

@app.post("/api/shop/case_free")
async def case_free(u: IdIn):
    now = int(time.time())
    user = get_user(u.id) or dict(EMPTY_USER)
    if now < user["free_ready_at"]:
        return {"ok": False, "reason": "cooldown", "wait": user["free_ready_at"] - now}
    sub = await check_sub(u.id)
    if not sub["subscribed"]:
        return {"ok": False, "reason": "not_subscribed", "diag": sub}
    prize = roll(MEM["conf"]["case_free"])
    user["stars"] += prize
    user["free_ready_at"] = now + FREE_CD
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/case_50")
def case_50(u: IdIn):
    user = get_user(u.id) or dict(EMPTY_USER)
    cost = MEM["conf"]["case_50_cost"]
    if user["stars"] < cost: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["case_50"])
    user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/wheel")
def wheel(u: IdIn):
    user = get_user(u.id) or dict(EMPTY_USER)
    cost = MEM["conf"]["wheel_cost"]
    if user["stars"] < cost: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["wheel"])
    if prize != "NFT": user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/addstars")
def addstars(a: AddIn):
    user = get_user(a.id) or dict(EMPTY_USER)
    user["stars"] = max(0, user["stars"] + a.amount)
    save_user(a.id, user)
    return {"ok": True, "stars": user["stars"]}

@app.post("/api/shop/setprob")
def setprob(p: ProbIn, r: Request):
    if r.headers.get("X-Admin-Id") != ADMIN_ID: raise HTTPException(403, "admin only")
    if p.key not in ("case_free", "case_50", "wheel"): raise HTTPException(400, "unknown key")
    table = MEM["conf"][p.key]
    if len(p.chances) != len(table): raise HTTPException(400, f"need {len(table)} values")
    for i, c in enumerate(p.chances):
        table[i]["chance"] = max(0, min(100, int(c)))
    return {"ok": True, "table": table}

@app.get("/api/shop/prob")
def prob():
    return {"case_free": MEM["conf"]["case_free"], "case_50": MEM["conf"]["case_50"], "wheel": MEM["conf"]["wheel"]}

@app.post("/api/shop/moveid")
def moveid(m: MoveIn, r: Request):
    if r.headers.get("X-Admin-Id") != ADMIN_ID: raise HTTPException(403, "admin only")
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at, registered FROM shop_users WHERE id=%s", (m.old,))
            old = cur.fetchone()
            if not old: raise HTTPException(404, "old id not found")
            cur.execute("SELECT stars FROM shop_users WHERE id=%s", (m.new,))
            if cur.fetchone():
                cur.execute("UPDATE shop_users SET stars=stars+%s, free_ready_at=GREATEST(free_ready_at,%s), registered=registered OR %s WHERE id=%s",
                            (old[0], old[1], old[2], m.new))
                cur.execute("DELETE FROM shop_users WHERE id=%s", (m.old,))
            else:
                cur.execute("UPDATE shop_users SET id=%s WHERE id=%s", (m.new, m.old))
        c.close()
    else:
        old = MEM["users"].pop(m.old, None)
        if not old: raise HTTPException(404, "old id not found")
        if m.new in MEM["users"]:
            MEM["users"][m.new]["stars"] += old["stars"]
            MEM["users"][m.new]["free_ready_at"] = max(MEM["users"][m.new]["free_ready_at"], old["free_ready_at"])
            MEM["users"][m.new]["registered"] = MEM["users"][m.new]["registered"] or old["registered"]
        else:
            MEM["users"][m.new] = old
    return {"ok": True}

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/{full_path:path}")
def fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    return FileResponse("frontend/index.html")