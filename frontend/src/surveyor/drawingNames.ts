import { useEffect, useState } from 'react';
import { drawingLabel, getProject } from '../api';

/** The project's drawings by id → plain name (#224, drawingLabel); {} until loaded or when the GET fails. */
export function useDrawingNames(projectId: string): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>({});
  useEffect(() => {
    const abort = new AbortController();
    getProject(projectId, { signal: abort.signal }).then(
      (p) => {
        setNames(Object.fromEntries(p.drawings.map((d) => [d.drawing_id, drawingLabel(d)])));
      },
      () => undefined, // names are a nicety: each screen falls back to the file name
    );
    return () => {
      abort.abort();
    };
  }, [projectId]);
  return names;
}
