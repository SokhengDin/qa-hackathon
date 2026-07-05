# task_1.md — Evidence Dashboard (Web)

Companion to `CLAUDE.md`. Read `CLAUDE.md` first — this task assumes the ADK pipeline,
schemas, and callbacks described there already exist or are being built in parallel. This
document specifies **one new piece**: a Next.js app, inside the same monorepo, that reads
the pipeline's own data and displays it.

## 0. Read this before writing any code — the framing that keeps us out of disqualification

The hackathon rules state: **"any project where a dashboard is the main feature" is
disqualified.** This is a real constraint, not a formality, and it changes how this task
must be built and pitched.

This dashboard is **not the product.** The product is the autonomous pipeline in
`src/qa_sentinel/` — TestRunner finds a bug, FixWriter fixes it, Verifier confirms it,
PRAgent opens a PR. That pipeline runs and produces value with **zero web UI involved.**
The dashboard is a **read-only window into a database the pipeline was already writing to**
— it exists so a judge or a developer can *see* what the agent did, not so a human operates
the agent through it. There is no "click here to start a test" button, no manual triage
queue as the centerpiece, no control panel. If a page in this app lets someone *do* agent
work rather than *observe* agent work, that page is scope creep — cut it.

When pitching: this dashboard gets maybe 20 seconds of stage time, to show one session's
evidence trail. The PR screenshot and the live pipeline run get the rest. If Claude Code
(or anyone) finds themselves adding features to this app beyond "list sessions, show
evidence, show the PR link," stop and re-read this section.

## 1. What this app does, concretely

Three views, nothing else:

1. **Session list** — every pipeline run (a "session" = one invocation of the root
   `Workflow` against one `TestCriteria`), most recent first, with an at-a-glance status
   per feature step (passed / failed / fixed_and_verified / blocked).
