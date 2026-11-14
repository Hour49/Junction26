// Where an issue of the two kinds that land on fe-surveyor's / the ask screens goes (conflicts.md CF-34).
// fe-ingest's issues screen calls this for `conflict` and `refused_answer` and builds the other kinds itself.
import { routeHref } from '../shell/route';

/** The fields read; structural, so the issues screen's `Issue` (#142) fits as is. */
export interface IssueLink {
  kind: string;
  drawing_id: string | null;
  quantity: string | null; // the takeoff Row.key
  question: string | null;
}

const withPack = (query: Record<string, string>, pack?: string | null) =>
  new URLSearchParams(pack ? { ...query, pack } : query);

/** The screen route for a conflict or refused-answer issue; null for every other kind. Never `issue.links` (API paths). */
export function issueRoute(
  issue: IssueLink,
  projectId: string,
  pack?: string | null,
): string | null {
  const { drawing_id: drawingId, quantity, question } = issue;
  if (issue.kind === 'conflict') {
    const card: Record<string, string> =
      drawingId !== null && quantity !== null ? { d: drawingId, q: quantity } : {};
    return routeHref({ name: 'conflicts', projectId, query: withPack(card, pack) });
  }
  if (issue.kind === 'refused_answer') {
    const query = withPack({ ask: question ?? '' }, pack); // the target asks it on open (EN-72, CH-14)
    return drawingId === null
      ? routeHref({ name: 'chat', projectId, query })
      : routeHref({ name: 'workspace', projectId, drawingId, role: 'engineer', query });
  }
  return null;
}
