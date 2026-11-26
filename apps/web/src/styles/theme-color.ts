/**
 * `<meta name="theme-color">` values: the `--bg` token of each scheme. Next needs them as constants;
 * `tokens.test.ts` fails if they drift from `tokens.css`.
 */
export const THEME_COLOR = { light: "#f3f5f2", dark: "#0e1315" } as const;
