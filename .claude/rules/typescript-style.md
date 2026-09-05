# TypeScript Style — `web/` only (backlog item 11)

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

- The Next.js route handler (`app/api/scans/route.ts`) is the **only** place that talks to
  `API_URL`. It parses the FastAPI response with a zod schema before returning it; the browser
  code never sees an unparsed body. Zod is the one runtime-validation dependency; no others.
- Schemas live in `web/src/api/schemas.ts`, one per endpoint response, named
  `<thing>Schema`; the inferred types are exported beside them (`ScanReport`, `DomainResult`,
  `Detection`, `Evidence`, `CollectionFailure`).
- A parse failure is an `error` state with a typed `ScanError`, never a thrown `Error` that
  reaches a component. Error codes mirror the API's `error.code` values.
- Requests are typed the same way: the body of `POST /api/scans` is validated with
  `scanRequestSchema` before the proxy call.

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
