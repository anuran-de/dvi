# M6 — Frontend (Landing + Operator UI) Design

**Status:** approved-for-planning
**Date:** 2026-09-01
**Milestone:** M6 — "Operator experience" (final roadmap milestone)

## 1. Purpose

DVI's detection engine, warehouse pushdown, CLI, and GitHub Action are all
shipped (M1–M5b). M6 gives DVI a **face**: a professional landing page that
tells the product story, and a sleek operator UI for viewing detected
incidents. It must read as a deliberately-designed, engineering-credible
product — **not** a generic AI-generated template.

The guiding principle still holds: **when breadth vs. reliability conflict,
reliability wins.** The UI never invents meaning — it presents what the
deterministic engine already produced.

## 2. Scope

**In scope**
- A marketing/product **landing page**.
- An **incident dashboard** (list, filter, sort).
- An **incident detail** view: timeline, evidence, blast-radius graph,
  business-impact panel.
- A **data seam** (`lib/data.ts`) that loads incidents from bundled JSON
  fixtures today and can be swapped for a live API later with no UI changes.
- **Curated fixtures generated from real `dvi analyze` runs** — no invented
  incident data.
- A **motion system** (tokenized, `prefers-reduced-motion`-respecting).
- Tests + CI gate + static export build.

**Out of scope (explicitly deferred)**
- A live backend / API serving the pipeline (the seam is designed for it; the
  server is not built here).
- Authentication, multi-tenant, persistence.
- Editing/triaging incidents (read-only presentation only).

## 3. Decisions (locked with the user)

| Decision | Choice |
|----------|--------|
| Stack | **Next.js (App Router) + TypeScript + Tailwind CSS + Framer Motion** |
| Data source | **Curated JSON fixtures from real `dvi analyze` runs**, behind one loader seam |
| UI scope | **Landing + dashboard + incident detail** |
| Build/deploy | **Static export** (`output: 'export'`) → GitHub Pages / Vercel; no server |
| Visual direction | **Light editorial / precise** |

## 4. Visual identity — "light editorial / precise"

The anti-AI-slop discipline: a committed, consistent system — not a pile of
effects. Explicitly avoided tells: purple/rainbow gradients, glassmorphism,
emoji as UI, uniform pill-rounded floating cards, `Inter` as the default body
face, a different random animation on every element, centered-everything
hero soup.

**Canvas & ink**
- Background: warm off-white `#FAFAF7`; secondary surfaces a hair darker
  (`#F2F1EC`).
- Ink (text): warm near-black `#1A1A18`; muted ink `#6B6A63` for secondary.
- Borders: hairline `1px` warm grey `#E3E1D9` — sharp corners or a small
  `2–4px` radius only; no large pill rounding on structural elements.

**One brand accent (distinct from severity)**
- Accent ink: a deep, restrained `#1F3A5F` (ink-blue) used sparingly for
  links, focus rings, and the primary CTA. Exactly one accent — not a palette.

**Severity is semantic, not brand** (muted for editorial feel)
- low `#3F7A5E` (muted green) · medium `#B07A2E` (amber) ·
  high/critical `#A23B34` (deep red). Rendered as small solid tags, never
  emoji.

**Typography (three roles, deliberate pairing)**
- Display / headlines: a high-quality **serif** — recommended `Newsreader`
  (or `Fraunces`), variable, self-hosted via `next/font`.
- Body / UI: a clean **grotesk** — recommended `Geist Sans` (NOT `Inter`).
- Data / numbers / code / labels: a **monospace** — recommended `Geist Mono`
  (or `IBM Plex Mono`). All asset names, magnitudes, confidences, timestamps
  render in mono so data reads as data.
- Type scale is a fixed modular scale; large editorial display sizes on the
  landing hero, tight functional sizes in the app.

**Layout**
- A real grid with generous whitespace on the landing page; denser, calm
  grid in the app. Left-aligned editorial composition, not centered blocks.

