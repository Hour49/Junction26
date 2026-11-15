import { drawingLabel, type ProjectView } from '../api';
import { isFinished, kindLabel, routeLabel } from '../ingest/ingest';
import { isNotPlan, rowLine } from '../ingest/triage';
import { StateBadge } from '../ingest/ProjectScreen';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tip } from '@/components/ui/tip';
import { fileStateTip } from '../shell/tips';
import { setAsideFiles, shortReason } from './documents';
import { CARD, MONO, MUTED, SMALL } from './ui';

/** Documents' drawings (documents.md flow 5): each card carries its file's state and, on the right, Open. */
export function DocumentLists({ project }: { project: ProjectView }) {
  const base = `#/p/${project.id}`;
  const setAside = setAsideFiles(project);
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
            {project.drawings.map((d) => {
              const file = project.files.find((f) => f.path === d.file);
              return (
                <li key={d.drawing_id}>
                  <Card
                    className={`${CARD} h-full flex-row items-center justify-between gap-3 px-[18px] py-4`}
                  >
                    <div className="flex min-w-0 flex-col items-start gap-1.5">
                      <b>{drawingLabel(d)}</b>
                      <span className={`${SMALL} ${MONO} [overflow-wrap:anywhere]`}>{d.file}</span>
                      <span className={SMALL}>
                        {kindLabel(d.kind)}
                        {d.route && ` · ${routeLabel(d.route)}`}
                      </span>
                      {file && (
                        <a
                          className="v-press text-inherit no-underline"
                          href={`${base}/f/${file.id}`}
                          aria-label={`How ${d.file} was read`}
                        >
                          <Tip text={fileStateTip(file.state)} wrap>
                            <StateBadge state={file.state} />
                          </Tip>
                        </a>
                      )}
                    </div>
                    <Button
                      asChild
                      variant="secondary"
                      size="pill"
                      className="v-press shrink-0 font-medium no-underline"
                    >
                      <a href={`${base}/d/${d.drawing_id}/engineer`}>Open</a>
                    </Button>
                  </Card>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      {setAside.length > 0 && (
        <section aria-label="Set aside" className="flex flex-col gap-3">
          <h2 className="m-0 text-xl">Set aside</h2>
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-2 p-0">
            {setAside.map((f) => (
              <li key={f.id}>
                <Card className={`${CARD} h-full items-start gap-1 px-3.5 py-2.5`}>
                  <span className={`${SMALL} ${MONO} [overflow-wrap:anywhere]`}>{f.path}</span>
                  <span className={`${SMALL} [overflow-wrap:anywhere]`}>
                    {f.triage && isNotPlan(f) ? rowLine(f.triage) : shortReason(f)}
                  </span>
                  <a
                    className="v-press text-inherit no-underline"
                    href={`${base}/f/${f.id}`}
                    aria-label={`How ${f.path} was read`}
                  >
                    <Tip text={fileStateTip(f.state)} wrap>
                      <StateBadge state={f.state} />
                    </Tip>
                  </a>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
