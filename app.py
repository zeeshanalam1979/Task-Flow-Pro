"""
TaskFlow Pro – Streamlit Task Manager
With login/password auth + Supabase persistent storage
"""

import streamlit as st
import hashlib
import uuid
import csv
import io
from datetime import datetime, date

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TaskFlow Pro",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Try Supabase (graceful fallback to session-only if not configured) ─────────
try:
    from supabase import create_client, Client
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        DB_MODE = "supabase"
    else:
        DB_MODE = "session"
except Exception:
    DB_MODE = "session"

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f0f2f6; }
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
.block-container { padding-top: 1.2rem; }
[data-testid="metric-container"] {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 10px 14px;
}
.task-card {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 12px 14px; margin-bottom: 6px;
}
.section-hdr {
    font-size: 11px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: .06em;
    padding: 8px 0 5px; border-bottom: 1px solid #e2e8f0; margin-bottom: 6px;
}
.badge {
    display:inline-block; padding:2px 8px; border-radius:20px;
    font-size:11px; font-weight:500; margin-right:3px;
}
.b-todo{background:#f1f5f9;color:#64748b}
.b-inprogress{background:#fef3c7;color:#92400e}
.b-review{background:#ede9fe;color:#5b21b6}
.b-blocked{background:#fee2e2;color:#991b1b}
.b-done{background:#dcfce7;color:#166534}
.b-high{background:#fee2e2;color:#991b1b}
.b-medium{background:#fef3c7;color:#92400e}
.b-low{background:#dcfce7;color:#166534}
.c-bubble {
    background:#f8fafc; border:1px solid #e2e8f0;
    border-radius:8px; padding:8px 12px; margin-bottom:5px; font-size:13px;
}
.login-card {
    max-width:400px; margin:60px auto; background:#fff;
    border:1px solid #e2e8f0; border-radius:14px; padding:32px;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def uid(): return str(uuid.uuid4())[:8]
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def today_str(): return str(date.today())
def now_str(): return datetime.now().strftime("%d %b %Y %H:%M")
def fmt_time(secs):
    secs = int(secs or 0)
    if secs <= 0: return "0s"
    h, r = divmod(secs, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m" if h else (f"{m}m {s}s" if m else f"{s}s")

STATUS_LABELS = {"todo":"To Do","in-progress":"In Progress","review":"In Review","blocked":"Blocked","done":"Done"}
STATUS_ICONS  = {"todo":"⬜","in-progress":"🔄","review":"🔍","blocked":"🚫","done":"✅"}
PRI_ICONS     = {"high":"🔴","medium":"🟡","low":"🟢"}
STATUS_ORDER  = ["todo","in-progress","review","blocked","done"]
STATUS_COLORS = {"todo":"#94a3b8","in-progress":"#f59e0b","review":"#7c3aed","blocked":"#ef4444","done":"#22c55e"}

# ── Database layer ─────────────────────────────────────────────────────────────
# All DB calls isolated here — swap backend without touching UI code

def db_get_user(username):
    if DB_MODE == "supabase":
        r = supabase.table("users").select("*").eq("username", username).execute()
        return r.data[0] if r.data else None
    else:
        return st.session_state.get("_users", {}).get(username)

def db_create_user(username, password, display_name):
    user = {"id": uid(), "username": username, "password_hash": hash_pw(password),
            "display_name": display_name, "created_at": now_str()}
    if DB_MODE == "supabase":
        supabase.table("users").insert(user).execute()
    else:
        if "_users" not in st.session_state: st.session_state["_users"] = {}
        st.session_state["_users"][username] = user
    return user

def db_get_projects(user_id):
    if DB_MODE == "supabase":
        r = supabase.table("projects").select("*").eq("user_id", user_id).order("created_at").execute()
        return r.data
    else:
        return [p for p in st.session_state.get("_projects", []) if p["user_id"] == user_id]

def db_add_project(proj):
    if DB_MODE == "supabase":
        supabase.table("projects").insert(proj).execute()
    else:
        if "_projects" not in st.session_state: st.session_state["_projects"] = []
        st.session_state["_projects"].append(proj)

def db_delete_project(proj_id):
    if DB_MODE == "supabase":
        supabase.table("projects").delete().eq("id", proj_id).execute()
        supabase.table("tasks").delete().eq("project_id", proj_id).execute()
    else:
        st.session_state["_projects"] = [p for p in st.session_state.get("_projects",[]) if p["id"] != proj_id]
        st.session_state["_tasks"] = [t for t in st.session_state.get("_tasks",[]) if t["project_id"] != proj_id]

def db_get_tasks(user_id, project_id=None):
    if DB_MODE == "supabase":
        q = supabase.table("tasks").select("*").eq("user_id", user_id)
        if project_id and project_id not in ("all","today"):
            q = q.eq("project_id", project_id)
        r = q.order("sort_order").execute()
        return r.data
    else:
        tasks = [t for t in st.session_state.get("_tasks",[]) if t["user_id"] == user_id]
        if project_id and project_id not in ("all","today"):
            tasks = [t for t in tasks if t["project_id"] == project_id]
        return tasks

def db_add_task(task):
    if DB_MODE == "supabase":
        supabase.table("tasks").insert(task).execute()
    else:
        if "_tasks" not in st.session_state: st.session_state["_tasks"] = []
        st.session_state["_tasks"].append(task)

def db_update_task(task_id, updates):
    if DB_MODE == "supabase":
        supabase.table("tasks").update(updates).eq("id", task_id).execute()
    else:
        for t in st.session_state.get("_tasks",[]):
            if t["id"] == task_id:
                t.update(updates)

def db_delete_task(task_id):
    if DB_MODE == "supabase":
        supabase.table("tasks").delete().eq("id", task_id).execute()
    else:
        st.session_state["_tasks"] = [t for t in st.session_state.get("_tasks",[]) if t["id"] != task_id]

import json as _json

def task_comments(t): 
    c = t.get("comments", [])
    return _json.loads(c) if isinstance(c, str) else (c or [])

def task_subtasks(t):
    s = t.get("subtasks", [])
    return _json.loads(s) if isinstance(s, str) else (s or [])

# ── Session init ───────────────────────────────────────────────────────────────
for k, v in {
    "logged_in": False, "current_user": None,
    "view": "board", "current_project": "all",
    "filter_status": "All", "search": "",
    "expanded_task": None, "show_add_task": False, "edit_task_id": None,
    "active_timer": None, "timer_start": None,
    "auth_page": "login",
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Auth pages ─────────────────────────────────────────────────────────────────
def show_login():
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("## ✅ TaskFlow Pro")
    st.caption("Project Task Manager — Sign in to continue")
    st.divider()

    tab1, tab2 = st.tabs(["🔐 Sign In", "📝 Create Account"])

    with tab1:
        uname = st.text_input("Username", key="li_user")
        pw    = st.text_input("Password", type="password", key="li_pw")
        if st.button("Sign In", type="primary", use_container_width=True):
            user = db_get_user(uname.strip().lower())
            if user and user["password_hash"] == hash_pw(pw):
                st.session_state.logged_in = True
                st.session_state.current_user = user
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        dname  = st.text_input("Display name", key="reg_name")
        uname2 = st.text_input("Username", key="reg_user")
        pw2    = st.text_input("Password (min 6 chars)", type="password", key="reg_pw")
        pw2c   = st.text_input("Confirm password", type="password", key="reg_pw2")
        if st.button("Create Account", type="primary", use_container_width=True):
            if len(pw2) < 6:
                st.error("Password must be at least 6 characters.")
            elif pw2 != pw2c:
                st.error("Passwords do not match.")
            elif not uname2.strip():
                st.error("Username is required.")
            elif db_get_user(uname2.strip().lower()):
                st.error("Username already taken.")
            else:
                user = db_create_user(uname2.strip().lower(), pw2, dname.strip() or uname2)
                # Seed default projects for new users
                for p in [
                    {"id": uid(), "user_id": user["id"], "name": "Cloud Wholesale SEO", "color": "#1D9E75", "created_at": now_str()},
                    {"id": uid(), "user_id": user["id"], "name": "iPuff24 Shopify SEO",  "color": "#534AB7", "created_at": now_str()},
                    {"id": uid(), "user_id": user["id"], "name": "General",               "color": "#378ADD", "created_at": now_str()},
                ]:
                    db_add_project(p)
                st.session_state.logged_in = True
                st.session_state.current_user = user
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ── Guard ──────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login()
    st.stop()

user    = st.session_state.current_user
user_id = user["id"]

# ── Load data ──────────────────────────────────────────────────────────────────
projects = db_get_projects(user_id)
all_tasks = db_get_tasks(user_id)

def get_proj(pid): return next((p for p in projects if p["id"] == pid), None)
def get_task(tid): return next((t for t in all_tasks if t["id"] == tid), None)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### ✅ TaskFlow Pro")
    st.caption(f"👤 {user.get('display_name', user['username'])}")
    if st.button("🚪 Sign out", use_container_width=True):
        for k in ["logged_in","current_user","view","current_project","filter_status",
                  "search","expanded_task","show_add_task","edit_task_id",
                  "active_timer","timer_start"]:
            st.session_state[k] = False if k=="logged_in" else None if "task" in k or "timer" in k else ("board" if k=="view" else "all" if k=="current_project" else "All" if k=="filter_status" else "")
        st.rerun()

    st.divider()

    def nav_btn(label, view, proj):
        active = st.session_state.view == view and (proj is None or st.session_state.current_project == proj)
        if st.button(label, use_container_width=True, type="primary" if active else "secondary"):
            st.session_state.view = view
            if proj is not None: st.session_state.current_project = proj
            st.rerun()

    nav_btn("🗂 All Tasks",     "board",   "all")
    nav_btn("📅 Today",          "board",   "today")
    nav_btn("📊 Daily Summary",  "summary", None)

    st.divider()
    st.markdown("**Projects**")

    for proj in projects:
        count = sum(1 for t in all_tasks if t["project_id"] == proj["id"])
        is_active = st.session_state.current_project == proj["id"] and st.session_state.view == "board"
        c1, c2 = st.columns([5, 1])
        with c1:
            if st.button(proj["name"], key=f"p_{proj['id']}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.current_project = proj["id"]
                st.session_state.view = "board"
                st.rerun()
        with c2:
            st.caption(str(count))

    st.divider()
    with st.expander("➕ New Project"):
        pname  = st.text_input("Name", key="np_name", placeholder="Project name")
        pcolor = st.color_picker("Color", "#1D9E75", key="np_color")
        if st.button("Create", type="primary", key="np_save"):
            if pname.strip():
                db_add_project({"id": uid(), "user_id": user_id, "name": pname.strip(),
                                "color": pcolor, "created_at": now_str()})
                st.rerun()

    if DB_MODE == "session":
        st.warning("⚠️ Running in demo mode.\nData resets on refresh.\nAdd Supabase credentials to persist data.", icon="⚠️")
    else:
        st.success("☁️ Cloud sync active", icon="✅")

# ── Title row ─────────────────────────────────────────────────────────────────
if st.session_state.view == "summary":
    view_title = "📊 Daily Summary"
elif st.session_state.current_project == "all":
    view_title = "🗂 All Tasks"
elif st.session_state.current_project == "today":
    view_title = "📅 Today"
else:
    p = get_proj(st.session_state.current_project)
    view_title = f"📁 {p['name']}" if p else "Tasks"

ct, cs, ccsv, cadd = st.columns([3, 3, 1, 1])
with ct: st.markdown(f"## {view_title}")
with cs:
    st.session_state.search = st.text_input("", placeholder="🔍 Search tasks...", label_visibility="collapsed", key="search_box")

# CSV export
with ccsv:
    exp_tasks = all_tasks
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Task","Project","Status","Priority","Due","Assignee","Est Hrs","Time Logged","Subtasks Done","Subtasks Total","Comments"])
    for t in exp_tasks:
        p = get_proj(t["project_id"])
        subs = task_subtasks(t)
        coms = task_comments(t)
        w.writerow([t["title"], p["name"] if p else "", STATUS_LABELS.get(t["status"],""),
                    t["priority"], t.get("due",""), t.get("assignee",""),
                    t.get("est_hours",0), fmt_time(t.get("elapsed",0)),
                    sum(1 for s in subs if s["done"]), len(subs),
                    " | ".join(c["text"] for c in coms)])
    st.download_button("⬇ CSV", buf.getvalue(), f"taskflow_{today_str()}.csv", "text/csv", use_container_width=True)

with cadd:
    if st.button("➕ Task", type="primary", use_container_width=True):
        st.session_state.show_add_task = True
        st.session_state.edit_task_id = None

# ── Stats ─────────────────────────────────────────────────────────────────────
vis_tasks = all_tasks
total_secs = sum(t.get("elapsed",0) or 0 for t in vis_tasks)
done_c  = sum(1 for t in vis_tasks if t["status"] == "done")
inpr_c  = sum(1 for t in vis_tasks if t["status"] == "in-progress")
blk_c   = sum(1 for t in vis_tasks if t["status"] == "blocked")
rev_c   = sum(1 for t in vis_tasks if t["status"] == "review")
pct     = round(done_c / len(vis_tasks) * 100) if vis_tasks else 0

s1,s2,s3,s4,s5,s6,s7 = st.columns(7)
s1.metric("Total",       len(vis_tasks))
s2.metric("In Progress", inpr_c)
s3.metric("In Review",   rev_c)
s4.metric("Blocked",     blk_c)
s5.metric("Done",        done_c)
s6.metric("Time Logged", fmt_time(total_secs))
s7.metric("Complete",    f"{pct}%")
if vis_tasks: st.progress(pct/100)
st.divider()

# ── Daily Summary ─────────────────────────────────────────────────────────────
if st.session_state.view == "summary":
    st.markdown(f"### 📅 {date.today().strftime('%A, %d %B %Y')}")
    today_tasks = [t for t in all_tasks if t.get("due") == today_str()]
    td = sum(1 for t in today_tasks if t["status"] == "done")
    ta,tb,tc,te = st.columns(4)
    ta.metric("Due Today",      len(today_tasks))
    tb.metric("Completed",      td)
    tc.metric("Blocked",        sum(1 for t in today_tasks if t["status"]=="blocked"))
    te.metric("Logged Today",   fmt_time(sum(t.get("elapsed",0) or 0 for t in today_tasks)))
    if today_tasks: st.progress(td/len(today_tasks))
    st.divider()

    for proj in projects:
        pt = [t for t in all_tasks if t["project_id"] == proj["id"]]
        if not pt: continue
        pd = sum(1 for t in pt if t["status"] == "done")
        ps = sum(t.get("elapsed",0) or 0 for t in pt)
        pp = round(pd/len(pt)*100) if pt else 0
        st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <span style="width:11px;height:11px;border-radius:50%;background:{proj['color']};display:inline-block"></span>
            <strong>{proj['name']}</strong>
            <span style="color:#64748b;font-size:12px;margin-left:auto">{fmt_time(ps)} logged · {pd}/{len(pt)} done</span>
        </div>""", unsafe_allow_html=True)
        st.progress(pp/100)
        for t in pt:
            elapsed_str = fmt_time(t.get("elapsed",0) or 0)
            st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9;font-size:13px">
                <span>{STATUS_ICONS.get(t['status'],'⬜')}</span>
                <span style="flex:1">{t['title']}</span>
                <span style="font-family:monospace;font-size:11px;color:#64748b">{elapsed_str}</span>
                <span class="badge b-{t['status'].replace('-','')}">{STATUS_LABELS.get(t['status'],'')}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    st.stop()

# ── Add / Edit Task form ───────────────────────────────────────────────────────
if st.session_state.show_add_task or st.session_state.edit_task_id:
    et = get_task(st.session_state.edit_task_id) if st.session_state.edit_task_id else None
    with st.expander("📝 " + ("Edit Task" if et else "New Task"), expanded=True):
        proj_names = [p["name"] for p in projects]
        proj_ids   = [p["id"]   for p in projects]

        f1, f2 = st.columns([3,1])
        with f1:
            t_title = st.text_input("Task title *", value=et["title"] if et else "", placeholder="What needs to be done?")
        with f2:
            default_pi = proj_ids.index(et["project_id"]) if et and et.get("project_id") in proj_ids else 0
            t_proj = st.selectbox("Project", proj_names, index=default_pi)

        f3,f4,f5 = st.columns(3)
        with f3:
            t_pri = st.selectbox("Priority", ["high","medium","low"],
                                 index=["high","medium","low"].index(et["priority"]) if et else 1)
        with f4:
            t_status = st.selectbox("Status", list(STATUS_LABELS.values()),
                                    index=STATUS_ORDER.index(et["status"]) if et else 0)
        with f5:
            due_v = date.fromisoformat(et["due"]) if et and et.get("due") else date.today()
            t_due = st.date_input("Due date", value=due_v)

        f6,f7 = st.columns(2)
        with f6: t_assign = st.text_input("Assignee", value=et.get("assignee","") if et else "")
        with f7: t_est = st.number_input("Est. hours", min_value=0.0, step=0.5, value=float(et.get("est_hours",0)) if et else 0.0)
        t_desc = st.text_area("Description", value=et.get("desc","") if et else "", height=65)

        bc1, bc2, _ = st.columns([1,1,5])
        with bc1:
            if st.button("💾 Save", type="primary"):
                if t_title.strip():
                    pid = proj_ids[proj_names.index(t_proj)]
                    sk  = STATUS_ORDER[list(STATUS_LABELS.values()).index(t_status)]
                    if et:
                        db_update_task(et["id"], {"title":t_title.strip(),"project_id":pid,
                            "priority":t_pri,"status":sk,"due":str(t_due),
                            "assignee":t_assign,"est_hours":t_est,"desc":t_desc})
                    else:
                        db_add_task({"id":uid(),"user_id":user_id,"title":t_title.strip(),
                            "project_id":pid,"priority":t_pri,"status":sk,
                            "due":str(t_due),"assignee":t_assign,"est_hours":t_est,
                            "desc":t_desc,"elapsed":0,"comments":[],"subtasks":[],"sort_order":len(all_tasks)})
                    st.session_state.show_add_task = False
                    st.session_state.edit_task_id  = None
                    st.rerun()
        with bc2:
            if st.button("✕ Cancel"):
                st.session_state.show_add_task = False
                st.session_state.edit_task_id  = None
                st.rerun()

# ── Filter tasks ──────────────────────────────────────────────────────────────
filter_opts = ["All","To Do","In Progress","In Review","Blocked","Done","Due Today"]
st.session_state.filter_status = st.radio("Filter:", filter_opts, horizontal=True,
    index=filter_opts.index(st.session_state.filter_status), label_visibility="collapsed")

def apply_filters(tasks):
    result = []
    for t in tasks:
        cp = st.session_state.current_project
        if   cp == "today" and t.get("due") != today_str(): continue
        elif cp not in ("all","today") and t["project_id"] != cp: continue
        f = st.session_state.filter_status
        if f == "To Do"       and t["status"] != "todo":        continue
        if f == "In Progress" and t["status"] != "in-progress": continue
        if f == "In Review"   and t["status"] != "review":      continue
        if f == "Blocked"     and t["status"] != "blocked":     continue
        if f == "Done"        and t["status"] != "done":        continue
        if f == "Due Today"   and t.get("due") != today_str():  continue
        q = st.session_state.search.lower()
        if q and q not in t["title"].lower() and q not in (t.get("desc","") or "").lower(): continue
        result.append(t)
    return result

filtered = apply_filters(all_tasks)
filtered.sort(key=lambda t: STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 99)

# ── Render tasks ──────────────────────────────────────────────────────────────
if not filtered:
    st.info("No tasks found. Add one or adjust filters.")
else:
    cur_status = None
    for t in filtered:
        # Section header per status group
        if t["status"] != cur_status:
            cur_status = t["status"]
            cnt = sum(1 for x in filtered if x["status"] == cur_status)
            st.markdown(f'<div class="section-hdr">{STATUS_ICONS.get(cur_status,"")} {STATUS_LABELS.get(cur_status,"")} · {cnt}</div>',
                        unsafe_allow_html=True)

        proj       = get_proj(t["project_id"])
        subs       = task_subtasks(t)
        coms       = task_comments(t)
        sub_done   = sum(1 for s in subs if s["done"])
        sub_total  = len(subs)
        elapsed    = t.get("elapsed", 0) or 0
        is_running = st.session_state.active_timer == t["id"]
        is_expanded = st.session_state.expanded_task == t["id"]
        sc         = STATUS_COLORS.get(t["status"],"#94a3b8")

        with st.container():
            st.markdown(f'<div style="border-left:3px solid {sc};background:#fff;border-radius:10px;padding:10px 14px;margin-bottom:4px;border:1px solid #e2e8f0">', unsafe_allow_html=True)

            cm, ca = st.columns([7,3])
            with cm:
                title_style = "text-decoration:line-through;color:#94a3b8" if t["status"]=="done" else "font-weight:600"
                pname = proj["name"] if proj else "—"
                meta  = f'{STATUS_ICONS.get(t["status"],"")} {STATUS_LABELS.get(t["status"],"")} &nbsp;|&nbsp; {PRI_ICONS.get(t["priority"],"")} {t["priority"]} &nbsp;|&nbsp; 📁 {pname}'
                if t.get("due"):      meta += f' &nbsp;|&nbsp; 📅 {t["due"]}'
                if t.get("assignee"): meta += f' &nbsp;|&nbsp; 👤 {t["assignee"]}'
                if sub_total:         meta += f' &nbsp;|&nbsp; ☑ {sub_done}/{sub_total}'
                if coms:              meta += f' &nbsp;|&nbsp; 💬 {len(coms)}'
                if t.get("est_hours"): meta += f' &nbsp;|&nbsp; ⏱ {t["est_hours"]}h est.'
                tmr_style = "color:#166534;background:#dcfce7;padding:2px 8px;border-radius:6px;font-family:monospace;font-size:12px" if is_running \
                            else "color:#374151;background:#f1f5f9;padding:2px 8px;border-radius:6px;font-family:monospace;font-size:12px"
                tmr_label = f"⏱ {fmt_time(elapsed)}{'  ●' if is_running else ''}"
                st.markdown(f'<div style="{title_style};font-size:14px;margin-bottom:3px">{t["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:11px;color:#64748b">{meta}</div>', unsafe_allow_html=True)
                st.markdown(f'<span style="{tmr_style}">{tmr_label}</span>', unsafe_allow_html=True)

            with ca:
                b1,b2,b3,b4,b5 = st.columns(5)

                # Timer
                with b1:
                    if is_running:
                        if st.button("⏹", key=f"stop_{t['id']}", help="Stop timer"):
                            if st.session_state.timer_start:
                                added = int((datetime.now()-st.session_state.timer_start).total_seconds())
                                db_update_task(t["id"], {"elapsed": elapsed + added})
                            st.session_state.active_timer = None
                            st.session_state.timer_start  = None
                            st.rerun()
                    else:
                        if st.button("▶", key=f"play_{t['id']}", help="Start timer"):
                            if st.session_state.active_timer:
                                prev = get_task(st.session_state.active_timer)
                                if prev and st.session_state.timer_start:
                                    added = int((datetime.now()-st.session_state.timer_start).total_seconds())
                                    db_update_task(prev["id"], {"elapsed": (prev.get("elapsed",0) or 0)+added})
                            st.session_state.active_timer = t["id"]
                            st.session_state.timer_start  = datetime.now()
                            if t["status"] == "todo":
                                db_update_task(t["id"], {"status":"in-progress"})
                            st.rerun()

                # Quick status change
                with b2:
                    new_st = st.selectbox("", STATUS_ORDER,
                                          index=STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 0,
                                          key=f"qs_{t['id']}", label_visibility="collapsed",
                                          format_func=lambda x: STATUS_ICONS.get(x,""))
                    if new_st != t["status"]:
                        db_update_task(t["id"], {"status": new_st})
                        st.rerun()

                with b3:
                    if st.button("💬", key=f"exp_{t['id']}", help="Details / comments"):
                        st.session_state.expanded_task = None if is_expanded else t["id"]
                        st.rerun()
                with b4:
                    if st.button("✏️", key=f"edit_{t['id']}", help="Edit"):
                        st.session_state.edit_task_id  = t["id"]
                        st.session_state.show_add_task = False
                        st.rerun()
                with b5:
                    if st.button("🗑", key=f"del_{t['id']}", help="Delete"):
                        db_delete_task(t["id"])
                        if st.session_state.expanded_task == t["id"]:
                            st.session_state.expanded_task = None
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        # ── Expanded panel ──────────────────────────────────────────────────
        if is_expanded:
            with st.expander("📋 Subtasks & Comments", expanded=True):
                if t.get("desc"):
                    st.caption(f"📝 {t['desc']}")

                # Subtasks
                st.markdown("**☑ Subtasks**")
                if sub_total:
                    st.progress(sub_done/sub_total)
                    st.caption(f"{sub_done}/{sub_total} completed")

                subs_updated = False
                for s in subs:
                    sc1, sc2, sc3 = st.columns([1,8,1])
                    with sc1:
                        checked = st.checkbox("", value=s["done"], key=f"s_{t['id']}_{s['id']}", label_visibility="collapsed")
                        if checked != s["done"]:
                            s["done"] = checked; subs_updated = True
                    with sc2:
                        style = "text-decoration:line-through;color:#94a3b8" if s["done"] else ""
                        st.markdown(f'<span style="font-size:13px;{style}">{s["title"]}</span>', unsafe_allow_html=True)
                    with sc3:
                        if st.button("✕", key=f"ds_{t['id']}_{s['id']}"):
                            subs = [x for x in subs if x["id"] != s["id"]]
                            db_update_task(t["id"], {"subtasks": _json.dumps(subs)})
                            st.rerun()
                if subs_updated:
                    db_update_task(t["id"], {"subtasks": _json.dumps(subs)})
                    st.rerun()

                ns_col, na_col = st.columns([5,1])
                with ns_col:
                    new_sub = st.text_input("New subtask", placeholder="Subtask title...", key=f"nsub_{t['id']}", label_visibility="collapsed")
                with na_col:
                    if st.button("+ Add", key=f"asub_{t['id']}"):
                        if new_sub.strip():
                            subs.append({"id": uid(), "title": new_sub.strip(), "done": False})
                            db_update_task(t["id"], {"subtasks": _json.dumps(subs)})
                            st.rerun()

                st.divider()

                # Comments
                st.markdown("**💬 Comments**")
                for c in coms:
                    st.markdown(f"""<div class="c-bubble">
                        <strong style="font-size:12px">👤 {t.get('assignee','User')}</strong>
                        <span style="font-size:11px;color:#64748b;margin-left:8px">{c.get('time','')}</span><br>
                        <span style="font-size:13px">{c['text']}</span>
                    </div>""", unsafe_allow_html=True)

                nc1, nc2 = st.columns([5,1])
                with nc1:
                    new_c = st.text_input("Comment", placeholder="Write a comment...", key=f"nc_{t['id']}", label_visibility="collapsed")
                with nc2:
                    if st.button("Post", key=f"pc_{t['id']}", type="primary"):
                        if new_c.strip():
                            coms.append({"id": uid(), "text": new_c.strip(), "time": now_str()})
                            db_update_task(t["id"], {"comments": _json.dumps(coms)})
                            st.rerun()
