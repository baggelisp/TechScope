# TypeScript Style — `web/` only (backlog item 12)

Applies to everything under `web/`. Two sources, in priority order:

1. **The `vspathonis-code-style` skill** — the user's house style for React/Next.js: page folder
   structure (`_components` / `_hooks`), one component per file, arrow-function components,
   `*Card` / `*Section` / `*Table` suffixes, `decide*` helpers resolved before the `return`,
   explicit props (no spread), translations, forms. It wins on every point it covers.
2. **This file** — type-level conventions the skill does not cover, taken from Matt Pocock's
   Total TypeScript guidance and trimmed to what this app needs.

When the two disagree, the skill wins (e.g. the skill's `src/utils/` utility classes stay).

## tsconfig — strict, Pocock's cheat-sheet baseline

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler"
  }
}
```

`noUncheckedIndexedAccess` is the one that matters for this app: `report.domains[0]` is
`DomainResult | undefined`, and the matrix code must handle it with a `decide*OrNull` helper,
never a `!`.

## Types

- **No `any`, no `as` casts, no `!` non-null assertions, no `@ts-ignore`.** If a type is hard,
  reshape the data or parse it at the boundary (below). `unknown` is allowed only as the input
  of a parser.
- **`type` over `interface`** for object shapes; `interface` only when a library requires
  declaration merging. Props types are `type <Component>Props = { … }` next to the component.
- **`as const` objects instead of `enum`.** Derive the union from the object:

  ```ts
  const CHANNEL = {
    header: 'header',
    cookie: 'cookie',
    scriptSrc: 'script_src',
    dnsMx: 'dns_mx',
  } as const

  type Channel = (typeof CHANNEL)[keyof typeof CHANNEL]
  ```

  The string values mirror the Python `ChannelEnum` values exactly; the API is the contract.
- **`satisfies` for config objects** (route maps, column definitions, colour tables) so the
  object keeps its literal type but is checked against the shape.
- **Discriminated unions for every state that has phases.** Never model a request with three
  independent booleans:

  ```ts
  type ScanState =
    | { status: 'idle' }
    | { status: 'scanning'; startedAt: number }
    | { status: 'success'; report: ScanReport }
    | { status: 'error'; error: ScanError }
  ```

  Branch with a `switch` on `status` and an exhaustive `default` that calls
  `assertNever(state)`. This is the TypeScript twin of the Python `match` + raising `case _`.
- **Generics only when a value flows through unchanged.** A component or helper with a type
  parameter that is used once is not generic; inline the concrete type.
- **Derive, don't duplicate.** Types of API responses come from the zod schemas
  (`z.infer<typeof scanReportSchema>`), never hand-written a second time. Derived views
  (`Pick`, `Omit`, mapped types) over copy-pasted shapes.

## The API boundary — parse, don't trust

- A **server action** in `web/src/app/actions/scans/` is the **only** place that talks to
  `API_URL`. It runs on the server, so the browser never learns the API's address and there is
  no CORS to arrange. It parses the response with a zod schema before returning it; no component
  ever sees an unparsed body. Zod is the one runtime-validation dependency; no others.
- Schemas live in `web/src/api/schemas.ts`, one per endpoint response, named
  `<thing>Schema`; the inferred types are exported beside them (`ScanReport`, `DomainResult`,
  `Detection`, `Evidence`, `Problem`).
- An action never throws at its caller. It returns
  `ActionResponse<T> = { success: true; data: T } | { success: false; error: { message, code } }`
  from `web/src/lib/utils/errors.ts`, and the page branches on it with an early return. Error
  codes mirror the API's `error.code` values.
- A parse failure is one of those failures, never an exception that reaches a component.

## Functions and absence (same spirit as `python-style.md`)

- `null` means absent; never `undefined`-vs-`null` mixtures in one type. Optional props use `?`
  and are read through a `decide*` helper that resolves the default before the JSX.
- `decide*` helpers are pure and typed on both ends; `decide*OrNull` when they may return
  `null`. Positive `if`, early return, blank line between blocks (see the skill).
- No inline ternaries in JSX attributes or returns; resolve into a named `const` first.
- Named handlers (`handleScanSubmit`), never inline arrow functions in JSX props.

## Lint and check

`npm run lint` (ESLint with `@typescript-eslint/no-explicit-any`,
`@typescript-eslint/consistent-type-definitions: type`, `no-restricted-syntax` banning `enum`)
and `npx tsc --noEmit` must be clean. They are not part of `make check`; they run in the
feature's own verification step and in the `reviewer` pass for `web/` changes.

## Pages

The app has two routed pages and they follow the skill's page-folder rules: one routed page per
folder, folders one level deep, page-local pieces in `_components/` and `_hooks/`.

- `/` is the form. It holds no result and knows nothing about scanning; submitting navigates.
- `/multi-scan-results` runs the scan for a list in its `page.tsx` as an async server component
  and renders `<PageError>` when the action fails. `loading.tsx` is the pending state.
- `/domain/<domain>` does the same for one domain, in full detail. One domain submitted on the
  form lands here, and so does a shared `/multi-scan-results` link carrying only one.

Putting the scan on the page that shows it is what removes the phase machine from the client:
with the result addressed by its URL, there is no `idle | scanning | success | error` union to
keep in step with anything, and a result can be reloaded, bookmarked and shared.

Everything under those pages is a server component. The evidence panels are native popovers
opened by the browser from an id, so a page full of them ships no JavaScript for them; the only
client components are the form, which owns what has been typed, and the download button, which
builds a file the browser then saves.

## Single language

The app ships in one language and carries no translation library. The rule the skill is really
making — no user-facing string written into markup — is kept by putting every one of them in
`web/src/constants/copy.constant.ts`.
