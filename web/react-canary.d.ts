// `ViewTransition` ships in the React that Next bundles and resolves to at
// runtime, but not in the stable `react` package TypeScript reads. Its types
// live in a file @types/react does not load by default, so without this line
// `import { ViewTransition } from "react"` is a type error against a component
// that genuinely exists.
//
// A reference is used rather than a tsconfig "types" array on purpose: setting
// "types" would switch off automatic @types discovery for every other package.
/// <reference types="react/canary" />
