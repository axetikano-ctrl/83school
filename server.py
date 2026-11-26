"""server.py — sTONks Shop: магазин, игры + Ракета (crash), промо, заказы, баннеры"""
import os, re, time, math, random, uuid
from pathlib import Path
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "@sTONks_shopuzb")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ADMIN_ID = os.getenv("ADMIN_ID", "8062748340")
FREE_CD = 24 * 3600
POINTS_PER_STAR = 100
HOUSE = 0.97
WIN_ONE_IN = 6
UP_BASE_PER = 100.0 / 18.0
ROCKET_RATE = 0.16
ROCKET_CAP = 200.0
INDEX = Path("frontend/index.html")

CONF = {
    "case_free": [{"prize": 100, "chance": 1}, {"prize": 50, "chance": 1},
                  {"prize": 25, "chance": 1}, {"prize": 0, "chance": 97}],
    "case_paid": [{"prize": 1000, "chance": 1}, {"prize": 500, "chance": 1},
                  {"prize": 200, "chance": 1}, {"prize": 150, "chance": 1},
                  {"prize": 25, "chance": 46}, {"prize": 15, "chance": 50}],
    "case_paid_cost": 300,
    "wheel":     [{"prize": "NFT", "chance": 1}, {"prize": 1000, "chance": 1},
                  {"prize": 200, "chance": 1}, {"prize": 150, "chance": 1},
                  {"prize": 15, "chance": 96}],
    "wheel_cost": 50,
    "upgrader_mults": [1.5, 2, 5, 10],
}

def up_chance(mult):
    return max(1, round(UP_BASE_PER * 2.0 / mult))

def rocket_growth(t):
    return math.exp(ROCKET_RATE * max(0.0, t))

def rocket_crash_point():
    u = random.random()
    if u < 0.01: return 1.0
    return round(min(0.97 / (1 - u), ROCKET_CAP), 2)

