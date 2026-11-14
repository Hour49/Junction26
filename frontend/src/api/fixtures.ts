// The backend's contract fixtures (backend/tests/fixtures/api_v1), typed for tests. A JSON import widens
// string unions, hence the casts; the backend's fixture test keeps the files true to the models.
import answerJson from '@fixtures/answer.json';
import answerAreaJson from '@fixtures/answer_area.json';
import answerConfidenceJson from '@fixtures/answer_confidence.json';
import answerModelJson from '@fixtures/answer_model.json';
import answerRefusedJson from '@fixtures/answer_refused.json';
import askRequestJson from '@fixtures/ask_request.json';
import drawingJson from '@fixtures/drawing.json';
import errorJson from '@fixtures/error.json';
import infoJson from '@fixtures/info.json';
import projectJson from '@fixtures/project.json';
import projectListJson from '@fixtures/project_list.json';
import projectReviewJson from '@fixtures/project_review.json';
import projectStartedJson from '@fixtures/project_started.json';
import reviewRequestsJson from '@fixtures/review_requests.json';
import signoffRequestJson from '@fixtures/signoff_request.json';
import takeoffJson from '@fixtures/takeoff.json';
import traceJson from '@fixtures/trace.json';
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
  ProjectView,
  SignOffRequest,
  Started,
  Takeoff,
} from './types';

export const info = infoJson as unknown as Info;
export const projectStarted = projectStartedJson as unknown as Started;
export const projectList = projectListJson as unknown as ProjectList;
export const project = projectJson as unknown as ProjectView;
export const trace = traceJson as unknown as FileTrace;
export const projectReview = projectReviewJson as unknown as ProjectReview;
export const drawing = drawingJson as unknown as DrawingView;
export const askRequest: AskRequest = askRequestJson;
export const answer = answerJson as unknown as AnswerView;
export const answerArea = answerAreaJson as unknown as AnswerView;
export const answerConfidence = answerConfidenceJson as unknown as AnswerView;
export const answerModel = answerModelJson as unknown as AnswerView;
export const answerRefused = answerRefusedJson as unknown as AnswerView;
export const takeoff = takeoffJson as unknown as Takeoff;
export const reviewRequests = reviewRequestsJson as unknown as Edit[];
export const signoffRequest = signoffRequestJson as unknown as SignOffRequest;
export const error: ErrorBody = errorJson;
