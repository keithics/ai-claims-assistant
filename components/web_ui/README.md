# web_ui

React + TypeScript single-page app (Vite, pnpm) for the claims assistant: chat with citations, the human approval screen, and a usage side panel. It talks only to `agent_app` over HTTP. There is no sign-in; access control comes from Cloudflare Access in front of the public hostname (see the notes in `FEATURES.md`), so run it locally or behind Access.

## Screens

- **Chat** (`/`): pick a country and language (the language list comes from the country pack; choosing a country switches to its main language and starts a new conversation), ask questions, read cited answers. Citations link to the source document (`/documents/:id`). Enter sends, Shift+Enter adds a line, and Enter does nothing while an IME composition is in progress (Japanese input works). A banner links to the approval screen when drafts are waiting.
- **Approvals** (`/approvals`): shows each drafted claim with Approve and Reject. Nothing is filed until Approve. Expired, already-used and offline cases are explained; an outage can be retried.
- **Usage panel** (collapsible, on the chat screen): route tier and reason, model, input, output and cached tokens, cost, time, cache hit, model calls and savings applied for every turn, plus a running total. The numbers come from the fields `agent_app` returns, never from telemetry stores.

## How it is built

- The API client is generated from `components/agent_app/openapi.json`: `pnpm gen:api`. Request and response types are never hand-written, and a test fails if `src/api/schema.d.ts` is stale.
- Runtime config is `public/config.json` (`apiBaseUrl` only), loaded when the page starts. No secrets or keys, and no `VITE_*` variables.
- All UI strings are in `src/i18n/locales/{en,fil,ceb,id,th,ja}.json`; a test checks all six have the same keys and placeholders. The translations are machine-written and not reviewed by native speakers.
- Thai and Japanese text carry `lang` attributes with CSS for line breaking and line height, so glyphs and wrapping render correctly.
- Accessible by default: labelled controls, skip link, landmarks, keyboard-operable, visible focus.

## Commands

- `pnpm dev` starts the dev server on port 5273 (an origin the API allows by default).
- `pnpm test` runs Vitest with React Testing Library. `pnpm lint` runs ESLint and Prettier. `pnpm build` type-checks and builds.
- `pnpm e2e` runs the Playwright happy path (see `make e2e`).
