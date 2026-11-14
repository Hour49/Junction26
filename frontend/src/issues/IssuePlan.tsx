import type { DrawingView, Issue, MarkView } from '../api';
import { PageViewer, type Tone } from '../viewer/PageViewer';

/** The selected issue's drawing with every located issue of it numbered, the selected one in focus. */
export function IssuePlan({
  issue,
  drawing,
  marks,
  tones,
  onSelect,
}: {
  issue: Issue | null;
  drawing: DrawingView | 'error' | undefined;
  marks: MarkView[];
  tones: Record<string, Tone>;
  onSelect: (id: string) => void;
}) {
  let body;
  if (!issue?.drawing_id) body = <p>This issue has no place on a drawing.</p>;
  else if (drawing === 'error') body = <p>Drawing not available</p>;
  else if (!drawing) body = <p className="v-caption">Loading the drawing…</p>;
  else
    body = (
      <PageViewer
        file={drawing.file}
        pages={drawing.pages}
        credit={drawing.credit ?? null}
        marks={marks}
        tones={tones}
        unit={null}
        selected={issue.id}
        focus={issue.page !== null ? { page: issue.page, box: issue.box } : null}
        onSelect={(id) => {
          if (id) onSelect(id);
        }}
      />
    );
  return (
    <section aria-label="Where" className="v-card is-plan">
      {body}
    </section>
  );
}
