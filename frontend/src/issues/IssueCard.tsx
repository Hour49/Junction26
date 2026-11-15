import { useRef, useState, type ReactNode } from 'react';
import {
  answerIssue,
  errorText,
  formatTime,
  postRelevance,
  resolverModel,
  resolverName,
  type DrawingView,
  type FileStatus,
  type Highlight,
  type Issue,
  type IssueAnswerRequest,
  type RelevanceRequest,
} from '../api';
import { callError, callLine } from '../ingest/triage';
import { issueRoute } from '../conflicts/issueLinks';
import { SourceFigure } from '../viewer/SourceFigure';
import { ModelDialog } from '../model3d/ModelDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { isAnswerable, issueSource, pillOf } from '../documents/documents';
import { CARD, FOOT, MONO, SMALL } from '../documents/ui';

/** An answer chip (the demo's .qchip): a soft pill, 44 px tall, its text wraps. */
export const CHIP =
  'v-press h-auto min-h-11 rounded-full px-3.5 py-2 text-left text-sm font-normal whitespace-normal disabled:opacity-55';
export const FIELD = 'min-h-11 min-w-0 flex-1 rounded-xl bg-card px-3.5 text-base md:text-base';

const NAME_KEY = 'countersign.surveyorName'; // the surveyor's key: one typed name for every call

export function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}

export function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, the call still works
  }
}

export function NameField({ name, onName }: { name: string; onName: (name: string) => void }) {
  return (
    <label className={`${SMALL} grid max-w-80 gap-1`}>
      Your name
      <Input
        className={FIELD}
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
    <div className="flex flex-col gap-2">
      {said ? (
        <div className={FOOT}>
          <span>{said}</span>
          <Button
            type="button"
            variant="secondary"
            size="pill"
            className="v-press font-medium"
            disabled={sending}
            onClick={() => void send({ undo: true })}
          >
            Change
          </Button>
        </div>
      ) : (
        <>
          <NameField name={name} onName={setName} />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              className={CHIP}
              disabled={blocked}
              onClick={() => {
                call('related');
              }}
            >
              It belongs to this project
            </Button>
            <Button
              type="button"
              variant="secondary"
              className={CHIP}
              disabled={blocked}
              onClick={() => {
                call('unrelated');
              }}
            >
              It does not belong
            </Button>
          </div>
        </>
      )}
      {failed && (
        <p role="alert" className="text-danger">
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
  pack: string | null;
  onIssue: (issue: Issue) => void;
}) {
  const { projectId, issue, pack, onIssue } = props;
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
      const next = await answerIssue(projectId, issue.id, body, { pack: pack ?? undefined });
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
    <p role="alert" className="text-danger">
      {failed}
    </p>
  );

  if (answer && !editing)
    return (
      <div className="flex flex-col gap-2">
        <div className={FOOT}>
          <span>
            “{answer.text}” · {answer.by}’s answer, {formatTime(answer.at)}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="pill"
            className="v-press font-medium"
            disabled={sending}
            onClick={() => {
              setText(answer.text);
              setEditing(true);
            }}
          >
            Change
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="pill"
            className="v-press font-medium"
            disabled={sending}
            onClick={() => void send({ undo: true })}
          >
            Undo
          </Button>
        </div>
        {error}
      </div>
    );
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim() && !noName) answerWith(text);
      }}
    >
      <NameField name={name} onName={setName} />
      {(issue.suggestions ?? []).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {issue.suggestions?.map((s) => (
            <Button
              key={s}
              type="button"
              variant="secondary"
              className={CHIP}
              disabled={noName}
              onClick={() => {
                answerWith(s);
              }}
            >
              {s}
            </Button>
          ))}
        </div>
      )}
      <label className={SMALL} htmlFor={inputId}>
        Your answer
      </label>
      <div className="flex gap-2 max-[520px]:flex-col">
        <Input
          className={FIELD}
          id={inputId}
          maxLength={140}
          autoComplete="off"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
        />
        <Button type="submit" size="pill" className="v-press" disabled={noName || !text.trim()}>
          Use my answer
        </Button>
        {answer && (
          <Button
            type="button"
            variant="secondary"
            size="pill"
            className="v-press font-medium"
            onClick={() => {
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        )}
      </div>
      {error}
    </form>
  );
}

