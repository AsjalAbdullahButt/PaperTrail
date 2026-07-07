# PaperTrail — Frontend

Next.js 16 (App Router, TypeScript) client for the PaperTrail RAG API.

## Setup

```bash
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL if the backend isn't on :8000
npm install
npm run dev                  # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` points at the backend (default `http://localhost:8000`).
It is inlined at build time, so set it before `npm run build`.

## Auth

Every data endpoint requires authentication. On first load you'll see a
sign-in / register screen; the JWT is stored in `localStorage` and sent as a
Bearer token. "Sign out" clears it.

## Features

- Ask questions in **RAG** (grounded, cited) or **Direct** mode.
- **Upload** PDF / TXT / Markdown documents.
- **Documents** panel: list your documents with chunk counts, delete with
  confirmation (empty / loading / error states).
- **History** panel: your past questions and answers.

## Scripts

```bash
npm run dev        # dev server
npm run build      # production build
npm run lint       # eslint
npm run test       # Vitest component tests
npm run test:e2e   # Playwright e2e (needs a live backend + `playwright install`)
```

## Design notes

- Styling is a hand-authored inline-style + CSS-variable theme system
  (light/dark). Tailwind was installed but unused, so it was removed.
- The ambient background is intentionally lightweight 2D (blurred layers +
  keyframes) with a mouse-parallax depth cue that respects
  `prefers-reduced-motion`.
