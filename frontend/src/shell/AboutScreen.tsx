import { useEffect, useState } from 'react';
import { getDrawing, getProject } from '../api';
import { ErrorView } from './ErrorView';
import { Loading } from './Loading';

interface Credits {
  name: string;
  rows: { id: string; file: string; credit: string | null }[];
}

/** Licence credits, moved off the screens (shared.md "Credits move to an About page"): CC BY needs them reachable.
 * shortcut: one getDrawing per drawing until API ask A2 puts `credit` on the project's drawings. */
export function AboutScreen({ projectId }: { projectId: string | null }) {
  const [state, setState] = useState<Credits | { error: unknown } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (projectId === null) return;
    const abort = new AbortController();
    const signal = abort.signal;
    getProject(projectId, { signal })
      .then(async (p) => ({
        name: p.name,
        rows: await Promise.all(
          p.drawings.map(async (d) => ({
            id: d.drawing_id,
            file: d.file,
            credit: (await getDrawing(d.drawing_id, { project: projectId, signal })).credit,
          })),
        ),
      }))
      .then(setState, (error: unknown) => {
        if (!signal.aborted) setState({ error });
      });
    return () => {
      abort.abort();
    };
  }, [projectId, attempt]);

  let credits;
  if (projectId === null) credits = <p>Open a project to see its drawings&apos; credits.</p>;
  else if (state === null) credits = <Loading label="Loading the credits…" />;
  else if ('error' in state)
    credits = (
      <ErrorView
        error={state.error}
        onRetry={() => {
          setState(null);
          setAttempt((n) => n + 1);
        }}
      />
    );
  else if (state.rows.length === 0) credits = <p>This project has no drawings.</p>;
  else
    credits = (
      <>
        <p className="about-project">{state.name}</p>
        <ul className="about-credits">
          {state.rows.map((r) => (
            <li key={r.id}>
              <span className="about-file">{r.file}</span>
              <span>
                {r.credit === null
                  ? 'No credit recorded for this file'
                  : r.credit.replace(/^credit:\s*/i, '')}
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
