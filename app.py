"""DB Tester Toolkit - local web app for functional testers (Oracle / SQL Server / SQLite)."""
import os, re, sys, json, time, base64, sqlite3, threading, webbrowser
from flask import Flask, request, Response, render_template

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.path.expanduser("~"), ".dbtester"); os.makedirs(DATA, exist_ok=True)
F_CONN, F_SNAP, F_HIST = [os.path.join(DATA, n) for n in ("connections.json", "snapshots.json", "history.json")]
app = Flask(__name__, template_folder=os.path.join(BASE, "templates"))
STATE = {"conn": None, "type": None, "name": None, "readonly": True}

def out(o, code=200): return Response(json.dumps(o, default=str), code, mimetype="application/json")
def load(f, d):
    try: return json.load(open(f))
    except Exception: return d
def save(f, o): json.dump(o, open(f, "w"), indent=1)
def enc(s): return base64.b64encode(s.encode()).decode()      # light obfuscation, not strong crypto
def dec(s): return base64.b64decode(s.encode()).decode()

def make_demo():
    p = os.path.join(DATA, "demo.db")
    if os.path.exists(p): os.remove(p)
    c = sqlite3.connect(p); c.executescript("""
    CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT, country TEXT);
    CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, price REAL);
    CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), status TEXT, order_date TEXT);
    CREATE TABLE order_items(id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id), product_id INTEGER REFERENCES products(id), qty INTEGER);
    INSERT INTO customers VALUES (1,'Alice Ray','alice@mail.com','US'),(2,'Bob Stone','bob@mail.com','UK'),(3,'Chen Wei',NULL,'SG'),(4,'Dana Lopez','dana@mail.com','US'),(5,'Alice Ray','alice@mail.com','US');
    INSERT INTO products VALUES (1,'Laptop',999.0),(2,'Mouse',19.5),(3,'Monitor',249.0),(4,'Keyboard',49.9);
    INSERT INTO orders VALUES (101,1,'SHIPPED','2026-10-01'),(102,2,'PENDING','2026-10-03'),(103,1,'SHIPPED','2026-10-05'),(104,4,'CANCELLED','2026-10-07'),(105,99,'PENDING','2026-10-09');
    INSERT INTO order_items VALUES (1,101,1,1),(2,101,2,2),(3,102,3,1),(4,103,4,3),(5,104,2,1),(6,105,1,1);
    """); c.commit(); c.close(); return p

def connect(cfg):
    t = cfg["type"]
    if t == "sqlite": return sqlite3.connect(cfg.get("database") or make_demo(), check_same_thread=False)
    if t == "oracle":
        import oracledb
        if cfg.get("conn_string"): dsn = cfg["conn_string"]
        elif cfg.get("mode") == "sid": dsn = oracledb.makedsn(cfg["host"], int(cfg.get("port") or 1521), sid=cfg["service"])
        else: dsn = f'{cfg["host"]}:{cfg.get("port") or 1521}/{cfg["service"]}'
        c = oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=dsn)
        if cfg.get("schema"):
            c.cursor().execute("ALTER SESSION SET CURRENT_SCHEMA = " + re.sub(r"[^A-Za-z0-9_$#]", "", cfg["schema"]))
        return c
    if t == "mssql":
        import pyodbc
        if cfg.get("conn_string"): return pyodbc.connect(cfg["conn_string"])
        drv = sorted([d for d in pyodbc.drivers() if "SQL Server" in d], key=lambda d: (("ODBC Driver" in d), d))
        if not drv: raise RuntimeError("No SQL Server ODBC driver found. Install 'ODBC Driver 17/18 for SQL Server'.")
        auth = "Trusted_Connection=yes" if cfg.get("mode") == "windows" else f'UID={cfg["user"]};PWD={cfg["password"]}'
        return pyodbc.connect(f'DRIVER={{{drv[-1]}}};SERVER={cfg["host"]},{cfg.get("port") or 1433};DATABASE={cfg["database"]};{auth};TrustServerCertificate=yes')
    raise ValueError("Unsupported DB type")

