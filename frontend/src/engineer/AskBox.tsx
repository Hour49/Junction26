import { useState } from 'react';
import { useInfo } from '../shell/info';

/** The question input; sends the trimmed question, nothing when empty, over the server's limit or while
 * an answer is pending. Before `/api/info` answers there is no limit here: the server's 422 shows. */
export function AskBox(props: { busy: boolean; asked: number; onAsk: (question: string) => void }) {
  const { busy, asked, onAsk } = props;
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
      <label htmlFor="en-question" className="en-sr">
        Question
      </label>
      <input
        id="en-question"
        value={text}
        placeholder="Ask a question about this drawing…"
        autoComplete="off"
        aria-describedby={tooLong ? 'en-too-long' : undefined}
        onChange={(e) => {
          setText(e.target.value);
        }}
      />
      <span className="en-meta">{asked} asked</span>
      <button type="submit" disabled={blocked}>
        Ask
      </button>
      {tooLong && (
        <p id="en-too-long" className="en-warn en-limit" role="alert">
          Questions are at most {limit} characters.
        </p>
      )}
    </form>
  );
}
