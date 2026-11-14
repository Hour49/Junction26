import type { FileStatus } from '../api';
import { STAGE_LABEL, stageCounts } from './ingest';

/** Where the files are in the pipeline: per stage, the files whose latest stage it is. */
export function StageStrip({ files }: { files: readonly FileStatus[] }) {
  const { waiting, stages } = stageCounts(files);
  return (
    <ol className="ingest-stages" aria-label="Pipeline stages">
      <li>
        <span>Waiting</span> <b>{waiting}</b>
      </li>
      {stages.map((s) => (
        <li key={s.stage} className={s.working ? 'working' : undefined}>
          <span>{STAGE_LABEL[s.stage]}</span> <b>{s.count}</b>
          {s.working && (
            <span className="ingest-working">
              <span aria-hidden="true">◌</span> working
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
