import { describe, expect, it } from 'vitest';
import { issueRoute } from './issueLinks';

const pid = '5e0c1a2b3d4f';
const did = '44cc9f0d991eafe3';
const base = { drawing_id: did, quantity: 'area:room|name=1.01', question: null };

describe('issueRoute (CF-34)', () => {
  it('a conflict goes to its card on the conflicts screen, with the pack when given', () => {
    const href = issueRoute({ ...base, kind: 'conflict' }, pid);
    expect(href).toBe(`#/p/${pid}/conflicts?d=${did}&q=area%3Aroom%7Cname%3D1.01`);
    const q = new URLSearchParams(href?.split('?')[1]);
    expect(q.get('q')).toBe('area:room|name=1.01');
    expect(issueRoute({ ...base, kind: 'conflict' }, pid, 'fi')).toBe(
      `#/p/${pid}/conflicts?d=${did}&q=area%3Aroom%7Cname%3D1.01&pack=fi`,
    );
  });

  it('a conflict with no drawing or quantity falls back to the conflicts screen', () => {
    expect(issueRoute({ ...base, kind: 'conflict', drawing_id: null }, pid)).toBe(
      `#/p/${pid}/conflicts`,
    );
    expect(issueRoute({ ...base, kind: 'conflict', quantity: null }, pid, 'fi')).toBe(
      `#/p/${pid}/conflicts?pack=fi`,
    );
  });

  it('a refused answer asks again on its drawing, or in the project chat', () => {
    const question = 'How many doors are there?';
    expect(issueRoute({ ...base, kind: 'refused_answer', question }, pid)).toBe(
      `#/p/${pid}/d/${did}/engineer?ask=How+many+doors+are+there%3F`,
    );
    expect(
      issueRoute({ ...base, kind: 'refused_answer', question, drawing_id: null }, pid, 'fi'),
    ).toBe(`#/p/${pid}/chat?ask=How+many+doors+are+there%3F&pack=fi`);
  });

  it('every other kind is not mine: null', () => {
    for (const kind of ['set_aside', 'reading_flag', 'code_check_failed', 'double_check'])
      expect(issueRoute({ ...base, kind }, pid)).toBeNull();
  });
});
