import { useState } from 'react';
import {
  postRelevance,
  type DrawingView,
  type FileStatus,
  type Issue,
  type RelevanceRequest,
} from '../api';
import { callError, callLine } from '../ingest/triage';
import { answerOf, setAnswer, useIssueAnswers } from '../shell/issueAnswers';
import { SourceFigure } from '../viewer/SourceFigure';
import { isAnswerable, issueSource, pillOf } from './documents';

const NAME_KEY = 'countersign.surveyorName'; // the surveyor's key: one typed name for every call

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}

function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, the call still works
  }
}

/** The call on a file triage set aside (decision 0010), saved by the API. */
function RelevanceCall(props: {
  projectId: string;
  file: FileStatus;
  onFile: (file: FileStatus) => void;
}) {
  const { projectId, file, onFile } = props;
  const [name, setName] = useState(savedName);
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const said = file.triage ? callLine(file.triage) : null;

  const send = async (body: RelevanceRequest) => {
    setSending(true);
    setFailed(null);
    try {
      onFile(await postRelevance(projectId, file.id, body));
    } catch (e) {
      setFailed(callError(e));
    } finally {
      setSending(false);
    }
  };
  const call = (verdict: 'related' | 'unrelated') => {
    const by = name.trim();
    saveName(by);
    // undo defaults to false server-side; the body is relevance_request.json as is
    void send({ verdict, by } as RelevanceRequest);
  };
  const blocked = sending || name.trim() === '';

  return (
    <div className="doc-answer">
      {said ? (
        <div className="doc-foot">
          <span>{said}</span>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            disabled={sending}
            onClick={() => void send({ undo: true })}
          >
            Change
          </button>
        </div>
      ) : (
        <>
          <label className="doc-small doc-name">
            Your name
            <input
              type="text"
              maxLength={100}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </label>
          <div className="doc-chips">
            <button
              type="button"
              className="doc-chip v-press"
              disabled={blocked}
              onClick={() => {
                call('related');
              }}
            >
              It belongs to this project
            </button>
            <button
              type="button"
              className="doc-chip v-press"
              disabled={blocked}
              onClick={() => {
                call('unrelated');
              }}
            >
              It does not belong
            </button>
          </div>
        </>
      )}
      {failed && (
        <p role="alert" className="doc-error">
          {failed}
        </p>
      )}
    </div>
  );
}

/** A typed answer, kept in fe-shared's in-memory store until the API can save it (documents.md API ask 1). */
function TypedAnswer({ projectId, issue }: { projectId: string; issue: Issue }) {
  useIssueAnswers(projectId); // re-render when an answer changes
  const answer = answerOf(projectId, issue.id);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(answer ?? '');
  const inputId = `answer-${issue.id}`;

  if (answer !== null && !editing)
    return (
      <div className="doc-answer">
        <div className="doc-foot">
          <span>You answered: “{answer}”.</span>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            onClick={() => {
              setText(answer);
              setEditing(true);
            }}
          >
            Change
          </button>
        </div>
        <p className="doc-small">Kept in this tab only: the server does not save answers yet.</p>
      </div>
    );
  return (
    <form
      className="doc-answer"
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        setAnswer(projectId, issue.id, text.trim());
        setEditing(false);
      }}
    >
      <label className="doc-small" htmlFor={inputId}>
        Your answer
      </label>
      <div className="doc-own">
        <input
          id={inputId}
          maxLength={140}
          autoComplete="off"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
        />
        <button type="submit" className="v-btn v-press" disabled={!text.trim()}>
          Use my answer
        </button>
        {answer !== null && (
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            onClick={() => {
              setEditing(false);
            }}
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

/** One issue on the Documents tab (documents.md flow 4). */
export function IssueCard(props: {
  projectId: string;
  issue: Issue;
  n: number;
  drawing: DrawingView | null | undefined;
  file: FileStatus | undefined;
  onFile: (file: FileStatus) => void;
}) {
  const { projectId, issue, n, drawing, file, onFile } = props;
  const answered = useIssueAnswers(projectId).has(issue.id);
  const pill = pillOf(issue, answered);
  const source = issueSource(issue, projectId, drawing, file);
  return (
    <li className="v-card doc-issue">
      <div className="doc-top">
        <span className="doc-n" aria-hidden="true">
          {n}
        </span>
        <span className={`v-pill${pill.tone ? ` v-pill--${pill.tone}` : ''}`}>{pill.word}</span>
        <span className="doc-mono doc-small">{issue.file}</span>
        {issue.file_id && (
          <a className="doc-small doc-open" href={`#/p/${projectId}/f/${issue.file_id}`}>
            Open the file
          </a>
        )}
      </div>
      <p className="doc-why">{issue.why}</p>
      {source && <SourceFigure sources={[source]} label={`Source of issue ${String(n)}`} />}
      {isAnswerable(issue) &&
        (issue.kind === 'unrelated_file' ? (
          file?.triage && <RelevanceCall projectId={projectId} file={file} onFile={onFile} />
        ) : (
          <TypedAnswer projectId={projectId} issue={issue} />
        ))}
    </li>
  );
}
