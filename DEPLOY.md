# Deploying the annotation platform (Supabase + Streamlit Community Cloud)

The app runs unchanged on SQLite (local) or Postgres (Supabase). Deployment switches the backend by
setting one secret (`DATABASE_URL`). No code changes are needed.

## Step 1 — Create a Supabase project (free)

1. Go to https://supabase.com, sign in, and create a new project. Choose a region near your
   annotators. Save the database password you set.
2. In the project, open **Project Settings → Database → Connection string → URI**.
3. Copy the connection string. It looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.abcdefgh.supabase.co:5432/postgres`
4. Change the scheme to the SQLAlchemy driver form by inserting `+psycopg2`:
   `postgresql+psycopg2://postgres:[YOUR-PASSWORD]@db.abcdefgh.supabase.co:5432/postgres`

   Tip: if you plan many concurrent annotators, use the **connection pooler** URI (port 6543) instead.

No table setup is needed. The app creates all tables on first run.

## Step 2 — Load the study items into Supabase

Point the loader at Supabase and load your curated pairs (see README for how the pool is built):

```bash
cd annotation-platform
export DATABASE_URL="postgresql+psycopg2://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres"
python load_items.py --deactivate-others selected_ids.txt
```

`selected_ids.txt` holds one `pair_id` per line (the ones you picked from
`annotation_candidates.html`). `--deactivate-others` makes only these items active.

## Step 3 — Put the code on GitHub

Streamlit Community Cloud deploys from a GitHub repo. From this folder:

```bash
cd annotation-platform
git init
git add app.py auth.py config.py db.py stages.py admin.py taxonomy.py requirements.txt README.md DEPLOY.md
git commit -m "Annotation platform"
# create an empty repo on GitHub, then:
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Do **not** commit `.streamlit/secrets.toml`, `data/`, or `sample_items.json` (the `.gitignore`
already excludes secrets and the local db). Secrets go in the Streamlit dashboard, not the repo.

## Step 4 — Deploy on Streamlit Community Cloud (free)

1. Go to https://share.streamlit.io, sign in with GitHub, and click **New app**.
2. Select your repo and branch, set the main file to `app.py`, and deploy.
3. Open **App settings → Secrets** and paste:

   ```toml
   ANNOTATOR_PASSWORD = "your-annotator-password"
   ADMIN_PASSWORD = "your-admin-password"
   DATABASE_URL = "postgresql+psycopg2://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres"
   PER_GENRE = "4"
   ```

4. Save. The app restarts and is live at your `*.streamlit.app` URL, password-protected.

## Notes

- The demo `sample_items.json` is only auto-seeded on local SQLite; it is never written to Supabase.
- To change passwords or the number of pairs per genre later, edit the Streamlit secrets and rerun.
- Export data anytime from the admin dashboard (log in with the admin password → Dashboard → Export).
- Back up: Supabase provides its own backups; you can also export the CSV periodically.
