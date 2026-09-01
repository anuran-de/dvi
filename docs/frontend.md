# DVI Web (M6)

A static Next.js app: an editorial landing page plus an operator UI for
browsing detected incidents. Light editorial / precise visual system.

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

`.github/workflows/pages.yml` publishes `web/out` to GitHub Pages on merge
to `main` (base path `/dvi`). For Vercel, point it at `web/` with no base
path.

## Tests

```bash
npm test         # vitest unit tests
npm run e2e      # playwright smoke tests (builds + serves out/)
```
