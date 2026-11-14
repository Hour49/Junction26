import { readerName, type DrawingView, type Suggestion } from '../api';

/** Reader ids are API values: shown by their names (`pdf` → "PDF vector reader"). */
function howRead({ reader }: DrawingView): string {
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
}) {
  return (
    <div className="en-suggest">
      {props.items.map((s) => (
        <button
          key={s.quantity}
          type="button"
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

/** The drawing's file, how it was read and the questions it is known to answer; after the first
 * answer the questions fold into a closed "Suggested questions". */
export function DrawingHeader(props: {
  drawing: DrawingView;
  busy: boolean;
  folded: boolean;
  onAsk: (question: string) => void;
}) {
  const { drawing, busy, folded, onAsk } = props;
  const items = drawing.suggestions;
  const buttons = <Suggestions items={items} busy={busy} onAsk={onAsk} />;
  return (
    <section className="en-header" aria-label="Drawing">
      <h1 className="en-file">{drawing.file}</h1>
      <p className="en-read">{howRead(drawing)}</p>
      {items.length === 0 ? (
        <>
          <p className="en-small">No ready questions for this drawing.</p>
          {drawing.reader.extractor === 'hello' && (
            <p className="en-small">Its route has no reader yet, so questions will be refused.</p>
          )}
        </>
      ) : folded ? (
        <details className="en-fold">
          <summary style={MARKER}>Suggested questions</summary>
          {buttons}
        </details>
      ) : (
        buttons
      )}
    </section>
  );
}
