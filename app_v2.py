"""
TaskFlow Pro – Streamlit Task Manager
Login + persistent storage (JSON locally, Supabase on cloud)
"""

import streamlit as st
import hashlib, uuid, csv, io, json
from datetime import datetime, date
from pathlib import Path

st.set_page_config(page_title="TaskFlow Pro", page_icon="✅", layout="wide",
                   initial_sidebar_state="expanded")

# ── Supabase — optional, fully silent fallback ────────────────────────────────
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
[data-testid="stAppViewContainer"] { background:#f0f2f6; }
[data-testid="stSidebar"]          { background:#ffffff; border-right:1px solid #e2e8f0; }
.block-container                   { padding-top:1.2rem; }
[data-testid="metric-container"]   { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:10px 14px; }
.section-hdr { font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase;
               letter-spacing:.06em; padding:8px 0 5px; border-bottom:1px solid #e2e8f0; margin-bottom:6px; }
.c-bubble    { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
               padding:8px 12px; margin-bottom:5px; font-size:13px; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_FILE     = Path("taskflow_data.json")
STATUS_LABELS = {"todo":"To Do","in-progress":"In Progress","review":"In Review","blocked":"Blocked","done":"Done"}
STATUS_ICONS  = {"todo":"⬜","in-progress":"🔄","review":"🔍","blocked":"🚫","done":"✅"}
PRI_ICONS     = {"high":"🔴","medium":"🟡","low":"🟢"}
STATUS_ORDER  = ["todo","in-progress","review","blocked","done"]
STATUS_COLORS = {"todo":"#94a3b8","in-progress":"#f59e0b","review":"#7c3aed","blocked":"#ef4444","done":"#22c55e"}

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

def jl(v, d):
    if isinstance(v, list): return v
    if isinstance(v, str):
        try: return json.loads(v)
        except: return d
    return d

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
    user = {"id":uid(),"username":username,"password_hash":hash_pw(pw),
            "display_name":name,"created_at":now_str()}
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
    for n,c in [("Cloud Wholesale SEO","#1D9E75"),("iPuff24 Shopify SEO","#534AB7"),("General","#378ADD")]:
        db_add_project({"id":uid(),"user_id":uid_,"name":n,"color":c,"created_at":now_str()})

# ── Session defaults ──────────────────────────────────────────────────────────
_DEF = {"logged_in":False,"current_user":None,"view":"board","current_project":"all",
        "filter_status":"All","search":"","expanded_task":None,
        "show_add_task":False,"edit_task_id":None,"active_timer":None,"timer_start":None}
for k,v in _DEF.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Auth page ─────────────────────────────────────────────────────────────────
def show_auth():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:40px 0 20px">
            <div style="font-size:48px">✅</div>
            <h2 style="margin:6px 0 4px;font-size:24px">TaskFlow Pro</h2>
            <p style="color:#64748b;font-size:13px;margin:0">Your personal project task manager</p>
        </div>""", unsafe_allow_html=True)

        with st.container():
            tab1, tab2 = st.tabs(["🔐 Sign In", "📝 Create Account"])

            with tab1:
                uname = st.text_input("Username", key="li_u", placeholder="Your username")
                pw    = st.text_input("Password", type="password", key="li_p", placeholder="Your password")
                st.markdown("")
                if st.button("Sign In →", type="primary", use_container_width=True):
                    u = db_get_user(uname.strip().lower())
                    if u and u["password_hash"] == hash_pw(pw):
                        st.session_state.logged_in    = True
                        st.session_state.current_user = u
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")

            with tab2:
                dn  = st.text_input("Your name",         key="rn", placeholder="e.g. Zeeshan Alam")
                un  = st.text_input("Choose a username", key="ru", placeholder="lowercase, no spaces")
                p1  = st.text_input("Password",          key="rp", type="password", placeholder="Min 6 characters")
                p2  = st.text_input("Confirm password",  key="rc", type="password")
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
                        st.session_state.logged_in    = True
                        st.session_state.current_user = u
                        st.rerun()

if not st.session_state.logged_in:
    show_auth()
    st.stop()

# ── Data ──────────────────────────────────────────────────────────────────────
user      = st.session_state.current_user
user_id   = user["id"]
projects  = db_get_projects(user_id)
all_tasks = db_get_tasks(user_id)

def get_proj(pid): return next((p for p in projects if p["id"]==pid), None)
def get_task(tid): return next((t for t in all_tasks if t["id"]==tid), None)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    initials = "".join(w[0].upper() for w in user.get("display_name","U").split()[:2])
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px">
      <div style="width:36px;height:36px;border-radius:50%;background:#534AB7;color:#fff;
                  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600">{initials}</div>
      <div>
        <div style="font-weight:600;font-size:13px">{user.get('display_name','User')}</div>
        <div style="font-size:11px;color:#64748b">@{user['username']}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.divider()

    def nav(label, view, proj):
        active = st.session_state.view==view and (proj is None or st.session_state.current_project==proj)
        if st.button(label, use_container_width=True, type="primary" if active else "secondary", key=f"nav_{label}"):
            st.session_state.view = view
            if proj is not None: st.session_state.current_project = proj
            st.rerun()

    nav("🗂  All Tasks",    "board",   "all")
    nav("📅  Today",         "board",   "today")
    nav("📊  Daily Summary", "summary", None)

    st.divider()
    st.markdown('<p style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Projects</p>', unsafe_allow_html=True)

    for proj in projects:
        count  = sum(1 for t in all_tasks if t["project_id"]==proj["id"])
        active = st.session_state.current_project==proj["id"] and st.session_state.view=="board"
        c1, c2 = st.columns([5,1])
        with c1:
            if st.button(proj["name"], key=f"pb_{proj['id']}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.current_project = proj["id"]
                st.session_state.view = "board"
                st.rerun()
        with c2:
            st.markdown(f'<div style="text-align:center;font-size:11px;color:#94a3b8;padding-top:6px">{count}</div>',
                        unsafe_allow_html=True)

    st.divider()
    with st.expander("➕  New Project"):
        pn = st.text_input("Project name", key="np_n", placeholder="e.g. Local SEO Campaign")
        pc = st.color_picker("Color", "#1D9E75", key="np_c")
        if st.button("Create", type="primary", key="np_btn"):
            if pn.strip():
                db_add_project({"id":uid(),"user_id":user_id,"name":pn.strip(),"color":pc,"created_at":now_str()})
                st.rerun()

    st.divider()
    if st.button("🚪  Sign out", use_container_width=True):
        for k, v in _DEF.items(): st.session_state[k] = v
        if "_jdb" in st.session_state: del st.session_state["_jdb"]
        st.rerun()

# ── Header row ────────────────────────────────────────────────────────────────
if   st.session_state.view == "summary":             vt = "📊 Daily Summary"
elif st.session_state.current_project == "all":      vt = "🗂 All Tasks"
elif st.session_state.current_project == "today":    vt = "📅 Today"
else:
    _p = get_proj(st.session_state.current_project)
    vt = f"📁 {_p['name']}" if _p else "Tasks"

ct, cs, c_csv, c_add = st.columns([3,3,1,1])
with ct: st.markdown(f"## {vt}")
with cs: st.session_state.search = st.text_input("","",placeholder="🔍 Search tasks...",label_visibility="collapsed",key="srch")
with c_csv:
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Task","Project","Status","Priority","Due","Assignee","Est Hrs","Time Logged","Subtasks Done","Subtasks Total","Comments"])
    for t in all_tasks:
        p=get_proj(t["project_id"]); subs=jl(t.get("subtasks",[]),[]); coms=jl(t.get("comments",[]),[])
        w.writerow([t["title"],p["name"] if p else "",STATUS_LABELS.get(t["status"],""),t["priority"],
                    t.get("due",""),t.get("assignee",""),t.get("est_hours",0),fmt_time(t.get("elapsed",0)),
                    sum(1 for s in subs if s["done"]),len(subs)," | ".join(c["text"] for c in coms)])
    st.download_button("⬇ CSV",buf.getvalue(),f"taskflow_{today_str()}.csv","text/csv",use_container_width=True)
with c_add:
    if st.button("➕ Task", type="primary", use_container_width=True):
        st.session_state.show_add_task = True; st.session_state.edit_task_id = None

# ── Stats ─────────────────────────────────────────────────────────────────────
_ts  = sum(t.get("elapsed",0) or 0 for t in all_tasks)
_dc  = sum(1 for t in all_tasks if t["status"]=="done")
_ip  = sum(1 for t in all_tasks if t["status"]=="in-progress")
_bl  = sum(1 for t in all_tasks if t["status"]=="blocked")
_rv  = sum(1 for t in all_tasks if t["status"]=="review")
_pct = round(_dc/len(all_tasks)*100) if all_tasks else 0
s1,s2,s3,s4,s5,s6,s7 = st.columns(7)
s1.metric("Total",len(all_tasks)); s2.metric("In Progress",_ip); s3.metric("In Review",_rv)
s4.metric("Blocked",_bl); s5.metric("Done",_dc); s6.metric("Time Logged",fmt_time(_ts)); s7.metric("Complete",f"{_pct}%")
if all_tasks: st.progress(_pct/100)
st.divider()

# ── Daily Summary ─────────────────────────────────────────────────────────────
if st.session_state.view == "summary":
    st.markdown(f"### 📅 {date.today().strftime('%A, %d %B %Y')}")
    tt = [t for t in all_tasks if t.get("due")==today_str()]
    _td = sum(1 for t in tt if t["status"]=="done")
    ta,tb,tc,te = st.columns(4)
    ta.metric("Due Today",len(tt)); tb.metric("Completed",_td)
    tc.metric("Blocked",sum(1 for t in tt if t["status"]=="blocked"))
    te.metric("Logged Today",fmt_time(sum(t.get("elapsed",0) or 0 for t in tt)))
    if tt: st.progress(_td/len(tt))
    st.divider()
    for proj in projects:
        pt = [t for t in all_tasks if t["project_id"]==proj["id"]]
        if not pt: continue
        pd=sum(1 for t in pt if t["status"]=="done"); ps=sum(t.get("elapsed",0) or 0 for t in pt)
        st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <span style="width:11px;height:11px;border-radius:50%;background:{proj['color']};display:inline-block"></span>
            <strong>{proj['name']}</strong>
            <span style="color:#64748b;font-size:12px;margin-left:auto">{fmt_time(ps)} logged · {pd}/{len(pt)} done</span>
        </div>""", unsafe_allow_html=True)
        st.progress(round(pd/len(pt)*100)/100)
        for t in pt:
            st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9;font-size:13px">
                <span>{STATUS_ICONS.get(t['status'],'⬜')}</span><span style="flex:1">{t['title']}</span>
                <span style="font-family:monospace;font-size:11px;color:#64748b">{fmt_time(t.get('elapsed',0) or 0)}</span>
                <span style="font-size:11px;padding:1px 8px;border-radius:10px;
                    background:{STATUS_COLORS.get(t['status'],'#94a3b8')}22;color:{STATUS_COLORS.get(t['status'],'#94a3b8')}">
                    {STATUS_LABELS.get(t['status'],'')}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    st.stop()

# ── Add/Edit form ─────────────────────────────────────────────────────────────
if st.session_state.show_add_task or st.session_state.edit_task_id:
    et = get_task(st.session_state.edit_task_id) if st.session_state.edit_task_id else None
    pnames = [p["name"] for p in projects]; pids = [p["id"] for p in projects]
    with st.expander("📝 "+("Edit Task" if et else "New Task"), expanded=True):
        f1,f2 = st.columns([3,1])
        with f1: t_title = st.text_input("Task title *", value=et["title"] if et else "", placeholder="What needs to be done?")
        with f2:
            dpi = pids.index(et["project_id"]) if et and et.get("project_id") in pids else 0
            t_proj = st.selectbox("Project", pnames, index=dpi)
        f3,f4,f5 = st.columns(3)
        with f3: t_pri = st.selectbox("Priority",["high","medium","low"],index=["high","medium","low"].index(et["priority"]) if et else 1)
        with f4: t_st  = st.selectbox("Status",list(STATUS_LABELS.values()),index=STATUS_ORDER.index(et["status"]) if et else 0)
        with f5:
            dv = date.fromisoformat(et["due"]) if et and et.get("due") else date.today()
            t_due = st.date_input("Due date", value=dv)
        f6,f7 = st.columns(2)
        with f6: t_asn = st.text_input("Assignee", value=et.get("assignee","") if et else "")
        with f7: t_est = st.number_input("Est. hours",min_value=0.0,step=0.5,value=float(et.get("est_hours",0)) if et else 0.0)
        t_desc = st.text_area("Description", value=et.get("desc","") if et else "", height=65)
        bc1,bc2,_ = st.columns([1,1,5])
        with bc1:
            if st.button("💾 Save", type="primary"):
                if t_title.strip():
                    pid = pids[pnames.index(t_proj)]; sk = STATUS_ORDER[list(STATUS_LABELS.values()).index(t_st)]
                    if et:
                        db_update_task(et["id"],{"title":t_title.strip(),"project_id":pid,"priority":t_pri,
                            "status":sk,"due":str(t_due),"assignee":t_asn,"est_hours":t_est,"desc":t_desc})
                    else:
                        db_add_task({"id":uid(),"user_id":user_id,"title":t_title.strip(),"project_id":pid,
                            "priority":t_pri,"status":sk,"due":str(t_due),"assignee":t_asn,"est_hours":t_est,
                            "desc":t_desc,"elapsed":0,"comments":[],"subtasks":[],"sort_order":len(all_tasks)})
                    st.session_state.show_add_task=False; st.session_state.edit_task_id=None; st.rerun()
        with bc2:
            if st.button("✕ Cancel"):
                st.session_state.show_add_task=False; st.session_state.edit_task_id=None; st.rerun()

# ── Filter bar ────────────────────────────────────────────────────────────────
f_opts = ["All","To Do","In Progress","In Review","Blocked","Done","Due Today"]
st.session_state.filter_status = st.radio("",f_opts,horizontal=True,
    index=f_opts.index(st.session_state.filter_status),label_visibility="collapsed")

def apply_filters(tasks):
    out=[]
    for t in tasks:
        cp=st.session_state.current_project
        if   cp=="today" and t.get("due")!=today_str():          continue
        elif cp not in ("all","today") and t["project_id"]!=cp:  continue
        f=st.session_state.filter_status
        if f=="To Do"       and t["status"]!="todo":             continue
        if f=="In Progress" and t["status"]!="in-progress":      continue
        if f=="In Review"   and t["status"]!="review":           continue
        if f=="Blocked"     and t["status"]!="blocked":          continue
        if f=="Done"        and t["status"]!="done":             continue
        if f=="Due Today"   and t.get("due")!=today_str():       continue
        q=st.session_state.search.lower()
        if q and q not in t["title"].lower() and q not in (t.get("desc","") or "").lower(): continue
        out.append(t)
    return out

filtered = apply_filters(all_tasks)
filtered.sort(key=lambda t: STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 99)

if not filtered:
    st.info("No tasks found. Add one or adjust the filters above.")
    st.stop()

# ── Task cards ────────────────────────────────────────────────────────────────
cur_st = None
for t in filtered:
    if t["status"] != cur_st:
        cur_st = t["status"]
        cnt = sum(1 for x in filtered if x["status"]==cur_st)
        st.markdown(f'<div class="section-hdr">{STATUS_ICONS.get(cur_st,"")} {STATUS_LABELS.get(cur_st,"")} &nbsp;·&nbsp; {cnt}</div>',
                    unsafe_allow_html=True)

    proj       = get_proj(t["project_id"])
    subs       = jl(t.get("subtasks",[]),[])
    coms       = jl(t.get("comments",[]),[])
    sub_done   = sum(1 for s in subs if s["done"])
    sub_total  = len(subs)
    elapsed    = int(t.get("elapsed",0) or 0)
    is_run     = st.session_state.active_timer == t["id"]
    is_exp     = st.session_state.expanded_task == t["id"]
    sc         = STATUS_COLORS.get(t["status"],"#94a3b8")

    with st.container():
        st.markdown(f'<div style="border-left:3px solid {sc};background:#fff;border-radius:10px;padding:10px 14px;margin-bottom:4px;border:1px solid #e2e8f0">', unsafe_allow_html=True)
        cm, ca = st.columns([7,3])

        with cm:
            ts   = "text-decoration:line-through;color:#94a3b8" if t["status"]=="done" else "font-weight:600"
            pnm  = proj["name"] if proj else "—"
            meta = (f'{STATUS_ICONS.get(t["status"],"")} {STATUS_LABELS.get(t["status"],"")} &nbsp;|&nbsp; '
                    f'{PRI_ICONS.get(t["priority"],"")} {t["priority"]} &nbsp;|&nbsp; 📁 {pnm}')
            if t.get("due"):       meta += f' &nbsp;|&nbsp; 📅 {t["due"]}'
            if t.get("assignee"):  meta += f' &nbsp;|&nbsp; 👤 {t["assignee"]}'
            if sub_total:          meta += f' &nbsp;|&nbsp; ☑ {sub_done}/{sub_total}'
            if coms:               meta += f' &nbsp;|&nbsp; 💬 {len(coms)}'
            if t.get("est_hours"): meta += f' &nbsp;|&nbsp; ⏱ {t["est_hours"]}h est.'
            tbg  = "#dcfce7" if is_run else "#f1f5f9"
            tcol = "#166534" if is_run else "#374151"
            tlbl = f"⏱ {fmt_time(elapsed)}{'  ⬤' if is_run else ''}"
            st.markdown(f'<div style="{ts};font-size:14px;margin-bottom:3px">{t["title"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:11px;color:#64748b;margin-bottom:4px">{meta}</div>', unsafe_allow_html=True)
            st.markdown(f'<span style="background:{tbg};color:{tcol};padding:2px 9px;border-radius:6px;font-family:monospace;font-size:12px">{tlbl}</span>', unsafe_allow_html=True)

        with ca:
            b1,b2,b3,b4,b5 = st.columns(5)
            with b1:
                if is_run:
                    if st.button("⏹",key=f"stop_{t['id']}",help="Stop timer"):
                        if st.session_state.timer_start:
                            added = int((datetime.now()-st.session_state.timer_start).total_seconds())
                            db_update_task(t["id"],{"elapsed":elapsed+added})
                        st.session_state.active_timer=None; st.session_state.timer_start=None; st.rerun()
                else:
                    if st.button("▶",key=f"play_{t['id']}",help="Start timer"):
                        if st.session_state.active_timer:
                            prev=get_task(st.session_state.active_timer)
                            if prev and st.session_state.timer_start:
                                added=int((datetime.now()-st.session_state.timer_start).total_seconds())
                                db_update_task(prev["id"],{"elapsed":(prev.get("elapsed",0) or 0)+added})
                        st.session_state.active_timer=t["id"]; st.session_state.timer_start=datetime.now()
                        if t["status"]=="todo": db_update_task(t["id"],{"status":"in-progress"})
                        st.rerun()
            with b2:
                ns = st.selectbox("",STATUS_ORDER,index=STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 0,
                                  key=f"qs_{t['id']}",label_visibility="collapsed",format_func=lambda x:STATUS_ICONS.get(x,""))
                if ns != t["status"]: db_update_task(t["id"],{"status":ns}); st.rerun()
            with b3:
                if st.button("💬",key=f"exp_{t['id']}",help="Details"):
                    st.session_state.expanded_task = None if is_exp else t["id"]; st.rerun()
            with b4:
                if st.button("✏️",key=f"ed_{t['id']}",help="Edit"):
                    st.session_state.edit_task_id=t["id"]; st.session_state.show_add_task=False; st.rerun()
            with b5:
                if st.button("🗑",key=f"dl_{t['id']}",help="Delete"):
                    db_delete_task(t["id"])
                    if st.session_state.expanded_task==t["id"]: st.session_state.expanded_task=None
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Expanded panel ────────────────────────────────────────────────────────
    if is_exp:
        with st.expander("📋 Subtasks & Comments", expanded=True):
            if t.get("desc"): st.caption(f"📝 {t['desc']}")

            st.markdown("**☑ Subtasks**")
            if sub_total:
                st.progress(sub_done/sub_total)
                st.caption(f"{sub_done} of {sub_total} completed")

            changed = False
            for s in subs:
                sc1,sc2,sc3 = st.columns([1,8,1])
                with sc1:
                    chk = st.checkbox("",value=s["done"],key=f"s_{t['id']}_{s['id']}",label_visibility="collapsed")
                    if chk != s["done"]: s["done"]=chk; changed=True
                with sc2:
                    sty = "text-decoration:line-through;color:#94a3b8" if s["done"] else ""
                    st.markdown(f'<span style="font-size:13px;{sty}">{s["title"]}</span>', unsafe_allow_html=True)
                with sc3:
                    if st.button("✕",key=f"ds_{t['id']}_{s['id']}"):
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
            st.markdown("**💬 Comments**")
            for c in coms:
                st.markdown(f"""<div class="c-bubble">
                    <strong style="font-size:12px">👤 {t.get('assignee') or 'User'}</strong>
                    <span style="font-size:11px;color:#64748b;margin-left:8px">{c.get('time','')}</span><br>
                    <span style="font-size:13px">{c['text']}</span>
                </div>""", unsafe_allow_html=True)

            nc1,nc2 = st.columns([5,1])
            with nc1: nc=st.text_input("",placeholder="Write a comment...",key=f"nc_{t['id']}",label_visibility="collapsed")
            with nc2:
                if st.button("Post",key=f"pc_{t['id']}",type="primary"):
                    if nc.strip():
                        coms.append({"id":uid(),"text":nc.strip(),"time":now_str()})
                        db_update_task(t["id"],{"comments":coms}); st.rerun()
