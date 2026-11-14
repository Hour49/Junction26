// The backend's contract fixtures (backend/tests/fixtures/api_v1), typed for tests. A JSON import widens
// string unions, hence the casts; the backend's fixture test keeps the files true to the models.
import answerJson from '@fixtures/answer.json';
import answerAreaJson from '@fixtures/answer_area.json';
import answerConfidenceJson from '@fixtures/answer_confidence.json';
import answerConflictJson from '@fixtures/answer_conflict.json';
import answerModelJson from '@fixtures/answer_model.json';
import answerRefusedJson from '@fixtures/answer_refused.json';
import answerScheduleJson from '@fixtures/answer_schedule.json';
import answerSignedJson from '@fixtures/answer_signed.json';
import askRequestJson from '@fixtures/ask_request.json';
import drawingJson from '@fixtures/drawing.json';
import errorJson from '@fixtures/error.json';
import errorNotAllowedJson from '@fixtures/error_not_allowed.json';
import infoJson from '@fixtures/info.json';
import projectJson from '@fixtures/project.json';
import projectFailedJson from '@fixtures/project_failed.json';
import projectListJson from '@fixtures/project_list.json';
import projectReviewJson from '@fixtures/project_review.json';
import projectRunningJson from '@fixtures/project_running.json';
import projectStartedJson from '@fixtures/project_started.json';
import reviewRequestsJson from '@fixtures/review_requests.json';
import signoffRequestJson from '@fixtures/signoff_request.json';
import takeoffJson from '@fixtures/takeoff.json';
import takeoffEditedJson from '@fixtures/takeoff_edited.json';
import projectTraceJson from '@fixtures/project_trace.json';
import traceJson from '@fixtures/trace.json';
import traceSetAsideJson from '@fixtures/trace_set_aside.json';
import type { ErrorBody } from './errors';
import type {
  AnswerView,
  AskRequest,
  DrawingView,
  Edit,
  FileTrace,
  Info,
  ProjectList,
  ProjectReview,
  ProjectTrace,
  ProjectView,
  SignOffRequest,
  Started,
  Takeoff,
} from './types';

export const info = infoJson as unknown as Info;
export const projectStarted = projectStartedJson as unknown as Started;
export const projectList = projectListJson as unknown as ProjectList;
export const project = projectJson as unknown as ProjectView;
export const projectRunning = projectRunningJson as unknown as ProjectView;
export const projectFailed = projectFailedJson as unknown as ProjectView;
export const trace = traceJson as unknown as FileTrace;
export const traceSetAside = traceSetAsideJson as unknown as FileTrace;
export const projectTrace = projectTraceJson as unknown as ProjectTrace;
export const projectReview = projectReviewJson as unknown as ProjectReview;
export const drawing = drawingJson as unknown as DrawingView;
export const askRequest: AskRequest = askRequestJson;
export const answer = answerJson as unknown as AnswerView;
export const answerArea = answerAreaJson as unknown as AnswerView;
export const answerConfidence = answerConfidenceJson as unknown as AnswerView;
export const answerModel = answerModelJson as unknown as AnswerView;
export const answerConflict = answerConflictJson as unknown as AnswerView;
export const answerSigned = answerSignedJson as unknown as AnswerView;
export const answerSchedule = answerScheduleJson as unknown as AnswerView;
export const answerRefused = answerRefusedJson as unknown as AnswerView;
export const takeoff = takeoffJson as unknown as Takeoff;
export const takeoffEdited = takeoffEditedJson as unknown as Takeoff;
export const reviewRequests = reviewRequestsJson as unknown as Edit[];
export const signoffRequest = signoffRequestJson as unknown as SignOffRequest;
export const error: ErrorBody = errorJson;
export const errorNotAllowed: ErrorBody = errorNotAllowedJson;
