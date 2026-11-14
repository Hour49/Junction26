// Fields the API lacks (account.md "Not in the API"), mocked from real data until the backend adds them (#14).
// Each reader takes the real field first, so a mock disappears by itself once the field exists.
import type { ProjectReview, ProjectSummary } from '../api';

// PENDING(ProjectSummary.to_review): mock until the backend adds it (#14)
/** Open items of a list entry: the real field, else the selected workspace's review, else unknown. */
export function toReviewOf(
  summary: ProjectSummary,
  review: ProjectReview | null,
): { n: number; pending: boolean } | null {
  const real = (summary as { to_review?: number | null }).to_review;
  if (typeof real === 'number') return { n: real, pending: false };
  if (!review) return null;
  return { n: review.drawings.reduce((n, d) => n + d.to_review, 0), pending: true };
}

/** `GET /api/projects/{id}/questions` as Bogdan specified it (#14 c6874945888), newest first. */
export interface QuestionLog {
  questions: {
    question: string;
    answer: number | null;
    unit: string | null;
    drawing_id: string;
    at: string;
    refused: boolean;
  }[];
}

// PENDING(GET /api/projects/{id}/questions): mock until the backend adds it (#14)
// shortcut: the screen passes `log` null until src/api has getQuestions; then load it and pass it here.
/** Questions asked in the workspace: the log's count, else one per settled conflict and per sign-off. */
export function questionsOf(
  log: QuestionLog | null,
  review: ProjectReview | null,
): { n: number; pending: boolean } | null {
  if (log) return { n: log.questions.length, pending: false };
  if (!review) return null;
  const settled = review.conflicts.filter((c) => c.settled).length;
  const signed = review.drawings.reduce((n, d) => n + d.signed, 0);
  return { n: settled + signed, pending: true };
}
