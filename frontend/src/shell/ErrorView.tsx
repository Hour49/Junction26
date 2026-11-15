import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ApiError, errorText } from '../api';

/** A screen's error state: the server's `detail` sentence, never only a colour; no raw code (QA R2-C5). */
export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const api = error instanceof ApiError ? error : null;
  const { detail } = errorText(error);
  // Asking again for something that is not there finds nothing: a 404 leads back instead of retrying.
  const notFound = api?.status === 404;
  return (
    <Card
      className="grid justify-items-start gap-2 rounded-[var(--v-radius)] border-0 p-6 shadow-[var(--v-shadow)] [overflow-wrap:anywhere] max-[720px]:p-5"
      role="alert"
    >
      <h2 className="m-0 text-2xl leading-tight tracking-[-0.01em] text-danger">
        {notFound ? 'Not found' : 'Something went wrong'}
      </h2>
      <p className="m-0">{detail}</p>
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
