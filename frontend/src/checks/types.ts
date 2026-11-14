// The #139 check shapes live in src/api/types.ts (fe-shared, from the generated schema); this folder imports them
// from here only. Two names are narrowed for this folder, from those types (no shape is defined here).
import type { CheckMark, CheckResult, RuleCheck } from '../api/types';

export type {
  CheckMark,
  CheckResult,
  Clause,
  DrawingChecks,
  ProjectChecks,
  Rule,
  RuleCheck,
  RulePack,
} from '../api/types';
/** A single result's status: pass, fail or cannot tell (never `not_applicable`). */
export type CheckStatus = CheckResult['status'];
/** A rule's (drawing's, project's) status: a result status, or `not_applicable`. */
export type RuleStatus = RuleCheck['status'];
export type Box = CheckMark['box'];
