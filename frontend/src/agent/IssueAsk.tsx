// Decision 0018: before it answers, the chat asks about an open issue the answer rests on. The issue is shown as
// the issue card shows it; the person picks a choice (a conflict's value settles it), types an answer, or skips.
import { useState } from 'react';
import type { DrawingView, FileStatus, Issue } from '../api';
import type { components } from '../api/schema';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SMALL } from '../documents/ui';
import { CHIP, FIELD, IssueCard, NameField, saveName, savedName } from '../issues/IssueCard';
import type { ChatTurn } from './agent';

export type IssueReply = components['schemas']['IssueReply'];

/** The ask turn's issue card with its choices. `closed`: answered already (a later turn exists), nothing to send. */
export function IssueAsk(props: {
  turn: ChatTurn;
  projectId: string;
  drawing: DrawingView | null | undefined;
  file: FileStatus | undefined;
  busy: boolean;
  closed: boolean;
  onAnswer: (message: string, reply: IssueReply) => void;
}) {
  const { turn, projectId, busy, closed, onAnswer } = props;
  const issue = turn.issue as Issue;
  const [name, setName] = useState(savedName);
  const [text, setText] = useState('');
  const by = name.trim();
  const off = busy || closed || by === '';
  const send = (message: string, more: Partial<IssueReply> = {}) => {
    saveName(by);
    onAnswer(message, { issue_id: issue.id, text: message, by, skip: false, ...more });
  };
  const inputId = `chat-answer-${issue.id}-${String(turn.turn)}`;
  return (
    <IssueCard
      projectId={projectId}
      issue={issue}
      drawing={props.drawing}
      file={props.file}
      onFile={() => undefined}
      pack={null}
      onIssue={() => undefined}
    >
      {!closed && (
        <form
          className="flex flex-col gap-2"
          aria-label="Answer the issue"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() && !off) send(text.trim());
          }}
        >
          <NameField name={name} onName={setName} />
          <div className="flex flex-wrap gap-2" role="group" aria-label="Choose one">
            {(turn.options ?? []).map((o) => (
              <Button
                key={o.label}
                type="button"
                variant="secondary"
                className={CHIP}
                title={o.message}
                disabled={o.skip ? busy : off}
                onClick={() => {
                  if (o.skip) {
                    onAnswer(o.message, {
                      issue_id: issue.id,
                      text: o.message,
                      by: by || 'someone',
                      skip: true,
                    });
                  } else send(o.message, o.value == null ? {} : { value: o.value });
                }}
              >
                {o.label}
              </Button>
            ))}
          </div>
          <label className={SMALL} htmlFor={inputId}>
            Your answer
          </label>
          <div className="flex gap-2 max-[520px]:flex-col">
            <Input
              className={FIELD}
              id={inputId}
              maxLength={500}
              autoComplete="off"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
              }}
            />
            <Button type="submit" size="pill" className="v-press" disabled={off || !text.trim()}>
              Use my answer
            </Button>
          </div>
        </form>
      )}
    </IssueCard>
  );
}
