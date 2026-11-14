import { useState } from 'react';
import { useInfo } from '../shell/info';

/** The question input; sends the trimmed question, nothing when empty, over the server's limit or while
 * an answer is pending. Before `/api/info` answers there is no limit here: the server's 422 shows. */
export function AskBox(props: {
  file: string;
  busy: boolean;
  asked: number;
  onAsk: (question: string) => void;
}) {
  const { file, busy, asked, onAsk } = props;
  const [text, setText] = useState('');
  const limit = useInfo().info?.limits.question_chars;
  const question = text.trim();
  const tooLong = limit !== undefined && question.length > limit;
  const blocked = !question || busy || tooLong;
  return (
    <form
      className="en-ask"
      onSubmit={(e) => {
        e.preventDefault();
        if (blocked) return;
        onAsk(question);
        setText('');
      }}
    >
      <div className="en-askpill">
        <label htmlFor="en-question" className="en-sr">
          Question
        </label>
        <input
          id="en-question"
          value={text}
          placeholder={`Ask about ${file}`}
          autoComplete="off"
          aria-describedby={tooLong ? 'en-too-long' : undefined}
          onChange={(e) => {
            setText(e.target.value);
          }}
        />
        <button type="submit" className="en-send v-press" aria-label="Ask" disabled={blocked}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              d="M12 19V5M5 12l7-7 7 7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
      <p className="en-meta">
        {asked} asked
        {limit !== undefined && ` · ${String(question.length)} / ${String(limit)}`}
      </p>
      {tooLong && (
        <p id="en-too-long" className="en-warn en-limit" role="alert">
          Questions are at most {limit} characters.
        </p>
      )}
    </form>
  );
}
