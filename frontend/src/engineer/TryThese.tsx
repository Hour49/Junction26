import './engineer.css';

/** "Try these": the curated prompts of the sample this project was made from (Bogdan 2026-11-15), in the given
 * order, above the drawings' own suggestions; nothing when there are none. `onAsk`: the chat asks it itself;
 * `chatHref`: elsewhere each chip opens the project chat with it. */
export function TryThese(props: {
  prompts: readonly string[] | undefined;
  busy?: boolean;
  onAsk?: (prompt: string) => void;
  chatHref?: (prompt: string) => string;
}) {
  const { prompts = [], busy = false, onAsk, chatHref } = props;
  if (prompts.length === 0) return null;
  return (
    <section className="en-try" aria-label="Try these">
      <h2 className="en-try-title">Try these</h2>
      <div className="en-suggest">
        {prompts.map((prompt) =>
          onAsk ? (
            <button
              key={prompt}
              type="button"
              className="en-chip en-chip--try v-press"
              disabled={busy}
              onClick={() => {
                onAsk(prompt);
              }}
            >
              {prompt}
            </button>
          ) : (
            <a key={prompt} className="en-chip en-chip--try v-press" href={chatHref?.(prompt)}>
              {prompt}
            </a>
          ),
        )}
      </div>
    </section>
  );
}

/** The project chat, opened with `prompt` asked (chat.md "Opening with a question"). */
export const chatWith = (projectId: string) => (prompt: string) =>
  `#/p/${projectId}/chat?${new URLSearchParams({ ask: prompt }).toString()}`;
