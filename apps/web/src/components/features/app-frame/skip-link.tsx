export function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only rounded-control border border-ink bg-surface px-3 py-2 text-ink focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
    >
      Skip to content
    </a>
  );
}
