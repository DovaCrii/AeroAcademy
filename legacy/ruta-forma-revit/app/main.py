"""Ruta Forma + Revit: backend mínimo para el modo equipo.

Identidad: la entrega Tailscale Serve en los encabezados Tailscale-User-*.
El servicio escucha solo en 127.0.0.1, así que el acceso es exclusivamente por la tailnet.
"""
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("RUTA_DB", BASE / "data" / "ruta.db"))
DEV_USER = os.environ.get("RUTA_DEV_USER", "")  # solo para pruebas locales sin Tailscale
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

KEY_RE = re.compile(r"^(kit|ph)\d{1,2}-\d{1,2}$")
LV_RE = re.compile(r"^(general|n[0-9])$")
TYPES = {"works", "fails", "tip", "ask", ""}

app = FastAPI(title="Ruta Forma + Revit", docs_url=None, redoc_url=None, openapi_url=None)


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


with db() as c:
    c.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS people(id TEXT PRIMARY KEY, name TEXT, pic TEXT, last_seen INTEGER);
        CREATE TABLE IF NOT EXISTS progress(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated INTEGER);
        CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY, author TEXT, lv TEXT, res INTEGER, type TEXT,
                                         text TEXT, parent TEXT, ts INTEGER);
        CREATE TABLE IF NOT EXISTS shared(key TEXT PRIMARY KEY, by TEXT, ts INTEGER);
        """
    )


def now() -> int:
    return int(time.time() * 1000)


def who(req: Request) -> dict:
    login = req.headers.get("Tailscale-User-Login") or DEV_USER
    if not login:
        raise HTTPException(401, "Sin identidad de Tailscale: entra por la URL de tailscale serve.")
    hdr_name = req.headers.get("Tailscale-User-Name")
    hdr_pic = req.headers.get("Tailscale-User-Profile-Pic")
    with db() as c:
        c.execute(
            "INSERT INTO people(id,name,pic,last_seen) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=COALESCE(?, people.name), pic=COALESCE(?, people.pic), "
            "last_seen=excluded.last_seen",
            (login, hdr_name or login.split("@")[0], hdr_pic or "", now(), hdr_name, hdr_pic),
        )
        row = c.execute("SELECT name, pic FROM people WHERE id=?", (login,)).fetchone()
    return {"id": login, "name": row["name"], "pic": row["pic"] or ""}


@app.get("/api/me")
def me(req: Request):
    return who(req)


@app.get("/api/state")
def state(req: Request):
    who(req)
    with db() as c:
        people = {r["id"]: {"name": r["name"], "pic": r["pic"]} for r in c.execute("SELECT * FROM people")}
        progress = {}
        for r in c.execute("SELECT * FROM progress"):
            d = json.loads(r["data"])
            d["updated"] = r["updated"]
            progress[r["id"]] = d
        notes = [dict(r) for r in c.execute("SELECT * FROM notes ORDER BY ts DESC LIMIT 1000")]
        shared = {r["key"]: {"by": r["by"], "ts": r["ts"]} for r in c.execute("SELECT * FROM shared")}
    return {"people": people, "progress": progress, "notes": notes, "shared": shared}


@app.put("/api/progress")
async def put_progress(req: Request):
    u = who(req)
    body = await req.json()
    data = {
        "checks": {k: True for k, v in (body.get("checks") or {}).items() if v and len(k) < 12},
        "quiz": {k: v for k, v in (body.get("quiz") or {}).items() if isinstance(v, int) and len(k) < 12},
        "certGoal": str(body.get("certGoal") or "")[:80],
    }
    raw = json.dumps(data)
    if len(raw) > 20000:
        raise HTTPException(413, "Avance demasiado grande")
    with db() as c:
        c.execute(
            "INSERT INTO progress(id,data,updated) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
            (u["id"], raw, now()),
        )
    return {"ok": True}


@app.post("/api/notes")
async def add_note(req: Request):
    u = who(req)
    b = await req.json()
    text = str(b.get("text") or "").strip()[:1000]
    lv = str(b.get("lv") or "general")
    ntype = str(b.get("type") or "")
    parent = b.get("parent") or None
    try:
        res = int(b.get("res", -1))
    except (TypeError, ValueError):
        res = -1
    if not text or not LV_RE.match(lv) or ntype not in TYPES:
        raise HTTPException(400, "Nota inválida")
    note = {"id": uuid.uuid4().hex, "author": u["id"], "lv": lv, "res": res, "type": ntype,
            "text": text, "parent": str(parent)[:40] if parent else None, "ts": now()}
    with db() as c:
        c.execute("INSERT INTO notes VALUES(:id,:author,:lv,:res,:type,:text,:parent,:ts)", note)
    return note


@app.delete("/api/notes/{nid}")
def del_note(nid: str, req: Request):
    u = who(req)
    with db() as c:
        row = c.execute("SELECT author FROM notes WHERE id=?", (nid,)).fetchone()
        if not row:
            raise HTTPException(404, "La nota no existe")
        if row["author"] != u["id"]:
            raise HTTPException(403, "Solo el autor puede borrar su nota")
        c.execute("DELETE FROM notes WHERE id=? OR parent=?", (nid, nid))
    return {"ok": True}


@app.put("/api/shared/{key}")
async def put_shared(key: str, req: Request):
    u = who(req)
    if not KEY_RE.match(key):
        raise HTTPException(400, "Clave inválida")
    done = bool((await req.json()).get("done"))
    with db() as c:
        if done:
            c.execute("INSERT OR REPLACE INTO shared VALUES(?,?,?)", (key, u["id"], now()))
        else:
            c.execute("DELETE FROM shared WHERE key=?", (key,))
    return {"ok": True}


@app.get("/healthz")
def health():
    return JSONResponse({"ok": True})


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/academia")
def academia():
    return FileResponse(BASE / "static" / "academia.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