2. **Session detail** — one session, showing its steps in dependency order, each step
   expandable to reveal its `EvidenceBundle` (screenshot, console errors, network failures,
   model's stated intent, confidence score) and, if a fix was written, the resulting PR link
   and the `Verifier` re-check result.
3. **Review action** (the one interactive element allowed) — for **low-confidence** steps
   only, a human can record a `ReviewDecision` (approve / reject / false_positive). This is
   the human-in-the-loop feedback the track's own examples emphasize. This is a single
   button + optional note field, not a queue management system.

That's the whole app. No auth system, no user management, no settings page, no
notifications — this is a hackathon demo artifact, built to be readable by a judge in under
a minute per session.

## 2. Database choice: Postgres (already in docker-compose), not a second database

`CLAUDE.md` §17 already provisions a `postgres` service for evidence bundles, session state,
and review decisions. **Use that same database.** Do not add MongoDB or any second data
store.

Why this holds up even now that the dashboard is a first-class consumer of the data:

- The actual shape of this data is **relational with some flexible JSON inside it** —
  sessions have steps, steps have one evidence bundle, evidence bundles have console/network
  arrays of varying shape. Postgres's `jsonb` column type handles the "varying shape" part
  natively, while foreign keys give you the session→step→evidence integrity a document store
  would make you re-implement in application code.
- One database means the **ADK pipeline and the Next.js dashboard read/write the exact same
  rows** — no sync job, no "which database has the source of truth" question, no risk of the
  dashboard showing stale data because a second store lagged.
- It's already provisioned. Adding Mongo means a second docker-compose service, a second
  connection pool, a second set of credentials — real hackathon-weekend time spent on
  plumbing that buys nothing here.

If you strongly want Mongo for the "nicer for JSON" feeling: the honest answer is `jsonb`
already gives you that, queryable with real SQL (`WHERE evidence->'console_errors' @>
'[...]'`), with less operational surface. Stick with Postgres unless a concrete requirement
emerges that jsonb genuinely can't satisfy — none has so far.

## 3. Monorepo placement

```
.
├── CLAUDE.md
├── task_1.md                         # this file
├── PROJECT_STRUCTURE.md
├── pyproject.toml                    # Python side, unchanged
├── docker-compose.yml                # add the "web" service here, see §7
├── src/qa_sentinel/                  # Python pipeline, unchanged — see CLAUDE.md
├── docs/                             # unchanged
├── demo_target_app/                  # unchanged
│
└── web/                               # <- NEW: the Next.js app lives here
    ├── package.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── postcss.config.mjs             # Tailwind v4 — see §5
    ├── prisma/
    │   ├── schema.prisma              # §4 — mirrors the Python pydantic schemas
    │   └── migrations/
    ├── src/
    │   ├── app/
    │   │   ├── globals.css            # Tailwind v4 CSS-first config — see §5
    │   │   ├── layout.tsx
    │   │   ├── page.tsx                # redirects to /sessions
    │   │   ├── sessions/
    │   │   │   ├── page.tsx            # session list (Server Component)
    │   │   │   └── [sessionId]/
    │   │   │       └── page.tsx        # session detail (Server Component)
    │   │   └── actions/
    │   │       └── review.ts           # Server Action: submit a ReviewDecision
    │   ├── components/
    │   │   ├── SessionList.tsx
    │   │   ├── SessionList.Row.tsx
    │   │   ├── StepTimeline.tsx        # ordered by depends_on, shows status badges
    │   │   ├── EvidencePanel.tsx       # expandable: screenshot + console + network + intent
    │   │   ├── ConfidenceBadge.tsx     # visual for high/medium/low, §6 of CLAUDE.md
    │   │   ├── PRLink.tsx
    │   │   └── ReviewForm.tsx          # the one interactive element, client component
    │   └── lib/
    │       ├── db.ts                    # Prisma client singleton
    │       └── types.ts                 # shared TS types mirroring the Python schemas
    └── public/
```

The Python side never imports from `web/`, and `web/` never runs Python. The only
connection between them is the shared Postgres database — the pipeline writes rows, the
dashboard reads them. This is intentional: it keeps the two halves independently
deployable/runnable, and it means a bug in the dashboard can never break the pipeline.

## 4. Prisma schema — mirrors the pydantic schemas in `CLAUDE.md` §6 exactly

The pipeline (Python/asyncpg or Python/SQLAlchemy — whichever `state/session_store.py`
ends up using) and the dashboard (TypeScript/Prisma) must agree on table shape. Prisma owns
the migrations; the Python side connects to the same tables without its own migration tool,
to avoid two systems fighting over schema ownership.

```prisma
// web/prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Session {
  id           String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  appName      String   @map("app_name")
  baseUrl      String   @map("base_url")
  createdAt    DateTime @default(now()) @map("created_at")
  steps        Step[]

  @@map("sessions")
}

model Step {
  id             String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  sessionId      String   @map("session_id") @db.Uuid
  session        Session  @relation(fields: [sessionId], references: [id])
  stepId         String   @map("step_id")           // matches TestStep.step_id, human-readable
  instruction    String
  dependsOn      String[] @map("depends_on")
  expectedOutcome String  @map("expected_outcome")
  status         String   @default("pending")        // pending | passed | failed | blocked | fixed_and_verified
  evidence       Evidence?
  reviewDecision ReviewDecision?
  prUrl          String?  @map("pr_url")
  createdAt      DateTime @default(now()) @map("created_at")

  @@unique([sessionId, stepId])
  @@map("steps")
}

model Evidence {
  id                 String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  stepId             String   @unique @map("step_id") @db.Uuid
  step               Step     @relation(fields: [stepId], references: [id])
  screenshotPath     String   @map("screenshot_path")
  consoleErrors      Json     @map("console_errors")      // jsonb — array of {level, text, url, ...}
  networkFailures    Json     @map("network_failures")     // jsonb — array of {url, status, method, ...}
  modelStatedIntent  String   @map("model_stated_intent")
  confidence         Float
  timestamp          DateTime @default(now())

  @@map("evidence_bundles")
}

model ReviewDecision {
  id           String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  stepId       String   @unique @map("step_id") @db.Uuid
  step         Step     @relation(fields: [stepId], references: [id])
  decision     String                                       // approved | rejected | false_positive
  reviewerNote String?  @map("reviewer_note")
  createdAt    DateTime @default(now()) @map("created_at")

  @@map("review_decisions")
}
```

Note the `@db.Uuid` + `dbgenerated("uuid_generate_v4()")` pattern throughout — this matches
the standing preference (UUID primary keys, `uuid_generate_v4()`, never `SERIAL`) and must
be paired with `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";` (or `pgcrypto`) in an init
migration, run once against the shared Postgres service.

`consoleErrors` and `networkFailures` are `Json` (→ Postgres `jsonb`) because their internal
shape comes straight from chrome-devtools-mcp's own tool output and shouldn't be forced into
a rigid relational shape — this is the one place a flexible column earns its keep, exactly
as described in §2.

## 5. Tailwind CSS v4 setup — CSS-first, no config file

Tailwind v4 removes `tailwind.config.js` entirely in favor of CSS-first configuration via
`@theme`, and content scanning is automatic — no content-path array to maintain.

```bash
cd web
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir
```

This scaffolds Tailwind v4 automatically on current Next.js versions. Confirm
`package.json` shows `tailwindcss` at v4.x and `postcss.config.mjs` references
`@tailwindcss/postcss` — if it scaffolded v3 instead, follow Tailwind's own Next.js install
guide to upgrade before writing any components.

```css
/* web/src/app/globals.css */
@import "tailwindcss";

@theme {
  --color-status-passed:   oklch(0.72 0.19 149);   /* green */
  --color-status-failed:   oklch(0.63 0.24 29);    /* red */
  --color-status-blocked:  oklch(0.75 0.15 85);    /* amber */
  --color-status-fixed:    oklch(0.65 0.18 250);   /* blue */

  --color-confidence-high:   var(--color-status-passed);
  --color-confidence-medium: var(--color-status-blocked);
  --color-confidence-low:    var(--color-status-failed);
}
```

Use these as `bg-status-passed`, `text-confidence-low`, etc. — Tailwind v4 exposes every
`@theme` token as both a utility class and a real CSS custom property, so the same tokens
are usable from inline `style` props if a chart library needs raw values.

No dark mode toggle needed for a hackathon demo — pick one theme (dark, for a "developer
tool" aesthetic that suits a QA agent) and ship it; don't spend time on a light/dark switch
nobody will use during a 3-minute pitch.

## 6. Data flow — Server Components read, one Server Action writes

This app should do almost everything in **Server Components** with **no client-side data
fetching** — the whole app is read-mostly, so there's no reason to ship a client-side
fetch/loading-state dance for the session list or evidence panels.

```typescript
// web/src/app/sessions/page.tsx
import { db } from "@/lib/db";

export default async function SessionsPage() {
  const sessions = await db.session.findMany({
    orderBy: { createdAt: "desc" },
    include: { steps: { select: { status: true } } },
  });

  return <SessionList sessions={sessions} />;
}
```

```typescript
// web/src/app/sessions/[sessionId]/page.tsx
import { db } from "@/lib/db";
import { notFound } from "next/navigation";

export default async function SessionDetailPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  const session = await db.session.findUnique({
    where: { id: sessionId },
    include: {
      steps: {
        include: { evidence: true, reviewDecision: true },
        orderBy: { createdAt: "asc" },
      },
    },
  });

  if (!session) notFound();

  return <StepTimeline session={session} />;
}
```

The **only** write path in the whole app is the review decision, and it's a Server Action —
no separate API route needed:

```typescript
// web/src/app/actions/review.ts
"use server";

import { db } from "@/lib/db";
import { revalidatePath } from "next/cache";

export async function submitReviewDecision(
  stepId: string,
  decision: "approved" | "rejected" | "false_positive",
  reviewerNote: string | null,
) {
  await db.reviewDecision.create({
    data: { stepId, decision, reviewerNote },
  });

  revalidatePath(`/sessions`);
}
```

`revalidatePath` is enough here — this is a hackathon demo, not a production system needing
websocket live-updates. If the pipeline is running live during the demo and you want the
session list to visibly update without a manual refresh, a simple `setInterval` +
`router.refresh()` in a small client wrapper around the session list is enough; do not build
a websocket/SSE layer for this — it's not worth the build time relative to what it adds to
the pitch.

## 7. Docker Compose — add one service to the existing file

Extend the compose file already specified in `CLAUDE.md` §17 with a `web` service. Do not
create a second `docker-compose.yml` — one file, one `docker compose up` for the whole repo.

```yaml
# addition to the existing docker-compose.yml
  web:
    build:
      context:    ./web
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://qa_sentinel:${POSTGRES_PASSWORD}@postgres:5432/qa_sentinel
    depends_on:
      - postgres
    ports:
      - "3000:3000"
    networks:
      - qa-net
```

`web/Dockerfile` — standard multi-stage Next.js build (`npm ci`, `npx prisma generate`,
`npm run build`, then a slim runtime stage with `npm start`). Nothing unusual here; don't
over-engineer the Dockerfile for a demo weekend — a working two-stage build is enough.

## 8. Confidence badge — the one visual that must be unmistakable to a judge

Since the confidence score (`CLAUDE.md` §7) is the genuine differentiator in the pitch — "the
agent knows what it doesn't know" — the dashboard's single most important visual element is
making that score legible at a glance, not burying it in a detail panel.

```tsx
// web/src/components/ConfidenceBadge.tsx
type Confidence = "high" | "medium" | "low";

function bucket(score: number): Confidence {
  if (score >= 0.8) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

const LABEL: Record<Confidence, string> = {
  high:   "High confidence — auto-fixed",
  medium: "Medium confidence — partial evidence",
  low:    "Low confidence — needs human review",
};

export function ConfidenceBadge({ score }: { score: number }) {
  const level = bucket(score);
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium
                  bg-confidence-${level}/15 text-confidence-${level}`}
    >
      <span className={`h-2 w-2 rounded-full bg-confidence-${level}`} />
      {LABEL[level]}
    </span>
  );
}
```

This badge should appear on every step row in the session list *and* at the top of the
evidence panel — it's the recurring visual motif that carries the "this agent knows its own
limits" story through the whole demo.

## 9. What NOT to build (explicit, because scope creep is the real risk here)

- No authentication/login — local demo only.
- No pagination beyond a simple "load more" if the session list gets long during
  development — a `LIMIT`/`OFFSET` query is enough, no infinite-scroll library.
- No charts/analytics/aggregate dashboards ("bugs found over time," "average confidence
  trend") — this is exactly the kind of feature that turns an evidence viewer into "a
  dashboard is the main feature." Resist adding it even if it looks impressive; it dilutes
  the pitch and risks the disqualification rule.
- No websocket/SSE real-time layer — `router.refresh()` on an interval is sufficient.
- No editing of evidence, steps, or sessions — this app is read-only except for the single
  review-decision action in §6.
- No second database. See §2.

## 10. Build order for this task

1. `web/` scaffold via `create-next-app --tailwind --typescript --app --src-dir`, confirm
   Tailwind v4 landed (not v3) per §5.
2. `web/prisma/schema.prisma` per §4, run the `uuid-ossp`/`pgcrypto` extension migration
   first, then `npx prisma migrate dev`.
3. `web/src/lib/db.ts` — Prisma client singleton (standard pattern: instantiate once, reuse
   across Server Component invocations, guard against multiple instances in dev via
   `globalThis`).
4. Seed a handful of fake `Session`/`Step`/`Evidence` rows directly via `prisma db seed` or a
   one-off script, so the UI can be built and demoed **before** the Python pipeline is
   writing real rows — do not block dashboard work on pipeline completion.
5. `sessions/page.tsx` + `SessionList.tsx` — the list view.
6. `sessions/[sessionId]/page.tsx` + `StepTimeline.tsx` + `EvidencePanel.tsx` +
   `ConfidenceBadge.tsx` — the detail view.
7. `actions/review.ts` + `ReviewForm.tsx` — the one write path.
8. Wire the `web` service into the root `docker-compose.yml` per §7.
9. Once `src/qa_sentinel/state/session_store.py` (from `CLAUDE.md`) is writing real rows to
   the same tables, delete the seed data and confirm the dashboard reflects a real pipeline
   run end to end.

Do this in parallel with the Python pipeline work, not after it — steps 1–7 need no real
agent data, only the schema, which is already fixed in `CLAUDE.md` §6.