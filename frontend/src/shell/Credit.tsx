/** The licence credit under every page of a drawing (docs/API.md "GET /api/drawings/{id}"). Some credit
 * fields carry their own "Credit:" prefix and some do not: the line says it once either way. */
export function Credit({ credit }: { credit: string | null }) {
  const text = credit === null ? 'none recorded for this file' : credit.replace(/^credit:\s*/i, '');
  return <p className="credit">Credit: {text}</p>;
}