/** What a model said on a conflict (resolver.md RS-30/31): its pick or that it could not tell, why, and the way to
 * the conflict card, where a person settles it. */
function ModelSaid({ projectId, issue }: { projectId: string; issue: Issue }) {
  const r = issue.resolved;
  if (!r) return null;
  const name = resolverName(r.by);
  const href = issueRoute(issue, projectId);
  const picked = r.verdict === 'picked';
  return (
    <div className={FOOT}>
      <span>
        <strong title={resolverModel(r.by)}>
          {picked ? `Picked by ${name}` : `${name} could not tell`}
        </strong>{' '}
        <span>{r.reason}</span>
      </span>
      {href && (
        <Button
          asChild
          variant="secondary"
          size="pill"
          className="v-press font-medium no-underline"
        >
          <a href={href}>{picked ? 'You can change it' : 'Settle the conflict'}</a>
        </Button>
      )}
    </div>
  );
}

/** One issue as the Documents tab showed it (documents.md flow 4); the chat shows it when it asks about it
 * (decision 0018), with its own answer in `children` instead of the issue's answer form. */
export function IssueCard(props: {
  projectId: string;
  issue: Issue;
  /** Its number in a list; none in the chat. */
  n?: number;
  drawing: DrawingView | null | undefined;
  file: FileStatus | undefined;
  onFile: (file: FileStatus) => void;
  pack: string | null;
  onIssue: (issue: Issue) => void;
  /** The issue's 3D model (model-3d.md "More places" 2): its file and the checked element. */
  model?: { fileId: string; highlight: readonly Highlight[] } | null;
  /** Replaces the answer form (the chat's choices). */
  children?: ReactNode;
}) {
  const { projectId, issue, n, drawing, file, onFile, pack, onIssue, model } = props;
  const [open3d, setOpen3d] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const name = issue.drawing_name ?? issue.file;
  const pill = pillOf(issue);
  const source = issueSource(issue, projectId, drawing, file);
  return (
    <li>
      <Card className={`${CARD} gap-2.5 px-5 py-[18px] [&_p]:m-0`}>
        <div className="flex flex-wrap items-center gap-2">
          {n !== undefined && (
            <span className="min-w-[22px] font-bold tabular-nums" aria-hidden="true">
              {n}
            </span>
          )}
          <Badge
            variant={pill.tone || 'secondary'}
            className="px-[11px] py-[5px] text-xs data-[variant=secondary]:text-text-2"
          >
            {pill.word}
          </Badge>
          {issue.drawing_name ? (
            <span className={SMALL}>{issue.drawing_name}</span>
          ) : (
            <span className={`${MONO} ${SMALL}`}>{issue.file}</span>
          )}
          {issue.file_id && (
            <a
              className={`${SMALL} ml-auto inline-flex min-h-11 items-center`}
              href={`#/p/${projectId}/f/${issue.file_id}`}
            >
              Open the file
            </a>
          )}
          {model && (
            <Button
              ref={opener}
              type="button"
              variant="secondary"
              size="pill"
              className="v-press m3-open3d font-medium"
              aria-label={`View in 3D: ${name}`}
              onClick={() => {
                setOpen3d(true);
              }}
            >
              View in 3D
            </Button>
          )}
        </div>
        <p className="text-base [overflow-wrap:anywhere]">{issue.why}</p>
        {source && (
          <SourceFigure
            sources={[source]}
            label={n === undefined ? 'Source of the issue' : `Source of issue ${String(n)}`}
          />
        )}
        <ModelSaid projectId={projectId} issue={issue} />
        {props.children ??
          (isAnswerable(issue) &&
            (issue.kind === 'unrelated_file' ? (
              file?.triage && <RelevanceCall projectId={projectId} file={file} onFile={onFile} />
            ) : (
              <IssueAnswerForm projectId={projectId} issue={issue} pack={pack} onIssue={onIssue} />
            )))}
        {model && open3d && (
          <ModelDialog
            projectId={projectId}
            fileId={model.fileId}
            label={name}
            highlight={model.highlight}
            onClose={() => {
              setOpen3d(false);
              opener.current?.focus();
            }}
          />
        )}
      </Card>
    </li>
  );
}