**Accessibility**
- All text pairs meet WCAG AA contrast on the off-white canvas. Focus states
  are visible (accent ring). Severity is never encoded by color alone (always
  paired with its text label).

## 5. Architecture & repo layout

```
web/
  app/
    layout.tsx              # root layout, fonts, page-transition wrapper
    page.tsx                # Landing
    incidents/
      page.tsx              # Dashboard (list)
      [id]/page.tsx         # Incident detail
    not-found.tsx
  components/
    landing/                # Hero, HowItWorks, SignatureShowcase, CTA
    incident/               # IncidentList, IncidentRow, SeverityTag,
                            # Timeline, EvidenceList, BlastRadiusGraph,
                            # BusinessImpactPanel
    ui/                     # primitives: Tag, Stat, Card, Prose, Container
    motion/                 # Reveal, PageTransition, motion tokens
  lib/
    data.ts                 # THE SEAM: getIncidents(), getIncident(id)
    types.ts                # Incident TS types (mirror render_json)
    format.ts               # number/percent/date formatting helpers
  content/
    incidents/*.json        # curated fixtures (real dvi output)
  styles/
    tokens.css              # CSS custom props: color, space, radius, motion
  tests/                    # vitest unit tests
  e2e/                      # playwright smoke tests
  next.config.mjs           # output: 'export'
  tailwind.config.ts
  package.json
scripts/
  export_fixtures.py        # runs the real pipeline, writes web/content/incidents/*.json
```

**The data seam.** Every page reads incidents through `lib/data.ts`:

```ts
export interface IncidentSummary {
  id: string; asset: string; severity: Severity;
  title: string; confidence: number | null;
  detectedAt: string; changeAt: string;
}
export interface IncidentDetail extends IncidentSummary {
  summary: string;
  evidence: string[];
  rootCause: { label: string; targets: string[]; timestamp: string };
  affectedAssets: string[];
  businessImpact: {
    exposures: { name: string; type: string; criticality: string; owner: string | null }[];
    maxCriticality: string | null;
  } | null;
}
export async function getIncidents(): Promise<IncidentSummary[]>
export async function getIncident(id: string): Promise<IncidentDetail | null>
```

Today these read from `content/incidents/*.json`. Swapping to a live API is a
one-file change; no component imports fixtures directly.

## 6. Fixtures — grounded in real output

`scripts/export_fixtures.py` runs the **real** DVI pipeline (the same
`analyze_change` / `analyze_change_from_profiles` the CLI uses) over the
diamonds dataset plus the existing synthetic scenarios, and serializes each
resulting `Incident` to `web/content/incidents/<id>.json` using the same
field shape as `render_json` (plus `change_at`/`detected_at`/root-cause
`label`+`targets`, which already exist on the `Incident` model). A clean run
(no incident) is included so the dashboard's empty/green state is real too.
No incident field is hand-authored.

## 7. Pages

### 7.1 Landing (`app/page.tsx`)
- **Hero:** the one hard problem stated plainly — every structural check
  green, the business number silently wrong — in large editorial display
  type; one accent CTA ("See a detected incident" → dashboard) and a
  secondary link to the GitHub repo.
- **How it works:** the pipeline as a narrative — profile → detect → rank →
  blast radius — each step revealed on scroll.
- **Signature showcase:** the flagship signatures (value substitution,
  distribution shift, etc.) as concise, data-styled cards.
- **Proof / credibility:** the calibration/benchmark numbers already in the
  README (deterministic, measured — not marketing fluff).
- **Footer CTA:** install line (`pip install dvi`) + repo link.

### 7.2 Dashboard (`app/incidents/page.tsx`)
- A calm, dense list of incidents: severity tag, asset (mono), title,
  confidence, detected-at.
- Filter by severity; sort by severity/confidence/recency. Deterministic
  ordering.
- Empty-state and all-clear (green) handled explicitly.
- Row → detail via a shared-layout transition.

