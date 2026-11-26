/** Move focus to the page's h1 after in-app navigation or a successful Retry (DESIGN §6, WCAG 2.4.3). */
export function focusMainHeading(): void {
  const heading = document.querySelector<HTMLElement>("main h1");
  // With a #hash the browser scrolls to the anchor; do not fight it.
  heading?.focus({ preventScroll: window.location.hash !== "" });
}
