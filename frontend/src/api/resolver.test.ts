import { describe, expect, it } from 'vitest';
import { answerResolved, projectResolved, projectReviewResolved, resolving } from './fixtures';

// docs/specs/frontend/resolver.md: the fixtures every RS criterion is tested against.
describe('resolver fixtures', () => {
  it('RS-1 project_resolved counts the pick in conflicts_picked, not conflicts_open or issues_to_answer', () => {
    expect(projectResolved.conflicts_picked).toBe(1);
    expect(projectResolved.conflicts_open).toBe(0);
    expect(projectResolved.issues_to_answer).toBe(0);
  });

  it('RS-2 project_review_resolved: a picked conflict, still status conflict, needs nobody, value = the pick', () => {
    const c = projectReviewResolved.conflicts[0];
    expect(c?.conflict.status).toBe('conflict');
    expect(c?.needs_person).toBe(false);
    expect(c?.settled).toBeNull();
    expect(c?.resolved?.verdict).toBe('picked');
    expect(c?.value).toBe(c?.resolved?.value);
    expect(c?.resolved?.by.startsWith('carbon:')).toBe(true);
    expect(c?.resolved?.reason).toBeTruthy();
    expect(c?.resolved?.marks.length).toBeGreaterThan(0);
  });

  it('RS-3 resolving: cannot_tell leaves the conflict to a person, value null', () => {
    const c = resolving.review.conflicts[0];
    expect(c?.resolved?.verdict).toBe('cannot_tell');
    expect(c?.resolved?.value).toBeNull();
    expect(c?.needs_person).toBe(true);
    expect(resolving.notes).toEqual([]);
  });

  it('RS-4 answer_resolved: an uncertain answer (check set, level not high) with a pick beside it', () => {
    expect(answerResolved.resolved?.verdict).toBe('picked');
    expect(answerResolved.check).not.toBeNull();
    expect(answerResolved.level?.level).not.toBe('high');
  });
});