CONNS = {}
def open_profile(name):
    if name not in CONNS:
        cfg = next((c for c in load(F_CONN, []) if c["name"] == name), None)
        if not cfg: raise ValueError(f"Unknown connection: {name}")
        cfg = dict(cfg); cfg["password"] = dec(cfg["password"]) if cfg.get("password") else ""
        CONNS[name] = connect(cfg)
    return CONNS[name]

def q(sql, params=(), limit=None, conn=None):
    cur = (conn or STATE["conn"]).cursor(); t0 = time.time(); cur.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [list(r) for r in (cur.fetchmany(limit) if limit else cur.fetchall())] if cols else []
    return cols, rows, round((time.time() - t0) * 1000)

def schema():
    t, tabs, fks = STATE["type"], {}, []
    if t == "sqlite":
        for (n,) in q("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by 1")[1]:
            tabs[n] = {"cols": [{"name": r[1], "type": r[2], "pk": bool(r[5])} for r in q(f"pragma table_info('{n}')")[1]]}
            for r in q(f"pragma foreign_key_list('{n}')")[1]: fks.append({"t": n, "c": r[3], "rt": r[2], "rc": r[4]})
    elif t == "oracle":
        o = re.sub(r"[^A-Za-z0-9_$#]", "", STATE["owner"]).upper()
        for n, c, ty in q(f"select c.table_name,c.column_name,c.data_type from all_tab_columns c join all_tables t on t.owner=c.owner and t.table_name=c.table_name where c.owner='{o}' order by c.table_name,c.column_id")[1]:
            tabs.setdefault(n, {"cols": []})["cols"].append({"name": c, "type": ty, "pk": False})
        for n, c in q(f"select cc.table_name,cc.column_name from all_constraints k join all_cons_columns cc on k.owner=cc.owner and k.constraint_name=cc.constraint_name where k.owner='{o}' and k.constraint_type='P'")[1]:
            for col in tabs.get(n, {"cols": []})["cols"]:
                if col["name"] == c: col["pk"] = True
        for a, b, c, d in q(f"select a.table_name,a.column_name,c_pk.table_name,pc.column_name from all_cons_columns a join all_constraints c on a.owner=c.owner and a.constraint_name=c.constraint_name join all_constraints c_pk on c.r_owner=c_pk.owner and c.r_constraint_name=c_pk.constraint_name join all_cons_columns pc on pc.owner=c_pk.owner and pc.constraint_name=c_pk.constraint_name and pc.position=a.position where c.owner='{o}' and c.constraint_type='R'")[1]:
            fks.append({"t": a, "c": b, "rt": c, "rc": d})
    else:
        nm = lambda sch, tb: f"case when {sch}='dbo' then {tb} else {sch}+'.'+{tb} end"
        for n, c, ty in q(f"select {nm('c.table_schema','c.table_name')},c.column_name,c.data_type from information_schema.columns c join information_schema.tables t on t.table_schema=c.table_schema and t.table_name=c.table_name and t.table_type='BASE TABLE' order by c.table_schema,c.table_name,c.ordinal_position")[1]:
            tabs.setdefault(n, {"cols": []})["cols"].append({"name": c, "type": ty, "pk": False})
        for n, c in q(f"select {nm('k.table_schema','k.table_name')},k.column_name from information_schema.table_constraints tc join information_schema.key_column_usage k on tc.constraint_name=k.constraint_name and tc.table_schema=k.table_schema where tc.constraint_type='PRIMARY KEY'")[1]:
            for col in tabs.get(n, {"cols": []})["cols"]:
                if col["name"] == c: col["pk"] = True
        sp, sr = "schema_name(tp.schema_id)", "schema_name(tr.schema_id)"
        for a, b, c, d in q(f"select {nm(sp,'tp.name')},cp.name,{nm(sr,'tr.name')},cr.name from sys.foreign_key_columns fk join sys.tables tp on fk.parent_object_id=tp.object_id join sys.columns cp on cp.object_id=tp.object_id and cp.column_id=fk.parent_column_id join sys.tables tr on fk.referenced_object_id=tr.object_id join sys.columns cr on cr.object_id=tr.object_id and cr.column_id=fk.referenced_column_id")[1]:
            fks.append({"t": a, "c": b, "rt": c, "rc": d})
    for n in tabs:
        try: tabs[n]["rows"] = q(f"select count(*) from {n}")[1][0][0]
        except Exception: tabs[n]["rows"] = None
    return {"tables": tabs, "fks": fks}

