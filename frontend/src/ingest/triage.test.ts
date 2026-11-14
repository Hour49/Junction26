import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/errors';
import {
  CLASS_LABEL,
  VERDICT_LABEL,
  callError,
  callLine,
  canCall,
  isNotPlan,
  planChance,
  rowLine,
  verdictOf,
} from './triage';
import { must, triaged } from './testing';

const file = (i: number) => must(triaged.files[i]);
const [plan, south, site, street] = [file(0), file(1), file(2), file(3)];
const t = (f: typeof south) => must(f.triage);

describe('triage.ts (file-triage.md FT-5)', () => {
  it('maps every class and verdict to words', () => {
    expect(CLASS_LABEL).toEqual({
      floor_plan: 'a floor plan',
      other_drawing: 'another kind of drawing',
      not_drawing: 'not a drawing',
    });
    expect(verdictOf(t(south))).toBe(VERDICT_LABEL.related);
    expect(VERDICT_LABEL.related.pill).toBe('✓ Related');
    expect(VERDICT_LABEL.unrelated.pill).toBe('✕ Not related');
    expect(VERDICT_LABEL.unsure.pill).toBe('? Unsure');
    expect(verdictOf(t(street)).pill).toBe('✕ Not related'); // undescribed, judged by the class rule (#183)
    expect(verdictOf({ verdict: null }).pill).toBe('– Not judged');
  });

  it('tells a non-plan from a plan and from a file triage never saw', () => {
    expect(isNotPlan(plan)).toBe(false); // triage off for this file
    expect(isNotPlan(south)).toBe(true);
    expect(isNotPlan({ ...south, triage: { ...t(south), class: 'floor_plan' } })).toBe(false);
  });

  it('writes the row line, subject only when described (FT-2, FT-3)', () => {
    expect(rowLine(t(south))).toBe(
      'Not a floor plan: another kind of drawing · the south elevation of a two-storey house',
    );
    expect(rowLine(t(street))).toBe('Not a floor plan: not a drawing');
  });

  it('writes the call line, with the judge only when judged (FT-9)', () => {
    expect(callLine(t(site))).toBe(
      'Related to this project: Ana’s call, 2026-11-14 08:05 UTC. The judge said: Not related.',
    );
    expect(callLine({ ...t(site), relevance: null })).toBe(
      'Related to this project: Ana’s call, 2026-11-14 08:05 UTC.',
    );
    expect(callLine(t(south))).toBeNull();
  });

  it('allows a call on any non-plan, described or not (#183 lifts the 422)', () => {
    expect(canCall(plan)).toBe(false);
    expect(canCall(south)).toBe(true);
    expect(canCall(street)).toBe(true); // not described: allowed since #183
    expect(canCall({ ...south, triage: { ...t(south), class: 'floor_plan' } })).toBe(false);
  });

  it('shows the chance of a plan as a percent', () => {
    expect(planChance(0.03)).toBe('3 %');
    expect(planChance(0.996)).toBe('100 %');
  });

  it('words each error of the call (FT-13)', () => {
    expect(callError(new ApiError(409, 'not-allowed', 'x'))).toBe(
      'The project is still being read: a call can be made once it is done.',
    );
    expect(callError(new ApiError(422, 'no-description', 'x'))).toBe(
      'This file was not described, so there is nothing to judge or overrule.',
    );
    expect(callError(new ApiError(404, 'not-found', 'no such file'))).toBe(
      'This file is no longer in the project. (no such file, not-found)',
    );
    expect(callError(new ApiError(500, 'internal', 'boom'))).toBe('boom (internal)');
  });
});
