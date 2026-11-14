import type { components } from './schema';

type Schemas = components['schemas'];

export type Info = Schemas['Info'];
export type Limits = Schemas['Limits'];
export type Started = Schemas['Started'];
export type ProjectList = Schemas['ProjectList'];
export type ProjectSummary = Schemas['ProjectSummary'];
export type ProjectView = Schemas['ProjectView'];
export type FileStatus = Schemas['FileStatus'];
export type DrawingEntry = Schemas['DrawingEntry'];
export type Rendering = Schemas['Rendering'];
export type FileTrace = Schemas['FileTrace'];
export type ProjectTrace = Schemas['ProjectTrace'];
export type ProjectQuestions = Schemas['ProjectQuestions'];
export type AskedQuestion = Schemas['AskedQuestion'];
export type StageTrace = Schemas['StageTrace'];
export type ProjectReview = Schemas['ProjectReview'];
export type DrawingReview = Schemas['DrawingReview'];
export type ConflictEntry = Schemas['ConflictEntry'];
export type DrawingView = Schemas['DrawingView'];
export type PageView = Schemas['PageView'];
export type Normalised = Schemas['Normalised'];
export type Reader = Schemas['Reader'];
export type Suggestion = Schemas['Suggestion'];
export type AskRequest = Schemas['AskRequest'];
export type AnswerView = Schemas['AnswerView'];
export type ProjectAnswer = Schemas['ProjectAnswer'];
export type Refusal = Schemas['Refusal'];
export type MarkView = Schemas['MarkView'];
export type Row = Schemas['Row'];
export type Scope = Schemas['Scope'];
export type RuleText = Schemas['RuleText'];
export type QuantityConflict = Schemas['QuantityConflict'];
export type Settled = Schemas['Settled'];
export type SignOff = Schemas['SignOff'];
export type Proof = Schemas['Proof'];
export type Takeoff = Schemas['Takeoff'];
export type Edit = Schemas['Edit'];
export type SignOffRequest = Schemas['SignOffRequest'];

/** The answer confidence (board #14): `score` is a raw model choice score, never a probability. */
export type Signal = Schemas['Signal'];
