# DVI Web (M6)

A static Next.js app: an editorial landing page plus an operator UI for
browsing detected incidents. Light editorial / precise visual system, with a
persistent header/footer, a signature "silent divergence" hero motif (two
series that track together until one quietly drifts while every structural
check stays green), and restrained motion throughout.

## Run locally

```bash
cd dvi
npm install
npm run dev      # http://localhost:3000
```

## Data seam

Every page reads incidents through `dvi/lib/data.ts`
(`getIncidents()` / `getIncident(id)`). Today it loads JSON bundled under
`dvi/content/incidents/`, generated from REAL pipeline runs:

```bash
python scripts/export_fixtures.py   # regenerates dvi/content/incidents/*.json
```

To serve live data later, replace the two loader bodies in `lib/data.ts`
with `fetch()` calls — no component changes needed.

## Design tokens

Colors, spacing, and motion live in `dvi/styles/tokens.css` (CSS custom
props) mirrored for motion in `dvi/components/motion/tokens.ts`. One brand
accent; severity colors are semantic and always paired with a text label.
All motion honors `prefers-reduced-motion`.

## Build & deploy

```bash
npm run build    # static export to dvi/out/
```

The app is a static export (`output: 'export'`), so it can be hosted anywhere
that serves files. It is served at the domain **root** (no base path).

### Vercel (production host)

Live at **[dvintelligence.vercel.app](https://dvintelligence.vercel.app)**.
`dvi/vercel.json` pins the Next.js framework preset and `trailingSlash`. Two
ways to deploy:

**A. Connect the GitHub repo (recommended, auto-deploys on push):**
1. In the Vercel dashboard: *New Project* → import `anuran-de/dvi`.
2. Set **Root Directory** to `dvi` (must match this folder, or Git builds fail
   with *"Couldn't find any pages or app directory"*).
3. Framework preset auto-detects **Next.js**; leave build/output defaults
   (Vercel handles the static export).
4. Deploy. Every push to `main` publishes a production deployment; PRs get
   preview URLs.

**B. From the CLI (one-off or scripted):**
```bash
npm i -g vercel
cd dvi
vercel            # first run links/creates the project (accept root = dvi)
vercel --prod     # promote to production
```

## Tests

```bash
npm test         # vitest unit tests
npm run e2e      # playwright smoke tests (builds + serves out/)
```
