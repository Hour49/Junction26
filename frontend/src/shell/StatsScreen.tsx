/** How it works: the pipeline explainer, a plain page (`public/stats.html`) shown inside the app shell. */
export function StatsScreen() {
  return <iframe className="stats-frame" src="/stats.html" title="How Vellum reads a floor plan" />;
}
