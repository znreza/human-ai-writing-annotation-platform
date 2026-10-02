# Deploying on Render from the public Git URL (no GitHub access required)

Render can deploy a **public Git repository by URL** without connecting your GitHub account, so it
never sees your GitHub organizations. The repo is already public:
`https://github.com/znreza/human-ai-writing-annotation-platform`

## Step 1 — Create the service

1. Sign up / sign in at https://render.com (email signup is fine; no GitHub needed, no card for free tier).
2. Click **New +** → **Web Service**.
3. Choose **Public Git Repository** and paste:
   `https://github.com/znreza/human-ai-writing-annotation-platform`
   then continue.

## Step 2 — Configure

Render reads `render.yaml`, or set these manually:
- **Runtime**: Python
- **Build command**: `pip install -r requirements.txt`
- **Start command**:
  `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.enableCORS false`
- **Instance type**: Free

## Step 3 — Environment variables (secrets)

In the service's **Environment** tab, add:

| Key | Value |
|---|---|
| `ANNOTATOR_PASSWORD` | your annotator password |
| `ADMIN_PASSWORD` | your admin password |
| `DATABASE_URL` | `postgresql+psycopg2://postgres.pgmzwhzklpddyjlgrfsu:YOUR-DB-PASSWORD@aws-0-us-east-2.pooler.supabase.com:5432/postgres` |
| `PER_GENRE` | `4` |
| `PYTHON_VERSION` | `3.11.9` |

The app reads these automatically (it falls back from Streamlit secrets to environment variables).

## Step 4 — Deploy

Click **Create Web Service**. Render builds and starts it, and gives you a URL like
`https://ai-writing-annotation.onrender.com` — password-gated, backed by Supabase.

## Step 5 — Load items into Supabase

Run locally once `data/selected_ids.txt` is ready:

```bash
export DATABASE_URL="postgresql+psycopg2://postgres.pgmzwhzklpddyjlgrfsu:YOUR-DB-PASSWORD@aws-0-us-east-2.pooler.supabase.com:5432/postgres"
python load_items.py --deactivate-others data/selected_ids.txt
```

## Step 6 — Keep it awake (free, no sleeping)

Free Render services spin down after ~15 min of no traffic. Prevent that with a free uptime pinger
that hits the URL every few minutes:

1. Sign up at **https://uptimerobot.com** (free) — or https://cron-job.org.
2. Create a new **HTTP(s) monitor**:
   - **URL**: your Render URL plus the health path, e.g. `https://ai-writing-annotation.onrender.com/_stcore/health`
     (this returns `ok` and is lighter than loading the full app; the root URL also works).
   - **Monitoring interval**: 5 minutes (UptimeRobot free minimum).
3. Save. The pings count as traffic and keep the service from spinning down, so annotators never hit a
   cold start.

Render's free tier allows ~750 instance-hours per month, which covers one always-on (pinged) service
24/7. Keep only this one free service running so you stay under the cap.

## Notes

- With the pinger above, the service stays awake. Without it, free services cold-start in ~30–60s after idle.
- To update the app: `git push origin main`, then in Render click **Manual Deploy → Deploy latest commit**
  (or enable auto-deploy, which polls the public repo).
- No GitHub authorization is involved at any point, so your GitHub organizations are never exposed.
