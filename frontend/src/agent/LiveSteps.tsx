import type { Live, LiveStep } from './stream';
import './agent.css';

const MARK: Record<LiveStep['status'], string> = { planned: '', running: '', ok: '✓', error: '✗' };
const STATUS_WORD: Record<LiveStep['status'], string> = {
  planned: 'next',
  running: 'running',
  ok: 'done',
  error: 'failed',
};

/** What the agent is doing now, in the server's words. */
function nowText(live: Live | undefined): string | null {
  if (!live || (live.steps.length === 0 && !live.now)) return 'Working on it…';
  const now = live.now;
  if (!now) return null;
  if (now.kind === 'thinking') return 'Thinking…';
  if (now.kind === 'checking') return 'Checking the answer…';
  return now.reason ? `Checking again: ${now.reason}` : 'Checking again…';
}

/** The pending row while the agent works (chat-ux #2, contract C): each tool line as it is planned, runs and ends
 * with the server's summary, then what it is doing now. Without a stream: "Working on it…" as before. */
export function LiveSteps({ live }: { live?: Live }) {
  const steps = live?.steps ?? [];
  const now = nowText(live);
  return (
    <div className="ag-live" role="status">
      {steps.length > 0 && (
        <ol className="ag-live-steps" aria-label="What the agent is doing">
          {steps.map((s) => (
            <li key={s.n} className={`ag-live-step ag-live-step--${s.status}`}>
              <span className="ag-live-mark" aria-hidden="true">
                {MARK[s.status]}
              </span>
              <span className="ag-live-body">
                <span>
                  {s.label}
                  <span className="en-sr"> ({STATUS_WORD[s.status]})</span>
                </span>
                {s.summary && <span className="ag-live-sum">{s.summary}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
      {now && <p className="en-pending">{now}</p>}
    </div>
  );
}
