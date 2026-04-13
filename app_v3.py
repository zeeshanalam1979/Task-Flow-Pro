"""
TaskFlow Pro – Jira-style Task Manager
Board view (Kanban) + List view + Daily Summary
Login + JSON local storage + Supabase cloud storage
"""

import streamlit as st
import hashlib, uuid, csv, io, json
from datetime import datetime, date
from pathlib import Path

st.set_page_config(page_title="TaskFlow Pro", page_icon="✅",
                   layout="wide", initial_sidebar_state="expanded")

# ── Supabase (optional, silent fallback) ──────────────────────────────────────
_supabase = None
DB_MODE   = "json"
try:
    from supabase import create_client
    _url = st.secrets.get("SUPABASE_URL", "")
    _key = st.secrets.get("SUPABASE_KEY", "")
    if _url and _key:
        _supabase = create_client(_url, _key)
        DB_MODE   = "supabase"
except Exception:
    pass

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Fix button cutoff at top */
.block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }

[data-testid="stAppViewContainer"] { background: #f4f5f7; }
[data-testid="stSidebar"]          { background: #1d2125; }
[data-testid="stSidebar"] * { color: #b6c2cf !important; }
[data-testid="stSidebar"] .stButton button {
    background: transparent !important; border: none !important;
    color: #b6c2cf !important; text-align: left !important;
    padding: 6px 10px !important; border-radius: 4px !important;
    font-size: 14px !important; width: 100% !important;
}
[data-testid="stSidebar"] .stButton button:hover { background: #2c333a !important; color: #fff !important; }
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #1c3a5e !important; color: #4a9eff !important; font-weight: 600 !important;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: #fff; border: 1px solid #dfe1e6;
    border-radius: 8px; padding: 12px 16px;
}
[data-testid="stMetricLabel"]  { font-size: 13px !important; color: #5e6c84 !important; }
[data-testid="stMetricValue"]  { font-size: 22px !important; font-weight: 700 !important; }

/* Top toolbar */
.toolbar-row { display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap; }

/* View toggle tabs */
.view-tabs { display:flex; gap:4px; background:#fff; border:1px solid #dfe1e6;
             border-radius:8px; padding:4px; margin-bottom:16px; width:fit-content; }
.view-tab  { padding:6px 18px; border-radius:6px; font-size:14px; font-weight:500;
             cursor:pointer; color:#5e6c84; border:none; background:transparent; }
.view-tab.active { background:#0052cc; color:#fff; }

/* Kanban board */
.kanban-wrap { display:flex; gap:12px; overflow-x:auto; padding-bottom:12px; }
.kanban-col  {
    min-width:270px; max-width:270px;
    background:#f0f1f4; border-radius:10px; padding:10px;
    display:flex; flex-direction:column; gap:8px;
}
.kanban-col-header {
    display:flex; align-items:center; justify-content:space-between;
    padding:6px 4px 10px; font-size:12px; font-weight:700;
    text-transform:uppercase; letter-spacing:.06em; color:#5e6c84;
}
.kanban-count { background:#dfe1e6; color:#5e6c84; border-radius:10px;
                padding:1px 8px; font-size:11px; font-weight:700; }

/* Kanban card */
.k-card {
    background:#fff; border-radius:8px; padding:14px;
    border:1px solid #dfe1e6; cursor:pointer;
    transition: box-shadow .15s, border-color .15s;
    margin-bottom:2px;
}
.k-card:hover { box-shadow:0 2px 8px rgba(0,0,0,.12); border-color:#adb5bd; }
.k-card-title { font-size:15px; font-weight:600; color:#172b4d; margin-bottom:10px; line-height:1.4; }
.k-card-meta  { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
.k-card-footer { display:flex; align-items:center; justify-content:space-between; margin-top:10px; }

/* List view table */
.list-table { width:100%; border-collapse:collapse; background:#fff;
              border:1px solid #dfe1e6; border-radius:10px; overflow:hidden; font-size:15px; }
.list-table th {
    background:#f4f5f7; padding:12px 14px; text-align:left;
    font-size:12px; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; color:#5e6c84; border-bottom:2px solid #dfe1e6;
}
.list-table td { padding:13px 14px; border-bottom:1px solid #f0f1f4; vertical-align:middle; }
.list-table tr:last-child td { border-bottom:none; }
.list-table tr:hover td { background:#f8f9fa; }
.list-table .task-title-cell { font-size:15px; font-weight:600; color:#172b4d; }
.list-table .task-desc-cell  { font-size:13px; color:#5e6c84; margin-top:2px; }

/* Status badges */
.badge {
    display:inline-flex; align-items:center; padding:3px 10px;
    border-radius:4px; font-size:12px; font-weight:700;
    letter-spacing:.03em; white-space:nowrap;
}
.badge-todo       { background:#f0f1f4; color:#5e6c84; }
.badge-inprogress { background:#e3f2fd; color:#0052cc; }
.badge-review     { background:#ede7f6; color:#5e35b1; }
.badge-blocked    { background:#ffebee; color:#c62828; }
.badge-done       { background:#e8f5e9; color:#2e7d32; }
.badge-high       { background:#ffebee; color:#c62828; }
.badge-medium     { background:#fff8e1; color:#f57f17; }
.badge-low        { background:#e8f5e9; color:#2e7d32; }

.pri-dot { width:10px; height:10px; border-radius:50%; display:inline-block; margin-right:5px; }
.pri-high   { background:#ef4444; }
.pri-medium { background:#f59e0b; }
.pri-low    { background:#22c55e; }

/* Timer pill */
.timer-pill {
    font-family:monospace; font-size:12px; font-weight:600;
    background:#f0f1f4; color:#5e6c84;
    padding:3px 9px; border-radius:20px; display:inline-block;
}
.timer-pill.running { background:#e3f2fd; color:#0052cc; }

/* Section header */
.sec-hdr {
    font-size:12px; font-weight:700; color:#5e6c84;
    text-transform:uppercase; letter-spacing:.06em;
    padding:12px 0 6px; border-bottom:2px solid #dfe1e6; margin-bottom:8px;
}

/* Comment bubble */
.c-bubble { background:#f4f5f7; border-left:3px solid #0052cc;
            border-radius:4px; padding:10px 14px; margin-bottom:8px; }
.c-bubble .c-author { font-size:13px; font-weight:700; color:#172b4d; }
.c-bubble .c-time   { font-size:11px; color:#5e6c84; margin-left:8px; }
.c-bubble .c-text   { font-size:14px; color:#172b4d; margin-top:4px; }

/* Auth page */
.auth-card { max-width:440px; margin:50px auto; background:#fff;
             border:1px solid #dfe1e6; border-radius:12px; padding:36px; }

/* Summary cards */
.sum-proj-card { background:#fff; border:1px solid #dfe1e6; border-radius:10px;
                 padding:16px 18px; margin-bottom:14px; }

/* Override Streamlit default form spacing */
div[data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_FILE     = Path("taskflow_data.json")
STATUS_LABELS = {"todo":"TO DO","in-progress":"IN PROGRESS","review":"IN REVIEW","blocked":"BLOCKED","done":"DONE"}
STATUS_ICONS  = {"todo":"⬜","in-progress":"🔄","review":"🔍","blocked":"🚫","done":"✅"}
STATUS_COLORS = {"todo":"#5e6c84","in-progress":"#0052cc","review":"#5e35b1","blocked":"#c62828","done":"#2e7d32"}
STATUS_BG     = {"todo":"#f0f1f4","in-progress":"#e3f2fd","review":"#ede7f6","blocked":"#ffebee","done":"#e8f5e9"}
PRI_ICONS     = {"high":"🔴","medium":"🟡","low":"🟢"}
PRI_COLORS    = {"high":"#ef4444","medium":"#f59e0b","low":"#22c55e"}
STATUS_ORDER  = ["todo","in-progress","review","blocked","done"]

KANBAN_COLS = [
    ("todo",        "To Do",       "#5e6c84"),
    ("in-progress", "In Progress", "#0052cc"),
    ("review",      "In Review",   "#5e35b1"),
    ("blocked",     "Blocked",     "#c62828"),
    ("done",        "Done",        "#2e7d32"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def uid():       return str(uuid.uuid4())[:8]
def hash_pw(p):  return hashlib.sha256(p.encode()).hexdigest()
def today_str(): return str(date.today())
def now_str():   return datetime.now().strftime("%d %b %Y %H:%M")

def fmt_time(secs):
    secs = int(secs or 0)
    if secs <= 0: return "0s"
    h, r = divmod(secs, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m" if h else (f"{m}m {s}s" if m else f"{s}s")

def jl(v, d=None):
    d = d if d is not None else []
    if isinstance(v, list): return v
    if isinstance(v, str):
        try: return json.loads(v)
        except: return d
    return d

def badge_html(status):
    key = status.replace("-","")
    label = STATUS_LABELS.get(status, status.upper())
    col   = STATUS_COLORS.get(status, "#5e6c84")
    bg    = STATUS_BG.get(status, "#f0f1f4")
    return f'<span class="badge badge-{key}" style="background:{bg};color:{col}">{label}</span>'

def pri_html(priority):
    col = PRI_COLORS.get(priority, "#5e6c84")
    return f'<span class="pri-dot" style="background:{col}"></span>{priority.capitalize()}'

# ── Local JSON storage ────────────────────────────────────────────────────────
def _load():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {"users":{}, "projects":[], "tasks":[]}

def _save(db): DATA_FILE.write_text(json.dumps(db, indent=2))
def _db():
    if "_jdb" not in st.session_state:
        st.session_state["_jdb"] = _load()
    return st.session_state["_jdb"]
def _flush():
    if DB_MODE == "json": _save(_db())

# ── DB layer ──────────────────────────────────────────────────────────────────
def db_get_user(u):
    if DB_MODE == "supabase":
        r = _supabase.table("users").select("*").eq("username",u).execute()
        return r.data[0] if r.data else None
    return _db()["users"].get(u)

def db_create_user(username, pw, name):
    user = {"id":uid(),"username":username,"password_hash":hash_pw(pw),"display_name":name,"created_at":now_str()}
    if DB_MODE == "supabase": _supabase.table("users").insert(user).execute()
    else: _db()["users"][username] = user; _flush()
    return user

def db_get_projects(uid_):
    if DB_MODE == "supabase":
        return _supabase.table("projects").select("*").eq("user_id",uid_).order("created_at").execute().data
    return [p for p in _db()["projects"] if p["user_id"] == uid_]

def db_add_project(p):
    if DB_MODE == "supabase": _supabase.table("projects").insert(p).execute()
    else: _db()["projects"].append(p); _flush()

def db_delete_project(pid):
    if DB_MODE == "supabase":
        _supabase.table("projects").delete().eq("id",pid).execute()
        _supabase.table("tasks").delete().eq("project_id",pid).execute()
    else:
        db = _db()
        db["projects"] = [p for p in db["projects"] if p["id"] != pid]
        db["tasks"]    = [t for t in db["tasks"]    if t["project_id"] != pid]
        _flush()

def db_get_tasks(uid_):
    if DB_MODE == "supabase":
        return _supabase.table("tasks").select("*").eq("user_id",uid_).order("sort_order").execute().data
    return [t for t in _db()["tasks"] if t["user_id"] == uid_]

def db_add_task(t):
    if DB_MODE == "supabase":
        t2 = dict(t)
        t2["subtasks"] = json.dumps(t2.get("subtasks",[]))
        t2["comments"] = json.dumps(t2.get("comments",[]))
        _supabase.table("tasks").insert(t2).execute()
    else: _db()["tasks"].append(t); _flush()

def db_update_task(tid, upd):
    if DB_MODE == "supabase":
        u2 = dict(upd)
        if "subtasks" in u2 and isinstance(u2["subtasks"],list): u2["subtasks"]=json.dumps(u2["subtasks"])
        if "comments" in u2 and isinstance(u2["comments"],list): u2["comments"]=json.dumps(u2["comments"])
        _supabase.table("tasks").update(u2).eq("id",tid).execute()
    else:
        for t in _db()["tasks"]:
            if t["id"] == tid: t.update(upd)
        _flush()

def db_delete_task(tid):
    if DB_MODE == "supabase": _supabase.table("tasks").delete().eq("id",tid).execute()
    else: _db()["tasks"] = [t for t in _db()["tasks"] if t["id"]!=tid]; _flush()

def seed_projects(uid_):
    for n,c in [("Cloud Wholesale SEO","#0052cc"),("iPuff24 Shopify SEO","#5e35b1"),("General","#2e7d32")]:
        db_add_project({"id":uid(),"user_id":uid_,"name":n,"color":c,"created_at":now_str()})

# ── Session state ─────────────────────────────────────────────────────────────
_DEF = {
    "logged_in":False,"current_user":None,
    "view":"board",          # board | list | summary
    "board_view":"kanban",   # kanban | list
    "current_project":"all",
    "filter_status":"All","search":"",
    "expanded_task":None,"show_add_task":False,"edit_task_id":None,
    "active_timer":None,"timer_start":None,
}
for k,v in _DEF.items():
    if k not in st.session_state: st.session_state[k] = v

# ── AUTH PAGE ─────────────────────────────────────────────────────────────────
def show_auth():
    _, col, _ = st.columns([1,2,1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:36px 0 20px">
            <div style="font-size:52px">✅</div>
            <h2 style="margin:8px 0 4px;font-size:26px;color:#172b4d">TaskFlow Pro</h2>
            <p style="color:#5e6c84;font-size:14px;margin:0">Jira-style project task manager</p>
        </div>""", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔐 Sign In", "📝 Create Account"])
        with tab1:
            uname = st.text_input("Username", key="li_u", placeholder="Your username")
            pw    = st.text_input("Password", type="password", key="li_p", placeholder="Your password")
            st.markdown("")
            if st.button("Sign In →", type="primary", use_container_width=True):
                u = db_get_user(uname.strip().lower())
                if u and u["password_hash"] == hash_pw(pw):
                    st.session_state.logged_in = True
                    st.session_state.current_user = u
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        with tab2:
            dn = st.text_input("Your name",         key="rn", placeholder="e.g. Zeeshan Alam")
            un = st.text_input("Choose a username", key="ru", placeholder="lowercase, no spaces")
            p1 = st.text_input("Password",          key="rp", type="password", placeholder="Min 6 characters")
            p2 = st.text_input("Confirm password",  key="rc", type="password")
            st.markdown("")
            if st.button("Create Account →", type="primary", use_container_width=True):
                errs = []
                if not dn.strip():                  errs.append("Name is required.")
                if not un.strip():                  errs.append("Username is required.")
                if len(p1) < 6:                     errs.append("Password must be at least 6 characters.")
                if p1 != p2:                        errs.append("Passwords do not match.")
                if db_get_user(un.strip().lower()): errs.append("Username already taken.")
                for e in errs: st.error(e)
                if not errs:
                    u = db_create_user(un.strip().lower(), p1, dn.strip())
                    seed_projects(u["id"])
                    st.session_state.logged_in = True
                    st.session_state.current_user = u
                    st.rerun()

if not st.session_state.logged_in:
    show_auth()
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
user      = st.session_state.current_user
user_id   = user["id"]
projects  = db_get_projects(user_id)
all_tasks = db_get_tasks(user_id)

def get_proj(pid): return next((p for p in projects if p["id"]==pid), None)
def get_task(tid): return next((t for t in all_tasks if t["id"]==tid), None)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    initials = "".join(w[0].upper() for w in user.get("display_name","U").split()[:2])
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:10px 0 14px">
      <div style="width:36px;height:36px;border-radius:50%;background:#0052cc;color:#fff;
                  display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700">{initials}</div>
      <div>
        <div style="font-weight:700;font-size:14px;color:#fff">{user.get('display_name','User')}</div>
        <div style="font-size:11px;color:#8c9bab">@{user['username']}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#2c333a;margin:4px 0 10px">', unsafe_allow_html=True)

    def nav(label, view, proj=None):
        active = st.session_state.view==view and (proj is None or st.session_state.current_project==proj)
        if st.button(label, key=f"nav_{label}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.view = view
            if proj is not None: st.session_state.current_project = proj
            st.rerun()

    nav("🗂  All Tasks",    "board", "all")
    nav("📅  Today",         "board", "today")
    nav("📊  Daily Summary", "summary")

    st.markdown('<hr style="border-color:#2c333a;margin:10px 0">', unsafe_allow_html=True)
    st.markdown('<p style="font-size:11px;font-weight:700;color:#5e6c84;text-transform:uppercase;letter-spacing:.06em;margin:0 0 6px 4px">Projects</p>', unsafe_allow_html=True)

    for proj in projects:
        count  = sum(1 for t in all_tasks if t["project_id"]==proj["id"])
        active = st.session_state.current_project==proj["id"] and st.session_state.view=="board"
        c1, c2 = st.columns([5,1])
        with c1:
            if st.button(f"● {proj['name']}", key=f"pb_{proj['id']}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.current_project = proj["id"]
                st.session_state.view = "board"
                st.rerun()
        with c2:
            st.markdown(f'<div style="text-align:center;font-size:11px;color:#5e6c84;padding-top:8px">{count}</div>', unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#2c333a;margin:10px 0">', unsafe_allow_html=True)
    with st.expander("➕  New Project"):
        pn = st.text_input("Name", key="np_n", placeholder="Project name")
        pc = st.color_picker("Color", "#0052cc", key="np_c")
        if st.button("Create Project", type="primary", key="np_btn"):
            if pn.strip():
                db_add_project({"id":uid(),"user_id":user_id,"name":pn.strip(),"color":pc,"created_at":now_str()})
                st.rerun()

    st.markdown('<hr style="border-color:#2c333a;margin:10px 0">', unsafe_allow_html=True)
    if st.button("🚪  Sign out", use_container_width=True):
        for k,v in _DEF.items(): st.session_state[k] = v
        if "_jdb" in st.session_state: del st.session_state["_jdb"]
        st.rerun()

# ── MAIN HEADER ───────────────────────────────────────────────────────────────
if   st.session_state.view == "summary":              vt = "📊 Daily Summary"
elif st.session_state.current_project == "all":       vt = "🗂 All Tasks"
elif st.session_state.current_project == "today":     vt = "📅 Today"
else:
    _p = get_proj(st.session_state.current_project)
    vt = f"📁 {_p['name']}" if _p else "Tasks"

# Toolbar — fixed with explicit margin
st.markdown(f"## {vt}")
st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

col_search, col_csv, col_add = st.columns([4, 1, 1])
with col_search:
    st.session_state.search = st.text_input(
        "", value=st.session_state.search,
        placeholder="🔍 Search tasks by title or description...",
        label_visibility="collapsed", key="srch")
with col_csv:
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Task","Project","Status","Priority","Due","Assignee","Est Hrs","Time Logged","Subtasks Done","Total Subtasks","Comments"])
    for t in all_tasks:
        p=get_proj(t["project_id"]); subs=jl(t.get("subtasks")); coms=jl(t.get("comments"))
        w.writerow([t["title"], p["name"] if p else "", STATUS_LABELS.get(t["status"],""),
                    t["priority"], t.get("due",""), t.get("assignee",""), t.get("est_hours",0),
                    fmt_time(t.get("elapsed",0)), sum(1 for s in subs if s["done"]), len(subs),
                    " | ".join(c["text"] for c in coms)])
    st.download_button("⬇ Export CSV", buf.getvalue(), f"taskflow_{today_str()}.csv",
                       "text/csv", use_container_width=True)
with col_add:
    if st.button("➕ Add Task", type="primary", use_container_width=True):
        st.session_state.show_add_task = True
        st.session_state.edit_task_id  = None

# ── STATS BAR ─────────────────────────────────────────────────────────────────
st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
_ts  = sum(t.get("elapsed",0) or 0 for t in all_tasks)
_dc  = sum(1 for t in all_tasks if t["status"]=="done")
_ip  = sum(1 for t in all_tasks if t["status"]=="in-progress")
_bl  = sum(1 for t in all_tasks if t["status"]=="blocked")
_rv  = sum(1 for t in all_tasks if t["status"]=="review")
_td  = sum(1 for t in all_tasks if t["status"]=="todo")
_pct = round(_dc/len(all_tasks)*100) if all_tasks else 0

s1,s2,s3,s4,s5,s6,s7,s8 = st.columns(8)
s1.metric("Total",       len(all_tasks))
s2.metric("To Do",       _td)
s3.metric("In Progress", _ip)
s4.metric("In Review",   _rv)
s5.metric("Blocked",     _bl)
s6.metric("Done",        _dc)
s7.metric("Time Logged", fmt_time(_ts))
s8.metric("Complete",    f"{_pct}%")
if all_tasks: st.progress(_pct/100)

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
st.divider()

# ── DAILY SUMMARY ─────────────────────────────────────────────────────────────
if st.session_state.view == "summary":
    st.markdown(f"### 📅 {date.today().strftime('%A, %d %B %Y')}")
    tt = [t for t in all_tasks if t.get("due")==today_str()]
    _td2 = sum(1 for t in tt if t["status"]=="done")
    ta,tb,tc,te = st.columns(4)
    ta.metric("Due Today", len(tt)); tb.metric("Completed", _td2)
    tc.metric("Blocked", sum(1 for t in tt if t["status"]=="blocked"))
    te.metric("Logged Today", fmt_time(sum(t.get("elapsed",0) or 0 for t in tt)))
    if tt: st.progress(_td2/len(tt))
    st.divider()

    for proj in projects:
        pt = [t for t in all_tasks if t["project_id"]==proj["id"]]
        if not pt: continue
        pd = sum(1 for t in pt if t["status"]=="done")
        ps = sum(t.get("elapsed",0) or 0 for t in pt)
        pp = round(pd/len(pt)*100)

        st.markdown(f"""<div class="sum-proj-card">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
                <span style="width:12px;height:12px;border-radius:50%;background:{proj['color']};display:inline-block"></span>
                <strong style="font-size:16px;color:#172b4d">{proj['name']}</strong>
                <span style="color:#5e6c84;font-size:13px;margin-left:auto">{fmt_time(ps)} logged &nbsp;·&nbsp; {pd}/{len(pt)} done</span>
            </div>""", unsafe_allow_html=True)
        st.progress(pp/100)
        st.markdown(f'<div style="font-size:12px;color:#5e6c84;margin:2px 0 10px">{pp}% complete</div>', unsafe_allow_html=True)

        for t in pt:
            subs      = jl(t.get("subtasks"))
            sub_done  = sum(1 for s in subs if s["done"])
            sub_span  = f'<span style="font-size:12px;color:#5e6c84">&#9745; {sub_done}/{len(subs)}</span>' if subs else ""
            t_elapsed = fmt_time(t.get("elapsed", 0) or 0)
            t_icon    = STATUS_ICONS.get(t["status"], "&#x2B1C;")
            row_html  = (
                '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f0f1f4;font-size:14px">'
                + f'<span style="font-size:16px">{t_icon}</span>'
                + f'<span style="flex:1;font-weight:500;color:#172b4d">{t["title"]}</span>'
                + sub_span
                + f'<span style="font-family:monospace;font-size:12px;color:#5e6c84;background:#f0f1f4;padding:2px 8px;border-radius:4px">{t_elapsed}</span>'
                + badge_html(t["status"])
                + '</div>'
            )
            st.markdown(row_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    st.stop()

# ── ADD / EDIT TASK FORM ──────────────────────────────────────────────────────
if st.session_state.show_add_task or st.session_state.edit_task_id:
    et = get_task(st.session_state.edit_task_id) if st.session_state.edit_task_id else None
    pnames = [p["name"] for p in projects]; pids = [p["id"] for p in projects]

    with st.expander(f"{'✏️ Edit Task' if et else '➕ New Task'}", expanded=True):
        f1,f2 = st.columns([3,1])
        with f1: t_title = st.text_input("Task title *", value=et["title"] if et else "", placeholder="Summarize this task clearly...")
        with f2:
            dpi = pids.index(et["project_id"]) if et and et.get("project_id") in pids else 0
            t_proj = st.selectbox("Project", pnames, index=dpi)

        f3,f4,f5 = st.columns(3)
        with f3: t_pri = st.selectbox("Priority", ["high","medium","low"],
                                      index=["high","medium","low"].index(et["priority"]) if et else 1)
        with f4: t_st  = st.selectbox("Status", list(STATUS_LABELS.keys()),
                                      format_func=lambda x: STATUS_LABELS[x],
                                      index=STATUS_ORDER.index(et["status"]) if et else 0)
        with f5:
            dv = date.fromisoformat(et["due"]) if et and et.get("due") else date.today()
            t_due = st.date_input("Due date", value=dv)

        f6,f7 = st.columns(2)
        with f6: t_asn = st.text_input("Assignee", value=et.get("assignee","") if et else "")
        with f7: t_est = st.number_input("Est. hours", min_value=0.0, step=0.5,
                                         value=float(et.get("est_hours",0)) if et else 0.0)
        t_desc = st.text_area("Description", value=et.get("desc","") if et else "", height=70,
                              placeholder="Add more details about this task...")

        bc1,bc2,_ = st.columns([1,1,5])
        with bc1:
            if st.button("💾 Save Task", type="primary"):
                if t_title.strip():
                    pid = pids[pnames.index(t_proj)]
                    if et:
                        db_update_task(et["id"],{"title":t_title.strip(),"project_id":pid,"priority":t_pri,
                            "status":t_st,"due":str(t_due),"assignee":t_asn,"est_hours":t_est,"desc":t_desc})
                    else:
                        db_add_task({"id":uid(),"user_id":user_id,"title":t_title.strip(),"project_id":pid,
                            "priority":t_pri,"status":t_st,"due":str(t_due),"assignee":t_asn,"est_hours":t_est,
                            "desc":t_desc,"elapsed":0,"comments":[],"subtasks":[],"sort_order":len(all_tasks)})
                    st.session_state.show_add_task=False; st.session_state.edit_task_id=None
                    st.rerun()
        with bc2:
            if st.button("✕ Cancel"):
                st.session_state.show_add_task=False; st.session_state.edit_task_id=None; st.rerun()

# ── VIEW SWITCHER ─────────────────────────────────────────────────────────────
vcol1, vcol2, _, vf1 = st.columns([1, 1, 3, 3])
with vcol1:
    if st.button("🗃 Board", type="primary" if st.session_state.board_view=="kanban" else "secondary", use_container_width=True):
        st.session_state.board_view = "kanban"; st.rerun()
with vcol2:
    if st.button("☰ List", type="primary" if st.session_state.board_view=="list" else "secondary", use_container_width=True):
        st.session_state.board_view = "list"; st.rerun()
with vf1:
    f_opts = ["All","To Do","In Progress","In Review","Blocked","Done","Due Today"]
    st.session_state.filter_status = st.selectbox("Filter by status", f_opts,
        index=f_opts.index(st.session_state.filter_status), label_visibility="collapsed")

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

# ── FILTER LOGIC ──────────────────────────────────────────────────────────────
def apply_filters(tasks):
    out = []
    for t in tasks:
        cp = st.session_state.current_project
        if   cp == "today" and t.get("due") != today_str():                  continue
        elif cp not in ("all","today") and t["project_id"] != cp:            continue
        f = st.session_state.filter_status
        if f=="To Do"       and t["status"]!="todo":        continue
        if f=="In Progress" and t["status"]!="in-progress": continue
        if f=="In Review"   and t["status"]!="review":      continue
        if f=="Blocked"     and t["status"]!="blocked":     continue
        if f=="Done"        and t["status"]!="done":        continue
        if f=="Due Today"   and t.get("due")!=today_str():  continue
        q = st.session_state.search.lower()
        if q and q not in t["title"].lower() and q not in (t.get("desc","") or "").lower(): continue
        out.append(t)
    return out

filtered = apply_filters(all_tasks)

if not filtered:
    st.info("No tasks found. Add one with **➕ Add Task** or adjust the filter.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# BOARD VIEW — Kanban columns
# ═══════════════════════════════════════════════════════════════════════════════
def render_task_detail(t):
    """Subtasks + comments expander for a task."""
    subs     = jl(t.get("subtasks"))
    coms     = jl(t.get("comments"))
    sub_done = sum(1 for s in subs if s["done"])
    sub_total= len(subs)
    elapsed  = int(t.get("elapsed",0) or 0)
    is_run   = st.session_state.active_timer == t["id"]

    with st.expander(f"📋 {t['title']} — Details", expanded=True):
        proj = get_proj(t["project_id"])

        # Header info
        hc1,hc2,hc3,hc4 = st.columns(4)
        hc1.markdown(f"**Status**<br>{badge_html(t['status'])}", unsafe_allow_html=True)
        hc2.markdown(f"**Priority**<br><span style='font-size:14px'>{PRI_ICONS.get(t['priority'],'')} {t['priority'].capitalize()}</span>", unsafe_allow_html=True)
        hc3.markdown(f"**Project**<br><span style='font-size:14px'>📁 {proj['name'] if proj else '—'}</span>", unsafe_allow_html=True)
        hc4.markdown(f"**Due**<br><span style='font-size:14px'>📅 {t.get('due','—')}</span>", unsafe_allow_html=True)

        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

        if t.get("desc"):
            st.markdown(f'<div style="background:#f4f5f7;border-radius:6px;padding:12px;font-size:15px;color:#172b4d;margin-bottom:10px">{t["desc"]}</div>', unsafe_allow_html=True)

        # Timer
        tc1,tc2 = st.columns([3,1])
        with tc1:
            run_class = "running" if is_run else ""
            st.markdown(f'<span class="timer-pill {run_class}">⏱ {fmt_time(elapsed)}{"  ⬤" if is_run else ""}</span>', unsafe_allow_html=True)
        with tc2:
            if is_run:
                if st.button("⏹ Stop Timer", key=f"stop_{t['id']}"):
                    if st.session_state.timer_start:
                        added = int((datetime.now()-st.session_state.timer_start).total_seconds())
                        db_update_task(t["id"],{"elapsed":elapsed+added})
                    st.session_state.active_timer=None; st.session_state.timer_start=None; st.rerun()
            else:
                if st.button("▶ Start Timer", key=f"play_{t['id']}", type="primary"):
                    if st.session_state.active_timer:
                        prev=get_task(st.session_state.active_timer)
                        if prev and st.session_state.timer_start:
                            added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                            db_update_task(prev["id"],{"elapsed":(prev.get("elapsed",0) or 0)+added})
                    st.session_state.active_timer=t["id"]; st.session_state.timer_start=datetime.now()
                    if t["status"]=="todo": db_update_task(t["id"],{"status":"in-progress"})
                    st.rerun()

        # Quick status change
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        new_st = st.selectbox("Change status", STATUS_ORDER,
                              index=STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 0,
                              format_func=lambda x: f"{STATUS_ICONS.get(x,'')} {STATUS_LABELS.get(x,'')}",
                              key=f"qs_{t['id']}")
        if new_st != t["status"]:
            db_update_task(t["id"],{"status":new_st}); st.rerun()

        st.divider()

        # Subtasks
        st.markdown(f"**☑ Subtasks** {'— '+str(sub_done)+'/'+str(sub_total)+' done' if sub_total else ''}")
        if sub_total: st.progress(sub_done/sub_total)

        changed = False
        for s in subs:
            sc1,sc2,sc3 = st.columns([1,8,1])
            with sc1:
                chk = st.checkbox("",value=s["done"],key=f"s_{t['id']}_{s['id']}",label_visibility="collapsed")
                if chk != s["done"]: s["done"]=chk; changed=True
            with sc2:
                sty = "color:#5e6c84;text-decoration:line-through" if s["done"] else "font-size:14px;color:#172b4d"
                st.markdown(f'<span style="{sty}">{s["title"]}</span>', unsafe_allow_html=True)
            with sc3:
                if st.button("✕",key=f"ds_{t['id']}_{s['id']}",help="Delete subtask"):
                    subs=[x for x in subs if x["id"]!=s["id"]]; db_update_task(t["id"],{"subtasks":subs}); st.rerun()
        if changed: db_update_task(t["id"],{"subtasks":subs}); st.rerun()

        ns1,ns2 = st.columns([5,1])
        with ns1: nsub=st.text_input("",placeholder="Add a subtask...",key=f"nsub_{t['id']}",label_visibility="collapsed")
        with ns2:
            if st.button("Add",key=f"asub_{t['id']}"):
                if nsub.strip():
                    subs.append({"id":uid(),"title":nsub.strip(),"done":False})
                    db_update_task(t["id"],{"subtasks":subs}); st.rerun()

        st.divider()

        # Comments
        st.markdown("**💬 Comments**")
        for c in coms:
            st.markdown(f"""<div class="c-bubble">
                <span class="c-author">👤 {t.get('assignee') or 'User'}</span>
                <span class="c-time">{c.get('time','')}</span>
                <div class="c-text">{c['text']}</div>
            </div>""", unsafe_allow_html=True)

        nc1,nc2 = st.columns([5,1])
        with nc1: nc=st.text_input("",placeholder="Write a comment...",key=f"nc_{t['id']}",label_visibility="collapsed")
        with nc2:
            if st.button("Post",key=f"pc_{t['id']}",type="primary"):
                if nc.strip():
                    coms.append({"id":uid(),"text":nc.strip(),"time":now_str()})
                    db_update_task(t["id"],{"comments":coms}); st.rerun()

        # Edit / Delete row
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        da,db_,dc = st.columns([2,2,5])
        with da:
            if st.button("✏️ Edit Task", key=f"ed_{t['id']}", use_container_width=True):
                st.session_state.edit_task_id=t["id"]; st.session_state.show_add_task=False; st.rerun()
        with db_:
            if st.button("🗑 Delete", key=f"dl_{t['id']}", use_container_width=True):
                db_delete_task(t["id"])
                if st.session_state.expanded_task==t["id"]: st.session_state.expanded_task=None
                st.rerun()


if st.session_state.board_view == "kanban":
    # ── KANBAN BOARD ──────────────────────────────────────────────────────────
    cols = st.columns(len(KANBAN_COLS))
    for col_idx, (status_key, status_label, status_color) in enumerate(KANBAN_COLS):
        col_tasks = [t for t in filtered if t["status"]==status_key]
        with cols[col_idx]:
            # Column header
            st.markdown(f"""
            <div style="background:{status_color}18;border:1px solid {status_color}33;border-radius:8px;
                        padding:8px 12px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between">
                <span style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:{status_color}">{status_label}</span>
                <span style="background:{status_color};color:#fff;border-radius:10px;padding:1px 9px;font-size:11px;font-weight:700">{len(col_tasks)}</span>
            </div>""", unsafe_allow_html=True)

            for t in col_tasks:
                proj     = get_proj(t["project_id"])
                subs     = jl(t.get("subtasks"))
                coms     = jl(t.get("comments"))
                sub_done = sum(1 for s in subs if s["done"])
                elapsed  = int(t.get("elapsed",0) or 0)
                is_run   = st.session_state.active_timer == t["id"]
                is_exp   = st.session_state.expanded_task == t["id"]

                # Pre-compute all conditional HTML fragments
                pri_col   = PRI_COLORS.get(t["priority"], "#5e6c84")
                due_html  = f'<span style="font-size:12px;color:#5e6c84">&nbsp;· 📅 {t["due"]}</span>' if t.get("due") else ""
                sub_html  = f'<span style="font-size:12px;color:#5e6c84">&nbsp;· ☑ {sub_done}/{len(subs)}</span>' if subs else ""
                com_html  = f'<span style="font-size:12px;color:#5e6c84">&nbsp;· 💬 {len(coms)}</span>' if coms else ""
                run_dot   = "&nbsp;⬤" if is_run else ""
                proj_name = proj["name"] if proj else "—"
                tmr_str   = fmt_time(elapsed)

                # Card — all variables pre-computed, no ternary inside f-string
                card_html = (
                    f'<div class="k-card" style="border-left:3px solid {status_color}">'
                    f'<div class="k-card-title">{t["title"]}</div>'
                    f'<div class="k-card-meta">'
                    f'<span class="pri-dot" style="background:{pri_col}"></span>'
                    f'<span style="font-size:12px;color:#5e6c84">{t["priority"].capitalize()}</span>'
                    f'{due_html}{sub_html}{com_html}'
                    f'</div>'
                    f'<div class="k-card-footer">'
                    f'<span style="font-size:12px;color:#5e6c84;background:#f0f1f4;padding:2px 8px;border-radius:4px;font-family:monospace">⏱ {tmr_str}{run_dot}</span>'
                    f'<span style="font-size:12px;color:#5e6c84">📁 {proj_name}</span>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

                # Action buttons under card
                ba,bb,bc = st.columns(3)
                with ba:
                    lbl = "⏹" if is_run else "▶"
                    if st.button(lbl, key=f"tmr_{t['id']}", use_container_width=True, help="Timer"):
                        if is_run:
                            if st.session_state.timer_start:
                                added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                                db_update_task(t["id"],{"elapsed":elapsed+added})
                            st.session_state.active_timer=None; st.session_state.timer_start=None
                        else:
                            if st.session_state.active_timer:
                                prev=get_task(st.session_state.active_timer)
                                if prev and st.session_state.timer_start:
                                    added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                                    db_update_task(prev["id"],{"elapsed":(prev.get("elapsed",0) or 0)+added})
                            st.session_state.active_timer=t["id"]; st.session_state.timer_start=datetime.now()
                            if t["status"]=="todo": db_update_task(t["id"],{"status":"in-progress"})
                        st.rerun()
                with bb:
                    if st.button("💬", key=f"exp_{t['id']}", use_container_width=True, help="Open details"):
                        st.session_state.expanded_task = None if is_exp else t["id"]; st.rerun()
                with bc:
                    if st.button("✏️", key=f"ed_{t['id']}", use_container_width=True, help="Edit"):
                        st.session_state.edit_task_id=t["id"]; st.session_state.show_add_task=False; st.rerun()

                st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

            # Show detail panel below column if expanded task belongs here
            exp_t = get_task(st.session_state.expanded_task) if st.session_state.expanded_task else None
            if exp_t and exp_t.get("status") == status_key and exp_t in filtered:
                render_task_detail(exp_t)

else:
    # ═══════════════════════════════════════════════════════════════════════════
    # LIST VIEW — Jira-style table
    # ═══════════════════════════════════════════════════════════════════════════
    filtered_sorted = sorted(filtered, key=lambda t: (
        STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 99,
        t.get("due","9999"), ["high","medium","low"].index(t["priority"]) if t["priority"] in ["high","medium","low"] else 99
    ))

    # Table header
    st.markdown("""
    <table class="list-table">
      <thead>
        <tr>
          <th style="width:32px"></th>
          <th>Summary</th>
          <th>Status</th>
          <th>Priority</th>
          <th>Project</th>
          <th>Assignee</th>
          <th>Due Date</th>
          <th>Time</th>
          <th>Subtasks</th>
          <th style="width:90px">Actions</th>
        </tr>
      </thead>
      <tbody>""", unsafe_allow_html=True)

    for t in filtered_sorted:
        proj     = get_proj(t["project_id"])
        subs     = jl(t.get("subtasks"))
        coms     = jl(t.get("comments"))
        sub_done = sum(1 for s in subs if s["done"])
        elapsed  = int(t.get("elapsed",0) or 0)
        is_run   = st.session_state.active_timer == t["id"]
        st_icon  = STATUS_ICONS.get(t["status"],"")
        pc       = proj["color"] if proj else "#5e6c84"
        pn       = proj["name"] if proj else "—"
        run_ind  = ' <span style="color:#0052cc;font-size:10px">&#x2B24;</span>' if is_run else ""
        timer_cls = "timer-pill running" if is_run else "timer-pill"
        title_style = "text-decoration:line-through;color:#5e6c84" if t["status"]=="done" else "color:#172b4d"
        pri_dot  = f'<span class="pri-dot" style="background:{PRI_COLORS.get(t["priority"],"#5e6c84")}"></span>'
        due_cell = f'&#128197; {t["due"]}' if t.get("due") else "&#8212;"
        asn_cell = f'&#128100; {t["assignee"]}' if t.get("assignee") else "&#8212;"
        tmr_str  = fmt_time(elapsed)

        # Subtask mini progress bar — pre-computed
        if subs:
            pct_sub = round(sub_done / len(subs) * 100)
            sub_bar = (
                f'<div style="background:#dfe1e6;border-radius:3px;height:5px;width:56px;'
                f'display:inline-block;vertical-align:middle;margin-right:5px">'
                f'<div style="background:#0052cc;height:100%;border-radius:3px;width:{pct_sub}%"></div>'
                f'</div> {sub_done}/{len(subs)}'
            )
        else:
            sub_bar = "&#8212;"

        # Description snippet — pre-computed
        if t.get("desc"):
            desc_snip = t["desc"][:80] + ("..." if len(t["desc"]) > 80 else "")
            desc_html = f'<div class="task-desc-cell">{desc_snip}</div>'
        else:
            desc_html = ""

        row_html = (
            f'<tr>'
            f'<td style="text-align:center;font-size:16px">{st_icon}</td>'
            f'<td><div class="task-title-cell" style="{title_style}">{t["title"]}</div>{desc_html}</td>'
            f'<td>{badge_html(t["status"])}</td>'
            f'<td><span style="font-size:14px">{pri_dot}{t["priority"].capitalize()}</span></td>'
            f'<td><span style="font-size:13px;color:{pc};font-weight:600">&#9679; {pn}</span></td>'
            f'<td><span style="font-size:14px">{asn_cell}</span></td>'
            f'<td><span style="font-size:14px;color:#172b4d">{due_cell}</span></td>'
            f'<td><span class="{timer_cls}">&#9201; {tmr_str}{run_ind}</span></td>'
            f'<td><span style="font-size:13px">{sub_bar}</span></td>'
            f'<td></td>'
            f'</tr>'
        )
        st.markdown(row_html, unsafe_allow_html=True)

    st.markdown("</tbody></table>", unsafe_allow_html=True)

    # Action buttons for list view (below table, per task)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Task Actions</div>', unsafe_allow_html=True)

    for t in filtered_sorted:
        elapsed  = int(t.get("elapsed",0) or 0)
        is_run   = st.session_state.active_timer == t["id"]
        is_exp   = st.session_state.expanded_task == t["id"]

        with st.container():
            la,lb,lc,ld,le,_ = st.columns([3,1,1,1,1,3])
            with la:
                st.markdown(f'<span style="font-size:14px;font-weight:600;color:#172b4d">{t["title"]}</span>', unsafe_allow_html=True)
            with lb:
                ns = st.selectbox("", STATUS_ORDER,
                                  index=STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 0,
                                  format_func=lambda x: STATUS_ICONS.get(x,""),
                                  key=f"lqs_{t['id']}", label_visibility="collapsed")
                if ns != t["status"]: db_update_task(t["id"],{"status":ns}); st.rerun()
            with lc:
                tmr_lbl = "⏹" if is_run else "▶"
                if st.button(tmr_lbl, key=f"ltmr_{t['id']}", use_container_width=True):
                    if is_run:
                        if st.session_state.timer_start:
                            added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                            db_update_task(t["id"],{"elapsed":elapsed+added})
                        st.session_state.active_timer=None; st.session_state.timer_start=None
                    else:
                        if st.session_state.active_timer:
                            prev=get_task(st.session_state.active_timer)
                            if prev and st.session_state.timer_start:
                                added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                                db_update_task(prev["id"],{"elapsed":(prev.get("elapsed",0) or 0)+added})
                        st.session_state.active_timer=t["id"]; st.session_state.timer_start=datetime.now()
                        if t["status"]=="todo": db_update_task(t["id"],{"status":"in-progress"})
                    st.rerun()
            with ld:
                if st.button("💬", key=f"lexp_{t['id']}", use_container_width=True):
                    st.session_state.expanded_task = None if is_exp else t["id"]; st.rerun()
            with le:
                if st.button("✏️", key=f"led_{t['id']}", use_container_width=True):
                    st.session_state.edit_task_id=t["id"]; st.session_state.show_add_task=False; st.rerun()

        if is_exp:
            render_task_detail(t)

        st.markdown('<hr style="border:none;border-top:1px solid #f0f1f4;margin:4px 0">', unsafe_allow_html=True)