app = FastAPI(title="sTONks Shop")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MEM = {"users": {}, "meta": {}, "promos": {}, "redemptions": set(), "mines": {}, "rocket": {},
       "conf": {k: ([dict(x) for x in v] if isinstance(v, list) and v and isinstance(v[0], dict) else v) for k, v in CONF.items()}}

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
        cur.execute("CREATE TABLE IF NOT EXISTS shop_promos(code TEXT PRIMARY KEY, reward BIGINT, max_uses INT, uses INT DEFAULT 0)")
        cur.execute("CREATE TABLE IF NOT EXISTS shop_redemptions(code TEXT, user_id TEXT, PRIMARY KEY(code, user_id))")
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_mines(
            gid TEXT PRIMARY KEY, uid TEXT, bet BIGINT, mines TEXT, picks TEXT, state TEXT, created BIGINT)""")
        cur.execute("ALTER TABLE shop_mines ADD COLUMN IF NOT EXISTS win BOOLEAN DEFAULT FALSE")
        cur.execute("""CREATE TABLE IF NOT EXISTS shop_rocket(
            gid TEXT PRIMARY KEY, uid TEXT, bet BIGINT, crash DOUBLE PRECISION, t0 DOUBLE PRECISION,
            state TEXT, cash_mult DOUBLE PRECISION, payout BIGINT)""")
    c.close()

class IdIn(BaseModel): id: str
class AddIn(BaseModel): id: str; amount: int
class ProbIn(BaseModel): key: str; chances: list
class RegIn(BaseModel): id: str; phone: str = ""; name: str = "user"; username: str = ""
class OrderIn(BaseModel): id: str; product: str; options: str = ""; comment: str = ""
class MoveIn(BaseModel): old: str; new: str
class PromoIn(BaseModel): id: str; code: str
class PromoCreate(BaseModel): code: str; reward: int; max_uses: int
class UpIn(BaseModel): id: str; stake: int; mult: float
class MinesStart(BaseModel): id: str; bet: int; mines: int
class MinesCell(BaseModel): id: str; gid: str; cell: int
class MinesCash(BaseModel): id: str; gid: str
class RocketStart(BaseModel): id: str; bet: int
class RocketCtl(BaseModel): id: str; gid: str
class ResetAll(BaseModel): confirm: bool = False

@app.on_event("startup")
def startup():
    try: init_db()
    except Exception as e: print("init_db failed, MEM mode:", e)

def serve_index():
    html = INDEX.read_text(encoding="utf-8")
    if "banners.js" not in html:
        html = html.replace("</body>", '<script src="/static/banners.js?v=14"></script></body>')
    return HTMLResponse(html)

@app.get("/")
def index(): return serve_index()

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/shop/config")
def config():
    c = MEM["conf"]
    return {"case_free": c["case_free"], "case_paid": c["case_paid"], "case_paid_cost": c["case_paid_cost"],
            "wheel": c["wheel"], "wheel_cost": c["wheel_cost"], "upgrader_mults": c["upgrader_mults"],
            "channel": CHANNEL, "free_cd": FREE_CD, "points_per_star": POINTS_PER_STAR}

def get_meta(key):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT value FROM shop_meta WHERE key=%s", (key,))
            r = cur.fetchone()
        c.close()
        return r[0] if r else None
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
    if not BOT_TOKEN: return {"subscribed": False, "status": "?"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                             params={"chat_id": CHANNEL_ID or CHANNEL, "user_id": int(uid)}) as r:
                d = await r.json()
        if not d.get("ok"): return {"subscribed": False, "status": "?"}
        st = d.get("result", {}).get("status", "")
        return {"subscribed": st in ("member", "administrator", "creator", "restricted"), "status": st}
    except Exception:
        return {"subscribed": False, "status": "?"}

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
def manager(): return {"id": get_meta("manager_id") or ""}

@app.post("/api/shop/order")
async def order(o: OrderIn):
    u = get_user(o.id)
    if not u or not u.get("registered"): raise HTTPException(400, "not registered")
    mgr = get_meta("manager_id")
    if not mgr: raise HTTPException(400, "manager not connected")
    text = (f"🟢 <b>Новый заказ</b>\n\n🛒 Товар: <b>{o.product}</b>\n⚙️ Параметры: {o.options or '—'}\n"
            f"👤 От: {u.get('name','?')} (@{u.get('username','без_юза')})\n🆔 id: <code>{o.id}</code>\n"
            f"📱 Контакт: <code>{u.get('phone','нет')}</code>\n💬 Комментарий: {o.comment or '—'}\n"
            f"🕐 {time.strftime('%d.%m.%Y %H:%M')}")
    async with aiohttp.ClientSession() as s:
        async with s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": int(mgr), "text": text, "parse_mode": "HTML"}) as r:
            d = await r.json()
    if not d.get("ok"): raise HTTPException(500, d.get("description", "send failed"))
    return {"ok": True}

@app.post("/api/shop/resetall")
def resetall(r: ResetAll, req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    if not r.confirm: raise HTTPException(400, "need confirm")
    now = int(time.time())
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("UPDATE shop_users SET stars=0, updated=%s", (now,))
            n = cur.rowcount
        c.close()
    else:
        for u in MEM["users"].values(): u["stars"] = 0
        n = len(MEM["users"])
    return {"ok": True, "reset": n}

@app.post("/api/shop/resetone")
def resetone(r: IdIn, req: Request):
    if not is_staff(req): raise HTTPException(403, "staff only")
    u = get_user(r.id)
    if not u: raise HTTPException(404, "user not found")
    u["stars"] = 0; save_user(r.id, u)
    return {"ok": True, "stars": 0}

def normalize(t):
    tot = sum(x["chance"] for x in t)
    if tot <= 0:
        t[-1]["chance"] = 100; return t
    if tot != 100:
        acc = 0
        for i, x in enumerate(t):
            if i == len(t)-1: x["chance"] = max(0, 100-acc)
            else:
                x["chance"] = round(x["chance"]*100/tot); acc += x["chance"]
    return t

def roll(t):
    r = random.randint(1, 100); acc = 0
    for it in t:
        acc += it["chance"]
        if r <= acc: return it["prize"]
    return t[-1]["prize"]

@app.post("/api/shop/case_free")
async def case_free(u: IdIn):
    now = int(time.time())
    user = get_user(u.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
    if now < user["free_ready_at"]: return {"ok": False, "reason": "cooldown"}
    sub = await check_sub(u.id)
    if not sub["subscribed"]: return {"ok": False, "reason": "not_subscribed", "diag": sub}
    prize = roll(MEM["conf"]["case_free"])
    user["stars"] += prize; user["free_ready_at"] = now + FREE_CD
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/case_paid")
def case_paid(u: IdIn):
    user = get_user(u.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
    cost = MEM["conf"]["case_paid_cost"]
    if user["stars"] < cost: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= cost
    prize = roll(MEM["conf"]["case_paid"]); user["stars"] += prize
    save_user(u.id, user)
    return {"ok": True, "prize": prize, "stars": user["stars"]}

@app.post("/api/shop/wheel")
def wheel(u: IdIn):
    user = get_user(u.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
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
def prob(): return {k: MEM["conf"][k] for k in ("case_free", "case_paid", "wheel")}

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
        if m.new in MEM["users"]: MEM["users"][m.new]["stars"] += old["stars"]
        else: MEM["users"][m.new] = old
    return {"ok": True}

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
        MEM["redemptions"].add((code, p.id)); pr["uses"] += 1
    u["stars"] += pr["reward"]; save_user(p.id, u)
    return {"ok": True, "reward": pr["reward"], "stars": u["stars"]}

@app.post("/api/shop/upgrade")
def upgrade(u: UpIn):
    user = get_user(u.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
    if u.mult not in MEM["conf"]["upgrader_mults"]: raise HTTPException(400, "bad mult")
    if u.stake < 10: raise HTTPException(400, "stake too small")
    if user["stars"] < u.stake: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= u.stake
    chance = up_chance(u.mult)
    win = random.randint(1, 100) <= chance
    payout = int(u.stake * u.mult) if win else 0
    user["stars"] += payout
    save_user(u.id, user)
    return {"ok": True, "win": win, "chance": chance, "payout": payout, "stars": user["stars"]}

def mines_mult(mines, k):
    m = HOUSE
    for i in range(k): m *= (25 - i) / (25 - mines - i)
    return m

def mines_get(gid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT uid, bet, mines, picks, state, win FROM shop_mines WHERE gid=%s", (gid,))
            r = cur.fetchone()
        c.close()
        if r: return {"uid": r[0], "bet": int(r[1]), "mines": [int(x) for x in r[2].split(",")],
                      "picks": [int(x) for x in r[3].split(",")] if r[3] else [], "state": r[4], "win": bool(r[5])}
        return None
    return MEM["mines"].get(gid)

def mines_save(gid, g):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO shop_mines(gid,uid,bet,mines,picks,state,created,win) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(gid) DO UPDATE SET picks=EXCLUDED.picks, state=EXCLUDED.state, win=EXCLUDED.win""",
                (gid, g["uid"], g["bet"], ",".join(map(str, g["mines"])), ",".join(map(str, g["picks"])), g["state"], int(time.time()), g.get("win", False)))
        c.close()
    else:
        MEM["mines"][gid] = g