### 7.3 Incident detail (`app/incidents/[id]/page.tsx`)
- **Header:** severity tag, title, confidence, asset.
- **Timeline:** `change_at → detected_at` rendered as a horizontal temporal
  strip, drawing in on view.
- **Evidence:** the engine's evidence bundle, mono-styled.
- **Blast-radius graph:** change target → downstream affected assets →
  external exposures, nodes colored by criticality, edges animated to draw
  once on view (Recharts or a small hand-rolled SVG/D3 layout; deterministic
  layout, no physics jitter).
- **Business-impact panel:** exposures table (name, type, criticality,
  owner), max criticality highlighted.
- Static export requires `generateStaticParams()` over all fixture ids.

## 8. Motion system

- Tokens in `styles/tokens.css` + a TS mirror: durations (`--motion-fast
  160ms`, `--motion-base 240ms`, `--motion-slow 420ms`) and **2–3 easing
  curves only** (a standard ease-out, a gentle spring for shared-layout).
  Every animation references these — that consistency is what reads as
  "designed."
- **Page transitions:** Framer Motion `AnimatePresence` wrapper in the root
  layout (fade + small rise).
- **Scroll reveal:** a single `Reveal` component (intersection-observer
  driven) used for landing sections; no bespoke per-element animation.
- **Shared-layout:** dashboard row → detail header via `layoutId`.
- **Graph/timeline:** draw-on-view once, then static.
- **`prefers-reduced-motion: reduce`** → all of the above collapse to instant
  or a minimal opacity change. This is asserted in tests, not just intended.

## 9. Testing & CI

- **Unit (Vitest + RTL):** the data seam (fixtures load + shape),
  formatting helpers, `SeverityTag`, `IncidentList` filter/sort determinism,
  `BlastRadiusGraph` renders expected node/edge counts from a fixture.
- **E2E (Playwright):** smoke the three routes render; nav landing →
  dashboard → detail works; reduced-motion path renders content.
- **CI:** extend `.github/workflows/ci.yml` with a `web` job — `npm ci`,
  typecheck, lint, unit tests, `next build` (static export must succeed),
  Playwright smoke. Fixtures are checked in, so the web job needs no Python.
- **Determinism:** incident ordering and graph layout are deterministic
  (consistent with the repo's `PYTHONHASHSEED` discipline).

## 10. Deployment

- `next.config.mjs` sets `output: 'export'`; `next build` emits static files.
- A GitHub Pages workflow (or Vercel) publishes on merge to `main`. Base-path
  handled for project-pages hosting.
- Zero server; the site is a static bundle over checked-in fixtures.

## 11. Documentation

- `docs/frontend.md`: how to run (`npm run dev`), regenerate fixtures
  (`python scripts/export_fixtures.py`), the data seam and how to point it at
  a live API later, the design tokens, and the deploy path.
- README roadmap row **M6 → ✅** with a screenshot; CHANGELOG entry.

## 12. Non-goals / risks

- **Not** a live analytical backend — deferred; the seam de-risks it.
- **Font licensing:** only self-hostable OSS faces (Newsreader/Fraunces,
  Geist, IBM Plex) via `next/font` — no proprietary fonts, no external CDN
  calls at runtime.
- **Graph complexity:** blast-radius layout stays deterministic and small
  (fixtures are modest); no force-directed physics that jitters between
  renders.
- **Motion overload:** the tokenized system + a single `Reveal` primitive is
  the guard against "as many transitions" becoming chaos — many transitions,
  one vocabulary.

## 13. Definition of done

- `web/` builds to a static export with no errors.
- All three page types render from real-run fixtures.
- Motion is smooth, consistent, and fully reduced-motion-safe.
- Unit + E2E tests green; CI `web` job gates them.
- Docs updated; README roadmap marks M6 delivered.
- The result reads as a deliberately-designed product, meeting the light
  editorial / precise system above.
