import { ApiError, errorText } from '../api';

/** A screen's error state: the server's `detail` and `code`, never only a colour. */
export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const api = error instanceof ApiError ? error : null;
  const { detail, code } = errorText(error);
  const notFound = code === 'not-found';
  return (
    <section className="error-view" role="alert">
      <h2>{notFound ? 'Not found' : 'Something went wrong'}</h2>
      <p>{detail}</p>
      <p className="error-code">
        code: {code}
        {api && api.status !== 0 ? ` · HTTP ${String(api.status)}` : ''}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
      {notFound && <a href="#/">Go to the start</a>}
    </section>
  );
}