@app.post("/api/shop/mines_start")
def mines_start(m: MinesStart):
    user = get_user(m.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
    if m.mines not in (3, 5, 10): raise HTTPException(400, "bad mines")
    if m.bet < 10: raise HTTPException(400, "bet too small")
    if user["stars"] < m.bet: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= m.bet; save_user(m.id, user)
    gid = uuid.uuid4().hex[:12]
    g = {"uid": m.id, "bet": m.bet, "mines": random.sample(range(25), m.mines), "picks": [],
         "state": "active", "win": random.randint(1, WIN_ONE_IN) == 1}
    mines_save(gid, g)
    return {"ok": True, "gid": gid, "bet": m.bet, "mines_count": m.mines, "stars": user["stars"]}

@app.post("/api/shop/mines_reveal")
def mines_reveal(m: MinesCell):
    g = mines_get(m.gid)
    if not g or g["uid"] != m.id: raise HTTPException(404, "game not found")
    if g["state"] != "active": raise HTTPException(400, "game over")
    if not (0 <= m.cell <= 24) or m.cell in g["picks"]: raise HTTPException(400, "bad cell")
    forced_loss = (not g.get("win")) and len(g["picks"]) == 0
    if forced_loss and m.cell not in g["mines"]:
        g["mines"].append(m.cell)
    if m.cell in g["mines"]:
        g["state"] = "lost"; mines_save(m.gid, g)
        return {"ok": True, "safe": False, "mines": g["mines"], "stars": get_user(m.id)["stars"]}
    g["picks"].append(m.cell)
    k = len(g["picks"]); mult = mines_mult(len(g["mines"]), k)
    payout = int(g["bet"] * mult)
    if k == 25 - len(g["mines"]):
        g["state"] = "won"; mines_save(m.gid, g)
        u = get_user(m.id); u["stars"] += payout; save_user(m.id, u)
        return {"ok": True, "safe": True, "auto": True, "mult": round(mult, 2), "payout": payout, "mines": g["mines"], "stars": u["stars"]}
    mines_save(m.gid, g)
    nxt = mines_mult(len(g["mines"]), k + 1)
    return {"ok": True, "safe": True, "auto": False, "mult": round(mult, 2), "payout": payout,
            "next_mult": round(nxt, 2), "next_payout": int(g["bet"] * nxt), "picked": g["picks"]}

@app.post("/api/shop/mines_cashout")
def mines_cashout(m: MinesCash):
    g = mines_get(m.gid)
    if not g or g["uid"] != m.id: raise HTTPException(404, "game not found")
    if g["state"] != "active" or not g["picks"]: raise HTTPException(400, "nothing to cash")
    mult = mines_mult(len(g["mines"]), len(g["picks"]))
    payout = int(g["bet"] * mult)
    g["state"] = "won"; mines_save(m.gid, g)
    u = get_user(m.id); u["stars"] += payout; save_user(m.id, u)
    return {"ok": True, "payout": payout, "mult": round(mult, 2), "mines": g["mines"], "stars": u["stars"]}

# ===== РАКЕТА (crash) =====
def rocket_get(gid):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("SELECT uid, bet, crash, t0, state, cash_mult, payout FROM shop_rocket WHERE gid=%s", (gid,))
            r = cur.fetchone()
        c.close()
        if r: return {"uid": r[0], "bet": int(r[1]), "crash": float(r[2]), "t0": float(r[3]),
                      "state": r[4], "cash_mult": float(r[5]) if r[5] else 0, "payout": int(r[6] or 0)}
        return None
    return MEM["rocket"].get(gid)

def rocket_save(gid, g):
    c = conn()
    if c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO shop_rocket(gid,uid,bet,crash,t0,state,cash_mult,payout) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(gid) DO UPDATE SET state=EXCLUDED.state, cash_mult=EXCLUDED.cash_mult, payout=EXCLUDED.payout""",
                (gid, g["uid"], g["bet"], g["crash"], g["t0"], g["state"], g.get("cash_mult", 0), g.get("payout", 0)))
        c.close()
    else:
        MEM["rocket"][gid] = g

@app.post("/api/shop/rocket_start")
def rocket_start(m: RocketStart):
    user = get_user(m.id) or dict(EMPTY)
    if not user.get("registered"): raise HTTPException(400, "not registered")
    if m.bet < 10: raise HTTPException(400, "bet too small")
    if user["stars"] < m.bet: return {"ok": False, "reason": "no_stars"}
    user["stars"] -= m.bet; save_user(m.id, user)
    gid = uuid.uuid4().hex[:12]
    g = {"uid": m.id, "bet": m.bet, "crash": rocket_crash_point(), "t0": time.time(), "state": "active", "cash_mult": 0, "payout": 0}
    rocket_save(gid, g)
    return {"ok": True, "gid": gid, "bet": m.bet, "stars": user["stars"]}

@app.post("/api/shop/rocket_state")
def rocket_state(m: RocketCtl):
    g = rocket_get(m.gid)
    if not g or g["uid"] != m.id: raise HTTPException(404, "game not found")
    if g["state"] != "active":
        return {"flying": False, "crashed": g["state"] == "crashed", "cur": g.get("cash_mult") or g["crash"],
                "crash": g["crash"], "payout": g.get("payout", 0)}
    cur = rocket_growth(time.time() - g["t0"])
    if cur >= g["crash"]:
        g["state"] = "crashed"; rocket_save(m.gid, g)
        return {"flying": False, "crashed": True, "cur": g["crash"], "crash": g["crash"], "payout": 0}
    return {"flying": True, "crashed": False, "cur": round(cur, 2)}

@app.post("/api/shop/rocket_cash")
def rocket_cash(m: RocketCtl):
    g = rocket_get(m.gid)
    if not g or g["uid"] != m.id: raise HTTPException(404, "game not found")
    if g["state"] != "active": raise HTTPException(400, "round over")
    cur = rocket_growth(time.time() - g["t0"])
    user = get_user(m.id) or dict(EMPTY)
    if cur >= g["crash"]:
        g["state"] = "crashed"; rocket_save(m.gid, g)
        return {"ok": True, "crashed": True, "mult": g["crash"], "payout": 0, "stars": user["stars"]}
    payout = int(g["bet"] * cur)
    g["state"] = "won"; g["cash_mult"] = round(cur, 2); g["payout"] = payout
    rocket_save(m.gid, g)
    user["stars"] += payout; save_user(m.id, user)
    return {"ok": True, "crashed": False, "mult": round(cur, 2), "payout": payout, "stars": user["stars"]}

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/{full_path:path}")
def fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(404)
    return serve_index()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))