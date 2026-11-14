import { errorText, readerName } from '../api';
import { useInfo } from './info';
import { OFFLINE_TEXT, READER_LABELS } from './strings';

/** Under the header on every route: whether the app runs offline, and which readers are active. */
/** `wide`: the account and workspace routes, whose header row is 1280 px (shared.md "Header"). */
export function InfoBar({ wide = false }: { wide?: boolean }) {
  const { info, error, reload } = useInfo();
  const width = wide ? ' info-bar--wide' : '';
  if (error !== null) {
    const { detail, code } = errorText(error);
    const text = `${detail} (${code})`;
    return (
      <div className={`info-bar info-bar-error${width}`} role="alert">
        <span>The server did not answer: {text}</span>
        <button type="button" onClick={reload}>
          Retry
        </button>
      </div>
    );
  }
  if (info === null) {
    return (
      <div className={`info-bar${width}`} role="status">
        Checking the server…
      </div>
    );
  }
  return (
    <div className={`info-bar${width}`}>
      {info.no_keys && <span className="offline">{OFFLINE_TEXT}</span>}
      <details className="what-runs">
        <summary>What runs</summary>
        <dl>
          {Object.entries(info.readers).map(([port, reader]) => (
            <div key={port}>
              <dt>{READER_LABELS[port] ?? port}</dt>
              <dd>{readerName(reader)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
