import { useCallback, useEffect, useRef, useState } from 'react';
import { addProjectFile, errorText, getProject, type FileStatus, type ProjectView } from '../api';

/** The photo added from the chat (CH-18..20): the status line, and whether it is still being read. */
interface Photo {
  line: string;
  reading: boolean;
}

const POLL_MS = 1000;
const MAX_POLLS = 180; // 3 minutes, then the paperclip is freed (Tudor #203 c6877912716)

/** What became of the added file, in the backend's own words (CH-18, CH-19): `ready` is read; `flagged` says
 * its reason, which may be that nothing was read ("not read: this setup has no reader ..."), so it never
 * promises answers; anything else was not read as a plan, with why. */
export function readLine(name: string, read: FileStatus | undefined): string {
  const why = (read?.reason ?? 'it is not in the project').replace(/\.$/, '');
  if (read?.state === 'ready') return `${name} is read: you can ask about it (${why}).`;
  if (read?.state === 'flagged') return `${name} is flagged: ${why}.`;
  return `${name} was not read as a plan: ${why}.`;
}

/** A photo added to the project from either chat (chat.md CH-17..21): `attach` posts it, then polls the project
 * until that file is read and hands the new project to `onProject` (its drawing becomes askable). `line` is the
 * status line to show, `attaching` disables the paperclip while it is read. */
export function usePhotoAdd(projectId: string, onProject: (project: ProjectView) => void) {
  const [photo, setPhoto] = useState<Photo | null>(null);
  const stopPhoto = useRef<AbortController | null>(null);
  useEffect(() => () => stopPhoto.current?.abort(), []);
  const onProjectNow = useRef(onProject);
  useEffect(() => {
    onProjectNow.current = onProject;
  }, [onProject]);

  const attach = useCallback(
    async (file: File) => {
      const abort = new AbortController();
      stopPhoto.current = abort;
      const { signal } = abort;
      const name = file.name;
      setPhoto({ line: `Reading ${name}…`, reading: true });
      let added: FileStatus;
      try {
        added = await addProjectFile(projectId, file, { signal });
      } catch (error) {
        if (!signal.aborted) {
          setPhoto({ line: `Could not add ${name}: ${errorText(error).detail}`, reading: false });
        }
        return;
      }
      for (let poll = 0; poll < MAX_POLLS; poll++) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        if (signal.aborted) return;
        let project: ProjectView;
        try {
          project = await getProject(projectId, { signal });
        } catch {
          continue; // the file is added either way: a failed check is retried on the next tick
        }
        const read = project.files.find((f) => f.id === added.id);
        if (read && (read.state === 'queued' || read.state === 'running')) continue;
        onProjectNow.current(project);
        setPhoto({ line: readLine(name, read), reading: false });
        return;
      }
      if (!signal.aborted) {
        setPhoto({
          line: `${name} is still being read. Reload later to ask about it.`,
          reading: false,
        });
      }
    },
    [projectId],
  );

  const line = photo && (
    <p className="en-small en-photo" role="status">
      {photo.line}
    </p>
  );
  return {
    attach: (file: File) => void attach(file),
    attaching: photo?.reading ?? false,
    line,
  };
}
