import { useEffect, useState } from 'react';
import { drawingLabel, getProject, type ProjectView } from '../api';
import { ErrorView } from './ErrorView';
import { Loading } from './Loading';

/** Licence credits, moved off the screens (shared.md "Credits move to an About page"): CC BY needs them reachable.
 * One request: the project's drawings carry their `credit` (#224, API ask A2). */
export function AboutScreen({ projectId }: { projectId: string | null }) {
  const [state, setState] = useState<ProjectView | { failed: unknown } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (projectId === null) return;
    const abort = new AbortController();
    const signal = abort.signal;
    getProject(projectId, { signal }).then(setState, (error: unknown) => {
      if (!signal.aborted) setState({ failed: error });
    });
    return () => {
      abort.abort();
    };
  }, [projectId, attempt]);

  let credits;
  if (projectId === null) credits = <p>Open a project to see its drawings&apos; credits.</p>;
  else if (state === null) credits = <Loading label="Loading the credits…" />;
  else if ('failed' in state)
    // not `error`: ProjectView has its own `error` field
    credits = (
      <ErrorView
        error={state.failed}
        onRetry={() => {
          setState(null);
          setAttempt((n) => n + 1);
        }}
      />
    );
  else if (state.drawings.length === 0) credits = <p>This project has no drawings.</p>;
  else
    credits = (
      <>
        <p className="about-project">{state.name}</p>
        <ul className="about-credits">
          {state.drawings.map((d) => (
            <li key={d.drawing_id}>
              <span className="about-file">{drawingLabel(d)}</span>
              <span className="v-caption">{d.file}</span>
              <span>
                {d.credit === null
                  ? 'No credit recorded for this file'
                  : d.credit.replace(/^credit:\s*/i, '')}
              </span>
            </li>
          ))}
        </ul>
      </>
    );

  return (
    <div className="v-page v-page--narrow about">
      <h1 className="v-title">About Vellum</h1>
      <p>
        Vellum reads a project&apos;s floor plans, models and scans, lists the quantities in them
        and shows where each number comes from.
      </p>
      <h2>Drawing credits</h2>
      {credits}
    </div>
  );
}
