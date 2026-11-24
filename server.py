"""server.py — sTONks Shop: кейс 300, честные шансы, промокоды, пополнение, менеджер-стафф"""
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
POINTS_PER_STAR = 100

CONF = {
    "case_free": [{"prize": 100, "chance": 0}, {"prize": 50, "chance": 1},
                  {"prize": 25, "chance": 1}, {"prize": 0, "chance": 98}],
    "case_paid": [{"prize": 1000, "chance": 1}, {"prize": 500, "chance": 0},
                  {"prize": 200, "chance": 0}, {"prize": 150, "chance": 0},
                  {"prize": 25, "chance": 49}, {"prize": 15, "chance": 50}],
    "case_paid_cost": 300,
    "wheel":     [{"prize": "NFT", "chance": 0}, {"prize": 1000, "chance": 1},
                  {"prize": 200, "chance": 0}, {"prize": 150, "chance": 0},
                  {"prize": 15, "chance": 99}],
    "wheel_cost": 50,
}

app = FastAPI(title="sTONks Shop")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {"users": {}, "meta": {}, "promos": {}, "redemptions": set(),
       "conf": {k: [dict(x) for x in v] if isinstance(v, list) else v for k, v in CONF.items()}}

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
        for col in ("name TEXT", "phone TEXT", "username TEXT", "registered BOOLEAN DEFAULT FALSE"):
            cur.execute(f"ALTER TABLE shop_users ADD COLUMN IF NOT EXISTS {col}")
        cur.execute("CREATE TABLE IF NOT EXISTS shop_meta(key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_promos(
            code TEXT PRIMARY KEY, reward BIGINT, max_uses INT, uses INT DEFAULT 0)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_redemptions(
            code TEXT, user_id TEXT, PRIMARY KEY(code, user_id))""")
    c.close()

class IdIn(BaseModel): id: str
class AddIn(BaseModel): id: str; amount: int
class ProbIn(BaseModel): key: str; chances: list
class RegIn(BaseModel): id: str; phone: str = ""; name: str = "user"; username: str = ""
class OrderIn(BaseModel): id: str; product: str; options: str = ""; comment: str = ""
class MoveIn(BaseModel): old: str; new: str
class PromoIn(BaseModel): id: str; code: str
class PromoCreate(BaseModel): code: str; reward: int; max_uses: int

@app.on_event("startup")
def startup():
    try: init_db()
    except Exception as e: print("init_db failed, MEM mode:", e)

@app.get("/")
def index(): return FileResponse("frontend/index.html")

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/shop/config")
def config():
    c = MEM["conf"]
    return {"case_free": c["case_free"], "case_paid": c["case_paid"],
            "case_paid_cost": c["case_paid_cost"], "wheel": c["wheel"],
            "wheel_cost": c["wheel_cost"], "channel": CHANNEL, "free_cd": FREE_CD,
            "points_per_star": POINTS_PER_STAR}

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

def is_staff(req: Request):
    if req.headers.get("X-Admin-Id") == ADMIN_ID: return True
    sid = req.headers.get("X-Staff-Id")
    return bool(sid) and sid == get_meta("manager_id")

async def check_sub(uid: str):
    if not BOT_TOKEN: return {"subscribed": False, "error": "no token", "status": "?"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                             params={"chat_id": CHANNEL_ID or CHANNEL, "user_id": int(uid)}) as r:
                d = await r.json()
        if not d.get("ok"):
            return {"subscribed": False, "error": d.get("description", "api"), "status": "?"}
        st = d.get("result", {}).get("status", "")
        return {"subscribed": st in ("member", "administrator", "creator", "restricted"), "status": st}
    except Exception as e:
        return {"subscribed": False, "error": str(e), "status": "?"}

EMPTY = {"stars": 0, "free_ready_at": 0, "registered": False, "phone": "", "username": "", "name": ""}

def get_user(uid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at, registered, phone, username, name FROM shop_users WHERE id=%s", (uid,))
            r = cur.fetchone()
        c.close()
        if r: return {"stars": int(r[0] or 0), "free_ready_at": int(r[1] or 0), "registered": bool(r[2]),
                      "phone": r[3] or "", "username": r[4] or "", "name": r[5] or ""}
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
                (uid, u.get("name",""), u.get("phone",""), u.get("username",""), u.get("registered",False), u["stars"], u["free_ready_at"], now))
        c.close()
    else:
        MEM["users"][uid] = u

@app.get("/api/shop/me")
async def me(id: str):
    u = get_user(id) or dict(EMPTY)
    sub = await check_sub(id)
    now = int(time.time())
    return {"stars": u["stars"], "subscribed": sub["subscribed"], "registered": bool(u["registered"]),
            "free_in": max(0, u["free_ready_at"] - now), "sub_diag": sub,
            "is_staff": id == ADMIN_ID or id == get_meta("manager_id")}

@app.post("/api/shop/register")
def register(r: RegIn):
    u = get_user(r.id) or dict(EMPTY)
    u.update(phone=r.phone, username=r.username.lstrip('@').lower(), name=r.name[:40], registered=True)
    save_user(r.id, u)
    return {"ok": True}

@app.post("/api/shop/setmanager")
def setmanager(r: IdIn, req: Request):
    if req.headers.get("X-Admin-Id") != ADMIN_ID: raise HTTPException(403, "admin only")
    set_meta("manager_id", r.id)
    return {"ok": True}

@app.get("/api/shop/manager")
def manager():
    return {"id": get_meta("manager_id") or ""}

@app.post("/api/shop/order")
async def order(o: OrderIn):
    u = get_user(o.id)
    if not u or not u.get("registered"): raise HTTPException(400, "not registered")
    mgr = get_meta("manager_id")
    if not mgr: raise HTTPException(400, "manager not connected")
    text = (f"🟢 <b>Новый заказ</b>\n\n🛒 Товар: <b>{o.product}</b>\n"
            f"⚙️ Параметры: {o.options or '—'}\n"
            f"👤 От: {u.get('name','?')} (@{u.get('username','без_юза')})\n"
            f"🆔 id: <code>{o.id}</code>\n📱 Контакт: <code>{u.get('phone','нет')}</code>\n"
            f"💬 Комментарий: {o.comment or '—'}\n🕐 {time.strftime('%d.%m.%Y %H:%M')}")
    async with aiohttp.ClientSession() as s:
        async with s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": int(mgr), "text": text, "parse_mode": "HTML"}) as r:
            d = await r.json()
    if not d.get("ok"): raise HTTPException(500, d.get("description", "send failed"))
    return {"ok": True}

def normalize(table):
    tot = sum(x["chance"] for x in table)
    if tot <= 0:
        table[-1]["chance"] = 100
        return table
    if tot != 100:
        acc = 0
        for i, x in enumerate(table):
            if i == len(table) - 1:
                x["chance"] = max(0, 100 - acc)
            else:
                x["chance"] = round(x["chance"] * 100 / tot)
                acc += x["chance"]
    return table

def roll(table):
    r = random.randint(1, 100)
    acc = 0
    for it in table:
        acc += it["chance"]
        if r <= acc: return it["prize"]
    return table[-1]["prize"]

@app.post("/api/shop/case_free")
async def case_free(u: IdIn):
    now = int(time.time())
    user = get_user(u.id) or dict(EMPTY)
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

@app.post("/api/shop/case_paid")
def case_paid(u: IdIn):
    user = get_user(u.id) or dict(EMPTY)
    cost = MEM["conf"]["case_paid_cost"]
    if user["stars"] < cost: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["case_paid"])
    user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/wheel")
def wheel(u: IdIn):
    user = get_user(u.id) or dict(EMPTY)
    cost = MEM["conf"]["wheel_cost"]
    if user["stars"] < cost: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["wheel"])
    if prize != "NFT": user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/addstars")
def addstars(a: AddIn, req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    user = get_user(a.id) or dict(EMPTY)
    user["stars"] = max(0, user["stars"] + a.amount)
    save_user(a.id, user)
    return {"ok": True, "stars": user["stars"]}

@app.post("/api/shop/setprob")
def setprob(p: ProbIn, req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    if p.key not in ("case_free", "case_paid", "wheel"): raise HTTPException(400, "unknown key")
    t = MEM["conf"][p.key]
    if len(p.chances) != len(t): raise HTTPException(400, f"need {len(t)} values")
    for i, c in enumerate(p.chances): t[i]["chance"] = max(0, int(c))
    normalize(t)
    return {"ok": True, "table": t}

@app.get("/api/shop/prob")
def prob():
    return {k: MEM["conf"][k] for k in ("case_free", "case_paid", "wheel")}

@app.post("/api/shop/moveid")
def moveid(m: MoveIn, req: Request):
    if req.headers.get("X-Admin-Id") != ADMIN_ID: raise HTTPException(403, "admin only")
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT stars, free_ready_at, registered FROM shop_users WHERE id=%s", (m.old,))
            old = cur.fetchone()
            if not old: raise HTTPException(404, "old id not found")
            cur.execute("SELECT stars FROM shop_users WHERE id=%s", (m.new,))
            if cur.fetchone():
                cur.execute("UPDATE shop_users SET stars=stars+%s, free_ready_at=GREATEST(free_ready_at,%s), registered=registered OR %s WHERE id=%s", (old[0], old[1], old[2], m.new))
                cur.execute("DELETE FROM shop_users WHERE id=%s", (m.old,))
            else:
                cur.execute("UPDATE shop_users SET id=%s WHERE id=%s", (m.new, m.old))
        c.close()
    else:
        old = MEM["users"].pop(m.old, None)
        if not old: raise HTTPException(404, "old id not found")
        if m.new in MEM["users"]:
            MEM["users"][m.new]["stars"] += old["stars"]
        else:
            MEM["users"][m.new] = old
    return {"ok": True}

# ===== ПРОМОКОДЫ =====
def get_promo(code):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT reward, max_uses, uses FROM shop_promos WHERE code=%s", (code,))
            r = cur.fetchone()
        c.close()
        return {"reward": int(r[0]), "max_uses": int(r[1]), "uses": int(r[2])} if r else None
    return MEM["promos"].get(code)

@app.post("/api/shop/promo_create")
def promo_create(p: PromoCreate, req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    code = p.code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,24}", code): raise HTTPException(400, "bad code")
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO shop_promos(code,reward,max_uses,uses) VALUES(%s,%s,%s,0) ON CONFLICT(code) DO UPDATE SET reward=EXCLUDED.reward, max_uses=EXCLUDED.max_uses", (code, p.reward, p.max_uses))
        c.close()
    else:
        MEM["promos"][code] = {"reward": p.reward, "max_uses": p.max_uses, "uses": MEM["promos"].get(code, {}).get("uses", 0)}
    return {"ok": True, "code": code}

@app.get("/api/shop/promo_list")
def promo_list(req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT code, reward, max_uses, uses FROM shop_promos ORDER BY code")
            rows = [{"code": r[0], "reward": int(r[1]), "max_uses": int(r[2]), "uses": int(r[3])} for r in cur.fetchall()]
        c.close()
        return {"promos": rows}
    return {"promos": [{"code": k, **v} for k, v in MEM["promos"].items()]}

@app.post("/api/shop/promo")
def promo_activate(p: PromoIn):
    u = get_user(p.id)
    if not u or not u.get("registered"): raise HTTPException(400, "not registered")
    code = p.code.strip().upper()
    pr = get_promo(code)
    if not pr: raise HTTPException(404, "promo not found")
    if pr["uses"] >= pr["max_uses"]: raise HTTPException(400, "promo exhausted")
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT 1 FROM shop_redemptions WHERE code=%s AND user_id=%s", (code, p.id))
            if cur.fetchone(): raise HTTPException(400, "already used")
            cur.execute("UPDATE shop_promos SET uses=uses+1 WHERE code=%s AND uses<max_uses", (code,))
            cur.execute("INSERT INTO shop_redemptions(code,user_id) VALUES(%s,%s)", (code, p.id))
        c.close()
    else:
        if (code, p.id) in MEM["redemptions"]: raise HTTPException(400, "already used")
        MEM["redemptions"].add((code, p.id))
        pr["uses"] += 1
    u["stars"] += pr["reward"]
    save_user(p.id, u)
    return {"ok": True, "reward": pr["reward"], "stars": u["stars"]}

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/{full_path:path}")
def fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(404)
    return FileResponse("frontend/index.html")