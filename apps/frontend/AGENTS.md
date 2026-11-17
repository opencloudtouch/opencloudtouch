# Frontend Agent Rules (`apps/frontend/`)

## Architecture & Conventions

- **Stack:** React 19, TypeScript strict mode, functional components only. Never import from `apps/backend/`.
- **State:** TanStack React Query for server state; local `useState`/`useReducer` for UI. No Redux or Zustand.
- **Structure:** PascalCase components in `components/`, `use*` camelCase hooks in `hooks/`, clients in `api/`, register pages in `App.tsx`.
- **API Types:** Use only `api/generated/` or `api/types.ts`. Regenerate via `npm run generate:api` after `openapi.yaml` changes.

## Ponytail Review/Audit Focus

- **No `any` or type assertions:** Fix types at the source; never bypass strict mode with `as any`.
- **Lean components:** Keep components focused; extract reusable logic into hooks only when used ≥ 2 times.

## Verification Commands

- **Tests:** `cd apps/frontend && npx vitest run` (Vitest 4, Testing Library, Cypress 15; ≥ 80% coverage)
- **Lint & Types:** `cd apps/frontend && npx eslint src/` and `npx tsc --noEmit` (Prettier + ESLint 9)
