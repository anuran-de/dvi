# DVI Web (M6)

A static Next.js app: an editorial landing page plus an operator UI for
browsing detected incidents. Light editorial / precise visual system, with a
persistent header/footer, a signature "silent divergence" hero motif (two
series that track together until one quietly drifts while every structural
check stays green), and restrained motion throughout.

## Run locally

```bash
cd web
npm install
npm run dev      # http://localhost:3000
```

## Data seam

Every page reads incidents through `web/lib/data.ts`
(`getIncidents()` / `getIncident(id)`). Today it loads JSON bundled under
`web/content/incidents/`, generated from REAL pipeline runs:

```bash
python scripts/export_fixtures.py   # regenerates web/content/incidents/*.json
```

To serve live data later, replace the two loader bodies in `lib/data.ts`
with `fetch()` calls — no component changes needed.

## Design tokens

Colors, spacing, and motion live in `web/styles/tokens.css` (CSS custom
props) mirrored for motion in `web/components/motion/tokens.ts`. One brand
accent; severity colors are semantic and always paired with a text label.
All motion honors `prefers-reduced-motion`.

## Build & deploy

```bash
npm run build    # static export to web/out/
```

The app is a static export (`output: 'export'`), so it can be hosted anywhere
that serves files. `basePath` is env-gated via `NEXT_PUBLIC_BASE_PATH`:
unset = served at the domain root, set = served under a sub-path.

### GitHub Pages

`.github/workflows/pages.yml` publishes `web/out` to GitHub Pages on merge to
`main` with `NEXT_PUBLIC_BASE_PATH=/dvi` (the repo sub-path). No action needed
beyond enabling Pages (Settings → Pages → Source: GitHub Actions).

### Vercel

Vercel serves the app at the domain **root**, so leave `NEXT_PUBLIC_BASE_PATH`
**unset** there (do not set it). `web/vercel.json` pins the Next.js framework
preset and `trailingSlash`. Two ways to deploy:

**A. Connect the GitHub repo (recommended, auto-deploys on push):**
1. In the Vercel dashboard: *New Project* → import `anuran-de/dvi`.
2. Set **Root Directory** to `web`.
3. Framework preset auto-detects **Next.js**; leave build/output defaults
   (Vercel handles the static export). Do **not** add `NEXT_PUBLIC_BASE_PATH`.
4. Deploy. Every push to `main` publishes a production deployment; PRs get
   preview URLs.

**B. From the CLI (one-off or scripted):**
```bash
npm i -g vercel
cd web
vercel            # first run links/creates the project (accept root = web)
vercel --prod     # promote to production
```

GitHub Pages and Vercel coexist: the base-path difference is the only knob,
and it is environment-driven, so the same commit deploys correctly to both.

## Tests

```bash
npm test         # vitest unit tests
npm run e2e      # playwright smoke tests (builds + serves out/)
```
