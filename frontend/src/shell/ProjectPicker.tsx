import { useEffect, useState } from 'react';
import { withPack } from './route';
import { errorText, formatTime, listProjects, type ProjectSummary } from '../api';

/** The header's project list (`GET /api/projects`); choosing one opens its ingest status. */
/** `pack`: the route's rule pack, kept when switching project (the country is a screen choice). */
export function ProjectPicker({
  projectId,
  pack,
}: {
  projectId: string | null;
  pack: string | null;
}) {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [askedFor, setAskedFor] = useState<string[]>([]);

  // A route naming a project the list lacks (one just uploaded): ask again, once per id.
  if (
    projects !== null &&
    projectId !== null &&
    !projects.some((p) => p.id === projectId) &&
    !askedFor.includes(projectId)
  ) {
    setAskedFor([...askedFor, projectId]);
    setAttempt(attempt + 1);
  }

  useEffect(() => {
    const abort = new AbortController();
    listProjects({ signal: abort.signal }).then(
      (found) => {
        setProjects(found.projects);
        setError(null);
      },
      (failed: unknown) => {
        if (!abort.signal.aborted) setError(failed);
      },
    );
    return () => {
      abort.abort();
    };
  }, [attempt]);

  if (error !== null) {
    const { detail, code } = errorText(error);
    return (
      <span className="project-picker project-picker-error">
        Projects: {detail} ({code}){' '}
        <button
          type="button"
          onClick={() => {
            setError(null);
            setAttempt(attempt + 1);
          }}
        >
          Retry
        </button>
      </span>
    );
  }
  if (projects === null || projects.length === 0) {
    return (
      <select className="project-picker" aria-label="Project" disabled value="">
        <option value="">{projects === null ? 'Loading projects…' : 'No projects yet'}</option>
      </select>
    );
  }
  const known = projectId !== null && projects.some((p) => p.id === projectId);
  return (
    <select
      className="project-picker"
      aria-label="Project"
      value={known ? projectId : ''}
      onChange={(event) => {
        if (event.target.value) window.location.hash = withPack(`#/p/${event.target.value}`, pack);
      }}
    >
      <option value="" disabled>
        Choose a project
      </option>
      {projects.map((p) => (
        <option key={p.id} value={p.id}>
          {`${p.name} · ${formatTime(p.created_at)}`}
        </option>
      ))}
    </select>
  );
}
