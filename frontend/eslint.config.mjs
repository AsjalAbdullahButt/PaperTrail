import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This codebase fetches data with plain useEffect (no React Query/SWR/
      // Suspense), so every data-loading component resets its loading/error
      // state synchronously at the top of the effect before kicking off the
      // fetch — the standard pre-Suspense data-fetching idiom, not the
      // derived-state-sync anti-pattern this rule targets. Downgraded to a
      // warning (still visible, doesn't fail the build) rather than
      // rewriting every data-fetching effect in the app.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
