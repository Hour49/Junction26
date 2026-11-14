import { expectTypeOf, it } from 'vitest';
import type * as T from './types';

it('SH-37 types.ts exports every name of the shared spec', () => {
  // tsc --noEmit fails here when a name is missing from types.ts or from the generated schema.
  expectTypeOf<
    [
      T.Info,
      T.Limits,
      T.Started,
      T.ProjectList,
      T.ProjectSummary,
      T.ProjectView,
      T.FileStatus,
      T.DrawingEntry,
      T.Rendering,
      T.FileTrace,
      T.StageTrace,
      T.ProjectReview,
      T.DrawingReview,
      T.ConflictEntry,
      T.DrawingView,
      T.PageView,
      T.Normalised,
      T.Reader,
      T.Suggestion,
      T.AskRequest,
      T.AnswerView,
      T.Refusal,
      T.MarkView,
      T.Row,
      T.Scope,
      T.RuleText,
      T.QuantityConflict,
      T.Settled,
      T.SignOff,
      T.Proof,
      T.Takeoff,
      T.Edit,
      T.SignOffRequest,
      T.Confidence,
    ]
  >().not.toBeNever();
});
