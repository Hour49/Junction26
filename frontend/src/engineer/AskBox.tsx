import { useRef, useState } from 'react';
import { useInfo } from '../shell/info';

/** The question input; sends the trimmed question, nothing when empty, over the server's limit or while
 * an answer is pending. Before `/api/info` answers there is no limit here: the server's 422 shows. */
export function AskBox(props: {
  file: string;
  busy: boolean;
  asked: number;
  onAsk: (question: string) => void;
  /** The chat's paperclip (chat.md CH-17): shown only when passed; `attaching` disables it. */
  onAttach?: (photo: File) => void;
  attaching?: boolean;
}) {
  const { file, busy, asked, onAsk, onAttach, attaching = false } = props;
  const [text, setText] = useState('');
  const picker = useRef<HTMLInputElement>(null);
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
        {onAttach && (
          <>
            <input
              ref={picker}
              type="file"
              accept="image/png,image/jpeg"
              hidden
              data-testid="photo-input"
              onChange={(e) => {
                const photo = e.target.files?.[0];
                e.target.value = ''; // the same file can be picked again
                if (photo) onAttach(photo);
              }}
            />
            <button
              type="button"
              className="en-attach v-press"
              aria-label="Add a photo"
              title="Add a photo (png or jpeg)"
              disabled={attaching}
              onClick={() => picker.current?.click()}
            >
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                <path
                  d="M21 11.5l-8.6 8.6a5 5 0 01-7.1-7.1l8.6-8.6a3.5 3.5 0 015 5l-8.6 8.6a2 2 0 01-2.8-2.8l7.9-7.9"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </>
        )}
        <span className="en-meta">
          {asked} asked
          {limit !== undefined && ` · ${String(question.length)} / ${String(limit)}`}
        </span>
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
      {tooLong && (
        <p id="en-too-long" className="en-warn en-limit" role="alert">
          Questions are at most {limit} characters.
        </p>
      )}
    </form>
  );
}
