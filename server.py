"""server.py — sTONks Shop: витрина + кейсы + колесо (ДЕМО-звёзды, честные шансы)"""
import os, time, random
import aiohttp
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "@sTONks_shopuzb")
FREE_CD = 24 * 3600

# конфиг призов: (приз, шанс %) — шансы ПОКАЗЫВАЮТСЯ пользователю как есть
CASE_FREE = [{"prize": 100, "chance": 0}, {"prize": 50, "chance": 1},
             {"prize": 25, "chance": 1}, {"prize": 0, "chance": 98}]
CASE_50 = [{"prize": 1000, "chance": 0}, {"prize": 500, "chance": 0},
           {"prize": 200, "chance": 1}, {"prize": 150, "chance": 1},
           {"prize": 15, "chance": 98}]
CASE_50_COST = 50
WHEEL = [{"prize": "NFT", "chance": 0}, {"prize": 1000, "chance": 0},
         {"prize": 200, "chance": 1}, {"prize": 150, "chance": 1},
         {"prize": 15, "chance": 98}]
WHEEL_COST = 50

app = FastAPI(title="sTONks Shop")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {}

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
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_users(
            id TEXT PRIMARY KEY, stars BIGINT DEFAULT 0, free_ready_at BIGINT DEFAULT 0, updated BIGINT)""")
    c.close()

class IdIn(BaseModel):
    id: str

class AddIn(BaseModel):
    id: str
    amount: int

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def index():
    return FileResponse("frontend/index.html")

@app.get("/api/shop/config")
def config():
    return {"case_free": CASE_FREE, "case_50": CASE_50, "case_50_cost": CASE_50_COST,
            "wheel": WHEEL, "wheel_cost": WHEEL_COST, "channel": CHANNEL, "free_cd": FREE_CD}

def get_user(uid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at FROM shop_users WHERE id=%s", (uid,))
            row = cur.fetchone()
        c.close()
        if row:
            return {"stars": int(row[0] or 0), "free_ready_at": int(row[1] or 0)}
        return None
    return MEM.get(uid)

def save_user(uid, u):
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO shop_users(id,stars,free_ready_at,updated) VALUES(%s,%s,%s,%s)
                           ON CONFLICT(id) DO UPDATE SET stars=EXCLUDED.stars, free_ready_at=EXCLUDED.free_ready_at, updated=EXCLUDED.updated""",
                        (uid, u["stars"], u["free_ready_at"], now))
        c.close()
    else:
        MEM[uid] = u

@app.get("/api/shop/me")
async def me(id: str):
    u = get_user(id) or {"stars": 0, "free_ready_at": 0}
    sub = False
    if BOT_TOKEN:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                                 params={"chat_id": CHANNEL, "user_id": int(id)}) as r:
                    d = await r.json()
            sub = d.get("result", {}).get("status") in ("member", "administrator", "creator")
        except Exception:
            sub = False
    now = int(time.time())
    return {"stars": u["stars"], "subscribed": sub,
            "free_in": max(0, u["free_ready_at"] - now)}

def roll(table):
    r = random.randint(1, 100)
    acc = 0
    for item in table:
        acc += item["chance"]
        if r <= acc:
            return item["prize"]
    return table[-1]["prize"]

@app.post("/api/shop/case_free")
async def case_free(u: IdIn):
    now = int(time.time())
    user = get_user(u.id) or {"stars": 0, "free_ready_at": 0}
    if now < user["free_ready_at"]:
        return {"ok": False, "reason": "cooldown", "wait": user["free_ready_at"] - now}
    if BOT_TOKEN:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                                 params={"chat_id": CHANNEL, "user_id": int(u.id)}) as r:
                    d = await r.json()
            if d.get("result", {}).get("status") not in ("member", "administrator", "creator"):
                return {"ok": False, "reason": "not_subscribed"}
        except Exception:
            return {"ok": False, "reason": "not_subscribed"}
    prize = roll(CASE_FREE)
    user["stars"] += prize
    user["free_ready_at"] = now + FREE_CD
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/case_50")
def case_50(u: IdIn):
    user = get_user(u.id) or {"stars": 0, "free_ready_at": 0}
    if user["stars"] < CASE_50_COST:
        return {"ok": False, "reason": "no_stars"}
    user["stars"] -= CASE_50_COST
    prize = roll(CASE_50)
    user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/wheel")
def wheel(u: IdIn):
    user = get_user(u.id) or {"stars": 0, "free_ready_at": 0}
    if user["stars"] < WHEEL_COST:
        return {"ok": False, "reason": "no_stars"}
    user["stars"] -= WHEEL_COST
    prize = roll(WHEEL)
    if prize != "NFT":
        user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/addstars")
def addstars(a: AddIn):
    user = get_user(a.id) or {"stars": 0, "free_ready_at": 0}
    user["stars"] = max(0, user["stars"] + a.amount)
    save_user(a.id, user)
    return {"ok": True, "stars": user["stars"]}

app.mount("/static", StaticFiles(directory="frontend"), name="static")