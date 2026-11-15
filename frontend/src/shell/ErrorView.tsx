import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ApiError, errorText } from '../api';

/** The server is restarting or out of reach (a proxy's 502/503/504, or no answer at all): a passing state, said
 * plainly; the code stays small under it (QA board #430). */
export const SERVER_DOWN = 'The server is restarting or not reachable. Try again in a moment.';
export function serverDown(error: unknown): boolean {
  return error instanceof ApiError && [0, 502, 503, 504].includes(error.status);
}

/** A screen's error state: the server's `detail` and `code`, never only a colour. */
export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const api = error instanceof ApiError ? error : null;
  const { detail, code } = errorText(error);
  // Asking again for something that is not there finds nothing: a 404 leads back instead of retrying.
  const notFound = api?.status === 404;
  const down = serverDown(error);
  return (
    <Card
      className="grid justify-items-start gap-2 rounded-[var(--v-radius)] border-0 p-6 shadow-[var(--v-shadow)] [overflow-wrap:anywhere] max-[720px]:p-5"
      role="alert"
    >
      <h2 className="m-0 text-2xl leading-tight tracking-[-0.01em] text-danger">
        {notFound ? 'Not found' : down ? 'The server is not answering' : 'Something went wrong'}
      </h2>
      <p className="m-0">{down ? SERVER_DOWN : detail}</p>
      <p className="m-0 font-mono text-[13px] text-muted-foreground">
        code: {code}
        {api && api.status !== 0 ? ` · HTTP ${String(api.status)}` : ''}
      </p>
      {notFound ? (
        <a href="#/workspaces">Back to workspaces</a>
      ) : (
        onRetry && (
          <Button variant="secondary" size="pill" className="font-medium" onClick={onRetry}>
            Retry
          </Button>
        )
      )}
    </Card>
  );
}
