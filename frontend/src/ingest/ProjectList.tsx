import { useCallback } from 'react';
import { formatTime, listProjects } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { usePoll } from './usePoll';

const once = () => false;

/** Earlier projects, newest first, as the API gives them. */
export function ProjectList() {
  const load = useCallback((signal: AbortSignal) => listProjects({ signal }), []);
  const { data, error, retry } = usePoll(load, once);

  let body;
  if (error !== null) body = <ErrorView error={error} onRetry={retry} />;
  else if (data === null) body = <Loading label="Loading projects…" />;
  else if (data.projects.length === 0)
    body = <p>No projects yet. Upload a file or try the sample.</p>;
  else
    body = (
      <ul className="ingest-projects">
        {data.projects.map((p) => (
          <li key={p.id}>
            <a href={`#/p/${p.id}`}>
              <b>{p.name}</b>
              <span>{p.state}</span>
              <time dateTime={p.created_at}>{formatTime(p.created_at)}</time>
              <span>
                {p.files} files · {p.drawings} drawings
              </span>
            </a>
          </li>
        ))}
      </ul>
    );

  return (
    <section aria-label="Projects">
      <h2>Projects</h2>
      {body}
    </section>
  );
}
