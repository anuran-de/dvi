# Deploying the web app to Vercel

The `web/` app is a static Next.js export (`output: 'export'` in
`web/next.config.mjs`). It already deploys to GitHub Pages under a
`/dvi` base path (`.github/workflows/pages.yml`); Vercel serves the same
app at the domain root with **no base path**. `basePath` is entirely
env-gated (`NEXT_PUBLIC_BASE_PATH`) — leave that variable **unset** on
Vercel and the GitHub Pages path is unaffected either way.

## Option A — Vercel dashboard (recommended)

1. Go to [vercel.com/new](https://vercel.com/new) and import the
   `anuran-de/dvi` GitHub repository.
2. In the project's **Configure** step, set:
   - **Root Directory:** `web`
   - **Framework Preset:** Next.js (auto-detected once the root directory
     is set — Vercel recognizes `output: 'export'` and serves the static
     export directly).
   - **Build Command / Output Directory:** leave as the framework
     defaults (`next build` / auto-detected `out`).
   - **Environment Variables:** none required. Do **not** set
     `NEXT_PUBLIC_BASE_PATH` — leaving it unset is what keeps the app
     served from `/` instead of `/dvi`.
3. Click **Deploy**. Every subsequent push to the connected branch
   redeploys automatically; PRs get preview deployments.

The repo root also ships a `vercel.json` (see below) so a deploy also
works if Root Directory is left at the repo root instead — it isn't
required when you set Root Directory to `web` as above, but it means the
project builds correctly either way.

## Option B — Vercel CLI

```bash
npm install -g vercel
cd web
vercel            # first run links/creates the project; accept the
                   # detected Next.js settings
vercel --prod      # subsequent production deploys
```

Running the CLI from inside `web/` is equivalent to setting Root
Directory to `web` in the dashboard.

## What the root `vercel.json` does

For the case where a deploy runs from the repository root (Root
Directory left unset — e.g. importing the monorepo without the dashboard
step above), `/vercel.json` explicitly points Vercel at the `web/`
subproject:

```json
{
  "buildCommand": "npm --prefix web ci && npm --prefix web run build",
  "installCommand": "npm --prefix web ci",
  "outputDirectory": "web/out",
  "framework": null
}
```

This does not set `NEXT_PUBLIC_BASE_PATH`, so the build still produces a
base-path-free static export at `web/out`, matching the Vercel option
above.

## Verifying locally

```bash
cd web
npm ci
npm run build      # NEXT_PUBLIC_BASE_PATH unset -> no basePath
npx serve out -l 4321
```

Open `http://localhost:4321` — routes should resolve at `/`,
`/incidents/`, and `/incidents/<id>/` with no `/dvi` prefix. Compare
against the GitHub Pages build, which prefixes every route with `/dvi`:

```bash
NEXT_PUBLIC_BASE_PATH=/dvi npm run build
```

## GitHub Pages stays untouched

`.github/workflows/pages.yml` is unchanged — it still builds with
`NEXT_PUBLIC_BASE_PATH=/dvi` and publishes `web/out` via
`actions/deploy-pages`. The two deploy targets are independent: Pages
gets the `/dvi`-prefixed build from CI, Vercel gets the base-path-free
build from its own build step.
