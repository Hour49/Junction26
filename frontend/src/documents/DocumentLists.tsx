import { drawingLabel, type ProjectView, type Triage } from '../api';
import { formatSize, isFinished, kindLabel, plural, routeLabel } from '../ingest/ingest';
import { StateBadge } from '../ingest/ProjectScreen';
import { isNotPlan, looksLike, rowLine, verdictOf } from '../ingest/triage';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tip } from '@/components/ui/tip';
import { fileStateTip } from '../shell/tips';
import { shortReason } from './documents';
import { CARD, MONO, MUTED, SMALL } from './ui';

const REASON = 'text-[13px] text-muted-foreground [overflow-wrap:anywhere]';

/** A triaged non-plan's row line (file-triage.md flow 1): class, subject, verdict pill, whose call. */
function TriageLine({ triage }: { triage: Triage }) {
  return (
    <span className={REASON}>
      {rowLine(triage)}{' '}
      <Badge
        variant={triage.verdict === 'unsure' ? 'warn' : 'secondary'}
        className="px-[11px] py-[5px] text-xs text-text-2 data-[variant=warn]:text-warn"
      >
        {verdictOf(triage).pill}
      </Badge>
      {triage.overruled && ` · ${triage.overruled.by}’s call`}
    </span>
  );
}

/** Documents' drawings and files (documents.md flow 5-6), moved from the Ingest screen. */
export function DocumentLists({ project }: { project: ProjectView }) {
  const base = `#/p/${project.id}`;
  const live = !project.files.every(isFinished) || project.state === 'queued';
  return (
    <>
      <section aria-label="Drawings" className="flex flex-col gap-3">
        <h2 className="m-0 text-xl">Drawings</h2>
        {project.drawings.length === 0 ? (
          <p className={MUTED}>
            {live
              ? 'No drawing ready yet.'
              : 'No drawings: nothing in this upload could be read as a plan.'}
          </p>
        ) : (
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3 p-0">
            {project.drawings.map((d) => (
              <li key={d.drawing_id}>
                <Card className={`${CARD} h-full items-start gap-1.5 px-[18px] py-4`}>
                  <b>{drawingLabel(d)}</b>
                  <span className={`${SMALL} ${MONO}`}>{d.file}</span>
                  <span className={SMALL}>
                    {kindLabel(d.kind)}
                    {d.route && ` · ${routeLabel(d.route)}`}
                  </span>
                  <Button
                    asChild
                    variant="secondary"
                    size="pill"
                    className="v-press font-medium no-underline"
                  >
                    <a href={`${base}/d/${d.drawing_id}/engineer`}>Open</a>
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-label="Files" className="flex flex-col gap-3">
        <h2 className="m-0 text-xl">Files</h2>
        {typeof project.not_plans === 'number' && (
          <p className={SMALL}>
            {project.not_plans === 0
              ? 'No image set aside as not a floor plan'
              : `${plural(project.not_plans, 'not a floor plan', 'not floor plans')}: kept, not read`}
          </p>
        )}
        {project.files.length === 0 ? (
          <p className={MUTED}>{live ? 'Waiting for the files…' : 'This upload has no files.'}</p>
        ) : (
          <ul className={`${CARD} m-0 list-none p-0 [&>li+li]:border-t [&>li+li]:border-border`}>
            {project.files.map((f) => (
              <li key={f.id}>
                <a
                  className="v-press flex min-h-11 flex-wrap justify-between gap-x-4 gap-y-1.5 px-[18px] py-3 text-inherit no-underline"
                  href={`${base}/f/${f.id}`}
                >
                  <span className="flex min-w-0 flex-[1_1_260px] flex-col gap-1">
                    <span className={MONO}>{f.path}</span>
                    {f.triage?.read_as_plan ? (
                      <span className={REASON}>
                        Read as a floor plan on {f.triage.read_as_plan.by}’s call
                      </span>
                    ) : f.triage && isNotPlan(f) ? (
                      <TriageLine triage={f.triage} />
                    ) : f.triage && looksLike(f.triage) ? (
                      <span className={REASON}>{rowLine(f.triage)}</span>
                    ) : (
                      shortReason(f) && <span className={REASON}>{shortReason(f)}</span>
                    )}
                  </span>
                  <span className="flex flex-col items-end gap-1 max-[520px]:flex-row max-[520px]:flex-wrap max-[520px]:items-start">
                    <Tip text={fileStateTip(f.state)} wrap>
                      <StateBadge state={f.state} />
                    </Tip>
                    <span className={SMALL}>
                      {kindLabel(f.kind)} · {formatSize(f.size)}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
