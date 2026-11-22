"""server.py — sTONks Shop: программа лояльности + кейсы + колесо (админ меняет %)"""
import os, time, random
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "@sTONks_shopuzb")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")  # опционально: -100xxxxxxxxxx
ADMIN_ID = os.getenv("ADMIN_ID", "8062748340")
FREE_CD = 24 * 3600

# конфиг: по умолчанию все 20%
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
MEM = {"users": {}, "conf": {k: [dict(x) for x in v] if isinstance(v, list) else v for k, v in CONF.items()}}

def conn():
    if not DB_URL: return None
    import psycopg
    return psycopg.connect(DB_URL, autocommit=True)

def init_db():
    c = conn()
    if not c: return
    with c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_users(
            id TEXT PRIMARY KEY, stars BIGINT DEFAULT 0, free_ready_at BIGINT DEFAULT 0, updated BIGINT)""")
    c.close()

class IdIn(BaseModel): id: str
class AddIn(BaseModel): id: str; amount: int
class ProbIn(BaseModel): key: str; chances: list  # e.g. key="case_free", chances=[25,25,25,25]

@app.on_event("startup")
def startup(): init_db()

@app.get("/")
def index(): return FileResponse("frontend/index.html")

@app.get("/api/shop/config")
def config():
    return {
        "case_free": MEM["conf"]["case_free"],
        "case_50": MEM["conf"]["case_50"],
        "case_50_cost": MEM["conf"]["case_50_cost"],
        "wheel": MEM["conf"]["wheel"],
        "wheel_cost": MEM["conf"]["wheel_cost"],
        "channel": CHANNEL,
        "free_cd": FREE_CD,
    }

async def check_sub(uid: str):
    """Проверка подписки с правильной диагностикой"""
    if not BOT_TOKEN: return {"subscribed": False, "error": "BOT_TOKEN не задан"}
    chat = CHANNEL_ID or CHANNEL
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                             params={"chat_id": chat, "user_id": int(uid)}) as r:
                d = await r.json()
        if "ok" not in d or not d.get("ok"):
            return {"subscribed": False, "error": d.get("description", "API error"), "raw": d}
        res = d.get("result", {})
        status = res.get("status", "")
        # "creator", "administrator", "member" = подписан
        # "restricted" = подписан с ограничениями (тоже подписан)
        # "left", "kicked" = не подписан
        subscribed = status in ("member", "administrator", "creator", "restricted")
        return {"subscribed": subscribed, "status": status, "raw": res}
    except Exception as e:
        return {"subscribed": False, "error": str(e)}

def get_user(uid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at FROM shop_users WHERE id=%s", (uid,))
            row = cur.fetchone()
        c.close()
        if row: return {"stars": int(row[0] or 0), "free_ready_at": int(row[1] or 0)}
        return None
    return MEM["users"].get(uid)

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
        MEM["users"][uid] = u

@app.get("/api/shop/me")
async def me(id: str):
    u = get_user(id) or {"stars": 0, "free_ready_at": 0}
    sub = await check_sub(id)
    now = int(time.time())
    return {"stars": u["stars"], "subscribed": sub["subscribed"],
            "free_in": max(0, u["free_ready_at"] - now),
            "sub_diag": sub}

def roll(table):
    total = sum(x["chance"] for x in table)
    if total <= 0:
        return table[-1]["prize"]
    r = random.randint(1, total)
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
    user = get_user(u.id) or {"stars": 0, "free_ready_at": 0}
    cost = MEM["conf"]["case_50_cost"]
    if user["stars"] < cost:
        return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["case_50"])
    user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/wheel")
def wheel(u: IdIn):
    user = get_user(u.id) or {"stars": 0, "free_ready_at": 0}
    cost = MEM["conf"]["wheel_cost"]
    if user["stars"] < cost:
        return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["wheel"])
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

@app.post("/api/shop/setprob")
def setprob(p: ProbIn, r: Request):
    if r.headers.get("X-Admin-Id") != ADMIN_ID:
        raise HTTPException(403, "admin only")
    if p.key not in ("case_free", "case_50", "wheel"):
        raise HTTPException(400, "unknown key")
    table = MEM["conf"][p.key]
    if len(p.chances) != len(table):
        raise HTTPException(400, f"need {len(table)} values, got {len(p.chances)}")
    for i, c in enumerate(p.chances):
        table[i]["chance"] = max(0, min(100, int(c)))
    return {"ok": True, "table": table}

@app.get("/api/shop/prob")
def prob():
    return {"case_free": MEM["conf"]["case_free"],
            "case_50": MEM["conf"]["case_50"],
            "wheel": MEM["conf"]["wheel"]}

app.mount("/static", StaticFiles(directory="frontend"), name="static")