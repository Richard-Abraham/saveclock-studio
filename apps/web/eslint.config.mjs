import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import boundaries from "eslint-plugin-boundaries";
import jsxA11y from "eslint-plugin-jsx-a11y";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores([".next/**", "coverage/**", "next-env.d.ts", "node_modules/**"]),
  ...nextVitals,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  { rules: { ...jsxA11y.configs.recommended.rules } },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/ban-ts-comment": [
        "error",
        { "ts-expect-error": "allow-with-description", "ts-ignore": true, "ts-nocheck": true },
      ],
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "no-console": "error",
      // SEC-112: no raw HTML injection.
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is banned (SEC-112).",
        },
      ],
      // STANDARDS §3: components never call fetch; only the generated client in src/lib/api does.
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Use the generated client in src/lib/api." },
        { name: "XMLHttpRequest", message: "Use the generated client in src/lib/api." },
      ],
    },
  },
  { files: ["src/lib/api/**"], rules: { "no-restricted-globals": "off" } },
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      "boundaries/elements": [
        { type: "ui", pattern: "src/components/ui/**" },
        { type: "feature", pattern: "src/components/features/**" },
        { type: "app", pattern: "src/app/**" },
        { type: "lib", pattern: "src/lib/**" },
      ],
    },
    rules: {
      "boundaries/dependencies": [
        "error",
        {
          default: "allow",
          policies: [
            {
              from: { element: { type: "ui" } },
              disallow: { to: { element: { types: ["feature", "app"] } } },
              message: "components/ui is a leaf: it may not import features or app code.",
            },
            {
              from: { element: { type: "feature" } },
              disallow: { to: { element: { type: "app" } } },
              message: "features may not import from app/ (pages compose features, not the reverse).",
            },
            {
              from: { element: { type: "lib" } },
              disallow: { to: { element: { types: ["ui", "feature", "app"] } } },
              message: "lib is framework-free: it may not import components or app code.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "tests/**"],
    rules: {
      "no-restricted-globals": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },
  { files: ["**/*.mjs"], ...tseslint.configs.disableTypeChecked },
]);
