# WritingMirror Draft-Comparison Annotation Platform

A password-protected Streamlit app for a three-stage study in which annotators compare an author's
original draft with an AI-revised version.

Deployed on Render from the public Git URL (no GitHub authorization needed). See `DEPLOY_RENDER.md`.

## Roles (two passwords)

- **Annotator** (`ANNOTATOR_PASSWORD`): consent → enter name → receive a participant ID → tutorial →
  three annotation stages. All pairs in a stage must be completed before the next stage opens.
- **Admin** (`ADMIN_PASSWORD`): a dashboard (progress + CSV export) and a **preview mode** that walks
  the full annotation flow with gating off and without recording real data (rows flagged `is_preview`).

## Stages

1. **Describe the differences** — free-form, one difference per line. Taxonomy hidden.
2. **Rate specific dimensions** — Likert ratings (intention change, positivity, formality, voice,
   abstraction, added content) plus edit-type tags.
3. **Instruction and justification** — the author's instruction and prior conversation are revealed;
   the annotator marks which of their noted differences were not justified, and rates satisfaction.

## Run locally

```bash
cd annotation-platform
pip install -r requirements.txt
streamlit run app.py
```

The app creates a local SQLite database at `data/app.db` and seeds demo items from
`sample_items.json` on first run. Dev passwords are `annotate-dev` (annotator) and `admin-dev`
(admin); override them in `.streamlit/secrets.toml` (see `secrets.toml.example`).

## Loading real items

`sample_items.json` is a small demo set. To load the real 50-pair study set, use `db.upsert_items`
with records shaped `{pair_id, genre, original, revised, instruction, prior_conversation}`. A
corpus-sampling builder (stratified by genre) will populate this from the WildChat corpus.

## Deploy (later)

1. Create a free Supabase project; copy its Postgres connection string.
2. Push this folder to a GitHub repo.
3. On Streamlit Community Cloud, point at `app.py` and set secrets: `ANNOTATOR_PASSWORD`,
   `ADMIN_PASSWORD`, and `DATABASE_URL` (the Supabase string). Uncomment `psycopg2-binary` in
   `requirements.txt`. No code changes are needed to switch from SQLite to Postgres.

## Configuration

All settings live in `config.py` and can be overridden via secrets/env: passwords, `DATABASE_URL`,
and `PAIRS_PER_ANNOTATOR` (default 50). The taxonomy, Likert dimensions, consent text, and tutorial
text live in `taxonomy.py`.
