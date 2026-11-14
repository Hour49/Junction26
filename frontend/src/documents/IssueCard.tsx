import { useState } from 'react';
import {
  answerIssue,
  errorText,
  formatTime,
  postRelevance,
  type DrawingView,
  type FileStatus,
  type Issue,
  type IssueAnswerRequest,
  type RelevanceRequest,
} from '../api';
import { callError, callLine } from '../ingest/triage';
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

function NameField({ name, onName }: { name: string; onName: (name: string) => void }) {
  return (
    <label className="doc-small doc-name">
      Your name
      <input
        type="text"
        maxLength={100}
        value={name}
        onChange={(e) => {
          onName(e.target.value);
        }}
      />
    </label>
  );
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
          <NameField name={name} onName={setName} />
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

/** An issue's answer, saved by the API (#223): suggestion chips or a typed answer, with the saved name. */
function IssueAnswerForm(props: {
  projectId: string;
  issue: Issue;
  onIssue: (issue: Issue) => void;
}) {
  const { projectId, issue, onIssue } = props;
  const answer = issue.answer ?? null;
  const [name, setName] = useState(savedName);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(answer?.text ?? '');
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const inputId = `answer-${issue.id}`;

  const send = async (body: IssueAnswerRequest) => {
    setSending(true);
    setFailed(null);
    try {
      const next = await answerIssue(projectId, issue.id, body);
      setEditing(false);
      setText(next.answer?.text ?? '');
      onIssue(next);
    } catch (e) {
      const { detail, code } = errorText(e);
      setFailed(`${detail} (${code})`);
    } finally {
      setSending(false);
    }
  };
  const answerWith = (value: string) => {
    const by = name.trim();
    saveName(by);
    void send({ text: value.trim(), by });
  };
  const noName = sending || name.trim() === '';
  const error = failed && (
    <p role="alert" className="doc-error">
      {failed}
    </p>
  );

  if (answer && !editing)
    return (
      <div className="doc-answer">
        <div className="doc-foot">
          <span>
            “{answer.text}” · {answer.by}’s answer, {formatTime(answer.at)}
          </span>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            disabled={sending}
            onClick={() => {
              setText(answer.text);
              setEditing(true);
            }}
          >
            Change
          </button>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            disabled={sending}
            onClick={() => void send({ undo: true })}
          >
            Undo
          </button>
        </div>
        {error}
      </div>
    );
  return (
    <form
      className="doc-answer"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim() && !noName) answerWith(text);
      }}
    >
      <NameField name={name} onName={setName} />
      {(issue.suggestions ?? []).length > 0 && (
        <div className="doc-chips">
          {issue.suggestions?.map((s) => (
            <button
              key={s}
              type="button"
              className="doc-chip v-press"
              disabled={noName}
              onClick={() => {
                answerWith(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}
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
        <button type="submit" className="v-btn v-press" disabled={noName || !text.trim()}>
          Use my answer
        </button>
        {answer && (
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
      {error}
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
  onIssue: (issue: Issue) => void;
}) {
  const { projectId, issue, n, drawing, file, onFile, onIssue } = props;
  const pill = pillOf(issue);
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
          <IssueAnswerForm projectId={projectId} issue={issue} onIssue={onIssue} />
        ))}
    </li>
  );
}
