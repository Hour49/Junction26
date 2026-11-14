import { must } from '../ingest/testing';
import { describe, expect, it } from 'vitest';
import { project, projectList, projectReview } from '../api/fixtures';
import { questionsOf, toReviewOf } from './pending';

const summary = must(projectList.projects[0]);

describe('pending fields', () => {
  it('to_review: the real field when present', () => {
    expect(toReviewOf({ ...summary, to_review: 4 } as typeof summary, null)).toEqual({
      n: 4,
      pending: false,
    });
  });
  it('to_review: else the review sum, else unknown', () => {
    const sum = projectReview.drawings.reduce((n, d) => n + d.to_review, 0);
    expect(toReviewOf(summary, projectReview)).toEqual({ n: sum, pending: true });
    expect(toReviewOf(summary, null)).toBeNull();
  });

  it("questions: the log's count when present", () => {
    const entry = {
      question: 'How many doors?',
      answer: 2,
      unit: null,
      drawing_id: 'd',
      at: project.created_at,
      refused: false,
    };
    expect(questionsOf({ questions: [entry, entry] }, null)).toEqual({ n: 2, pending: false });
  });
  it('questions: else settled conflicts plus sign-offs, else unknown', () => {
    const review = {
      ...projectReview,
      drawings: projectReview.drawings.map((d, i) => ({ ...d, signed: i === 0 ? 2 : 0 })),
      conflicts: projectReview.conflicts.map((c) => ({
        ...c,
        settled: { value: 1, at: project.created_at },
      })),
    };
    expect(questionsOf(null, review)).toEqual({ n: 2 + review.conflicts.length, pending: true });
    expect(questionsOf(null, null)).toBeNull();
  });
});
