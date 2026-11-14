/** The licence credit under every page of a drawing (docs/API.md "GET /api/drawings/{id}"). */
export function Credit({ credit }: { credit: string | null }) {
  return <p className="credit">Credit: {credit ?? 'none recorded for this file'}</p>;
}