def guard(sql):
    s = sql.strip().rstrip(";")
    if ";" in s: raise ValueError("Only one statement at a time.")
    if STATE["readonly"] and not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("Read-only mode is ON: only SELECT / WITH queries are allowed. Turn it off in the top bar to run changes.")
    return s

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/connections", methods=["GET", "POST", "DELETE"])
def connections():
    L = load(F_CONN, [])
    if request.method == "GET": return out([{k: v for k, v in c.items() if k != "password"} for c in L])
    d = request.json
    L = [c for c in L if c["name"] != d["name"]]
    if request.method == "POST":
        old = next((c for c in load(F_CONN, []) if c["name"] == d["name"]), {})
        d["password"] = enc(d["password"]) if d.get("password") else old.get("password", ""); L.append(d)
    save(F_CONN, L); return out({"ok": True})

@app.route("/api/connect", methods=["POST"])
def do_connect():
    d = request.json
    cfg = next((c for c in load(F_CONN, []) if c["name"] == d["name"]), None)
    if not cfg: return out({"error": "Unknown profile"}, 400)
    cfg = dict(cfg); cfg["password"] = dec(cfg["password"]) if cfg.get("password") else ""
    try:
        conn = connect(cfg)
        if d.get("test_only"): conn.close(); return out({"ok": True, "msg": "Connection successful"})
        STATE.update(conn=conn, type=cfg["type"], name=cfg["name"], owner=cfg.get("schema") or cfg.get("user") or ""); CONNS[cfg["name"]] = conn; return out({"ok": True, "schema": schema()})
    except Exception as e: return out({"error": str(e)}, 400)

@app.route("/api/mode", methods=["POST"])
def mode(): STATE["readonly"] = bool(request.json["readonly"]); return out({"ok": True})

@app.route("/api/query", methods=["POST"])
def query():
    if not STATE["conn"]: return out({"error": "Not connected. Open the Connections tab."}, 400)
    d = request.json
    try:
        sql = guard(d["sql"]); cols, rows, ms = q(sql, limit=int(d.get("limit", 500)))
        if not cols: STATE["conn"].commit()
        H = load(F_HIST, []); H.insert(0, {"sql": sql, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "conn": STATE["name"], "rows": len(rows)}); save(F_HIST, H[:50])
        return out({"cols": cols, "rows": rows, "ms": ms})
    except Exception as e: return out({"error": str(e)}, 400)

@app.route("/api/history")
def history(): return out(load(F_HIST, []))

def norm(v):
    """Make Oracle / SQL Server values comparable (Decimal vs int, date vs datetime, padding)."""
    import decimal, datetime
    if v is None: return None
    if isinstance(v, (int, float, decimal.Decimal)) and not isinstance(v, bool): return float(f"{float(v):.10g}")
    if isinstance(v, datetime.datetime): return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date): return v.strftime("%Y-%m-%d") + " 00:00:00"
    return v.strip() if isinstance(v, str) else str(v)

