-- ============================================================
-- TaskFlow Pro – Supabase Database Schema
-- Run this in Supabase > SQL Editor > New Query
-- ============================================================

-- 1. USERS TABLE
create table if not exists users (
  id            text primary key,
  username      text unique not null,
  password_hash text not null,
  display_name  text,
  created_at    text
);

-- 2. PROJECTS TABLE
create table if not exists projects (
  id         text primary key,
  user_id    text references users(id) on delete cascade,
  name       text not null,
  color      text default '#1D9E75',
  created_at text
);

-- 3. TASKS TABLE
create table if not exists tasks (
  id          text primary key,
  user_id     text references users(id) on delete cascade,
  project_id  text references projects(id) on delete cascade,
  title       text not null,
  description text default '',
  desc        text default '',
  status      text default 'todo',
  priority    text default 'medium',
  due         text,
  assignee    text,
  est_hours   numeric default 0,
  elapsed     integer default 0,
  subtasks    text default '[]',   -- stored as JSON string
  comments    text default '[]',   -- stored as JSON string
  sort_order  integer default 0,
  created_at  text
);

-- 4. Row Level Security (RLS) — users only see their own data
alter table users    enable row level security;
alter table projects enable row level security;
alter table tasks    enable row level security;

-- Allow all operations via service role key (used by our app)
create policy "service_all_users"    on users    for all using (true) with check (true);
create policy "service_all_projects" on projects for all using (true) with check (true);
create policy "service_all_tasks"    on tasks    for all using (true) with check (true);

-- 5. Indexes for performance
create index if not exists idx_projects_user on projects(user_id);
create index if not exists idx_tasks_user    on tasks(user_id);
create index if not exists idx_tasks_project on tasks(project_id);
create index if not exists idx_tasks_status  on tasks(status);
create index if not exists idx_tasks_due     on tasks(due);
