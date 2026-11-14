import { readerName, type DrawingView, type Suggestion } from '../api';

/** Reader ids are API values: shown by their names (`pdf` → "PDF vector reader"). */
export function howRead({ reader }: DrawingView): string {
  const by =
    reader.extractor === 'hello'
      ? ', not read (no reader for this route yet)'
      : ` by ${readerName(reader.extractor)}`;
  const second =
    reader.second_counter === 'none'
      ? 'no second count'
      : `second count: ${readerName(reader.second_counter)}`;
  return (
    `${reader.route ?? 'no'} route, read from ${reader.source ?? 'no file'}${by}; ${second}; ` +
    `questions: ${readerName(reader.question_parser)}`
  );
}

// Inline as well as in engineer.css, so the tests can see it: list-item keeps the disclosure marker.
export const MARKER = { display: 'list-item' } as const;

/** One button per question; a click asks it. */
export function Suggestions(props: {
  items: Suggestion[];
  busy: boolean;
  onAsk: (question: string) => void;
  label?: string;
}) {
  return (
    <div className="en-suggest" role="group" aria-label={props.label ?? 'Suggested questions'}>
      {props.items.map((s) => (
        <button
          key={s.quantity}
          type="button"
          className="en-chip v-press"
          title={s.label}
          disabled={props.busy}
          onClick={() => {
            props.onAsk(s.question);
          }}
        >
          {s.question}
        </button>
      ))}
    </div>
  );
}

/** The drawing's questions after the thread (outside every turn), or why there are none. */
export function SuggestionRow(props: {
  drawing: DrawingView;
  busy: boolean;
  onAsk: (question: string) => void;
}) {
  const { drawing, busy, onAsk } = props;
  if (drawing.suggestions.length > 0)
    return <Suggestions items={drawing.suggestions} busy={busy} onAsk={onAsk} />;
  return (
    <div className="en-suggest">
      <p className="en-small">No ready questions for this drawing.</p>
      {drawing.reader.extractor === 'hello' && (
        <p className="en-small">Its route has no reader yet, so questions will be refused.</p>
      )}
    </div>
  );
}