@app.route("/api/compare", methods=["POST"])
def compare():
    d = request.json
    try:
        cA = open_profile(d["connA"]) if d.get("connA") else None; cB = open_profile(d["connB"]) if d.get("connB") else None
        ca, ra, _ = q(guard(d["a"]), conn=cA); cb, rb, _ = q(guard(d["b"]), conn=cB)
        ra, rb = [[norm(v) for v in r] for r in ra], [[norm(v) for v in r] for r in rb]
        key = [k.strip().lower() for k in d.get("key", "").split(",") if k.strip()]
        la, lb = [c.lower() for c in ca], [c.lower() for c in cb]
        if key:
            ia, ib = [la.index(k) for k in key], [lb.index(k) for k in key]
            A = {tuple(r[i] for i in ia): r for r in ra}; B = {tuple(r[i] for i in ib): r for r in rb}
            onlyA = [A[k] for k in A if k not in B]; onlyB = [B[k] for k in B if k not in A]
            changed = []
            for k in A:
                if k in B and A[k] != B[k]:
                    diff = [f"{ca[i]}: {A[k][i]} → {B[k][i]}" for i in range(min(len(ca), len(cb))) if A[k][i] != B[k][i]]
                    changed.append(list(k) + ["; ".join(diff)])
            return out({"colsA": ca, "colsB": cb, "countA": len(ra), "countB": len(rb), "onlyA": onlyA[:200], "onlyB": onlyB[:200], "changed": changed[:200], "keycols": key})
        sa, sb = {tuple(r) for r in ra}, {tuple(r) for r in rb}
        return out({"colsA": ca, "colsB": cb, "countA": len(ra), "countB": len(rb), "onlyA": [list(r) for r in sa - sb][:200], "onlyB": [list(r) for r in sb - sa][:200], "changed": [], "keycols": []})
    except Exception as e: return out({"error": str(e)}, 400)

@app.route("/api/checks", methods=["POST"])
def checks():
    d = request.json; tb = d["table"]; res = []
    try:
        sc = schema(); info = sc["tables"][tb]
        n = q(f"select count(*) from {tb}")[1][0][0]
        res.append({"check": "Row count", "status": "PASS" if n else "WARN", "detail": f"{n} rows" if n else "Table is empty"})
        for c in info["cols"]:
            nulls = q(f"select count(*) from {tb} where {c['name']} is null")[1][0][0]
            if nulls: res.append({"check": f"NULLs in {c['name']}", "status": "WARN", "detail": f"{nulls} of {n} rows are NULL"})
        for c in info["cols"]:
            if c["pk"]: continue
            dup = q(f"select {c['name']}, count(*) from {tb} where {c['name']} is not null group by {c['name']} having count(*)>1")[1]
            if dup and len(dup) < n and c["name"].lower() in ("email", "name", "code", "username", "ssn"):
                res.append({"check": f"Duplicates in {c['name']}", "status": "WARN", "detail": f"{len(dup)} duplicated value(s), e.g. {dup[0][0]} ×{dup[0][1]}"})
        for f in sc["fks"]:
            if f["t"] == tb:
                o = q(f"select count(*) from {tb} a left join {f['rt']} b on a.{f['c']}=b.{f['rc']} where a.{f['c']} is not null and b.{f['rc']} is null")[1][0][0]
                res.append({"check": f"Orphans: {tb}.{f['c']} → {f['rt']}.{f['rc']}", "status": "FAIL" if o else "PASS", "detail": f"{o} orphan row(s)" if o else "No orphans"})
        return out(res)
    except Exception as e: return out({"error": str(e)}, 400)

@app.route("/api/snapshots", methods=["GET", "POST"])
def snaps():
    S = load(F_SNAP, {})
    if request.method == "GET": return out({k: {"ts": v["ts"], "conn": v["conn"]} for k, v in S.items()})
    d = request.json; cur = {k: v["rows"] for k, v in schema()["tables"].items()}
    if d.get("diff"):
        old = S[d["name"]]["counts"]
        return out([{"table": t, "before": old.get(t), "after": cur.get(t), "delta": (cur.get(t) or 0) - (old.get(t) or 0)} for t in sorted(set(old) | set(cur))])
    S[d["name"]] = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "conn": STATE["name"], "counts": cur}; save(F_SNAP, S); return out({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5055))
    if "--demo" in sys.argv or not load(F_CONN, []):
        L = [c for c in load(F_CONN, []) if c["name"] != "Demo (SQLite)"]
        L.insert(0, {"name": "Demo (SQLite)", "type": "sqlite", "database": "", "password": ""}); save(F_CONN, L)
    if not os.environ.get("NO_BROWSER"): threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port)
