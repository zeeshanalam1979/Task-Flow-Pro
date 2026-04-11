# ✅ TaskFlow Pro — Setup Guide

Jira-style task manager built with Python + Streamlit + Supabase (free forever).

---

## 🚀 Deploy in 4 Steps

### Step 1 — Set up Supabase (free database)

1. Go to [supabase.com](https://supabase.com) → **Start for free** → Sign up with GitHub
2. Click **New Project** → give it a name (e.g. `taskflow`) → set a DB password → Create
3. Wait ~1 minute for the project to start
4. Go to **SQL Editor** → **New Query**
5. Paste the entire contents of `supabase_schema.sql` → click **Run**
6. Go to **Project Settings → API**
   - Copy **Project URL** → this is your `SUPABASE_URL`
   - Copy **service_role key** (under Project API keys) → this is your `SUPABASE_KEY`

---

### Step 2 — Push to GitHub

1. Create a new **public** GitHub repo (e.g. `taskflow-pro`)
2. Push these files to the repo root:
   ```
   app.py
   requirements.txt
   supabase_schema.sql   ← optional, just for reference
   .gitignore
   ```
   ⚠️ Do NOT push `.streamlit/secrets.toml` — it's in `.gitignore`

---

### Step 3 — Deploy on Streamlit Cloud (free)

1. Go to [share.streamlit.io](https://share.streamlit.io) → Sign in with GitHub
2. Click **New app** → Select your repo → set `app.py` as the main file
3. Click **Advanced settings** → **Secrets** → paste:
   ```toml
   SUPABASE_URL = "https://your-project-id.supabase.co"
   SUPABASE_KEY = "your-service-role-key"
   ```
4. Click **Deploy** → ✅ Live in ~60 seconds

Your app URL will be: `https://your-app-name.streamlit.app`

---

### Step 4 — Create your account

1. Open your app URL
2. Click **Create Account** tab
3. Sign up with username + password
4. You're in — your 3 default projects are ready

---

## 🔒 Login & Data

- Each user has their own isolated projects and tasks
- Passwords are hashed with SHA-256 (never stored in plain text)
- All data stored in Supabase PostgreSQL (500MB free tier = thousands of tasks)
- Data persists forever — survives redeployments

## 📦 Features

| Feature | Details |
|---|---|
| 🔐 Login / Register | Username + password auth |
| 📁 Projects | Unlimited projects with custom colors |
| ✅ Tasks | Title, project, priority, status, due date, assignee, est. hours |
| 🔄 5 Statuses | To Do → In Progress → In Review → Blocked → Done |
| ⏱ Time Tracker | Start/stop per task, auto-logs time |
| ☑ Subtasks | Add/check/delete subtasks with progress bar |
| 💬 Comments | Timestamped comments per task |
| 🔍 Search | Live search across titles and descriptions |
| 📊 Daily Summary | Per-project progress + time logged |
| ⬇ CSV Export | Download all visible tasks |
| ☁️ Cloud sync | All data saved to Supabase in real-time |

---

## 💻 Run Locally

```bash
pip install -r requirements.txt

# Create local secrets file
mkdir .streamlit
echo 'SUPABASE_URL = "your-url"' >> .streamlit/secrets.toml
echo 'SUPABASE_KEY = "your-key"' >> .streamlit/secrets.toml

streamlit run app.py
```

If you don't set up Supabase yet, the app runs in **demo mode** (session-only, resets on refresh).

---

## Built by Zeeshan Alam
SEO Specialist & Digital Marketing Consultant — Karachi, Pakistan
[linkedin.com/in/zeeshan-alam-seo-expert/](https://linkedin.com/in/zeeshan-alam-seo-expert/)
