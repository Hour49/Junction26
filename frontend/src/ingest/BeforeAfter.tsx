import { useCallback, useState } from 'react';
import { getDrawing, pageUrl, previewUrl, type Normalised } from '../api';
import { Credit } from '../shell/Credit';
import { normalisedSteps } from './ingest';
import { usePoll } from './usePoll';

const once = () => false;

function Picture({ src, alt, missing }: { src: string; alt: string; missing: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) return <p className="ingest-missing">{missing}</p>;
  return (
    <img
      src={src}
      alt={alt}
      onError={() => {
        setBroken(true);
      }}
    />
  );
}

/** The upload next to the normalised page, with what normalisation did and the drawing's credit. */
export function BeforeAfter({
  projectId,
  fileId,
  path,
  drawingId,
  normalised,
}: {
  projectId: string;
  fileId: string;
  path: string;
  drawingId: string;
  normalised: Normalised;
}) {
  const load = useCallback((signal: AbortSignal) => getDrawing(drawingId, { signal }), [drawingId]);
  // One request; on failure the credit reads as null.
  const { data: drawing, error } = usePoll(load, once);
  const steps = normalisedSteps(normalised);
  return (
    <section aria-label="Before and after" className="ingest-before-after">
      <div className="ingest-pair">
        <figure>
          <Picture
            src={previewUrl(projectId, fileId)}
            alt={`${path} as uploaded`}
            missing="Preview not available"
          />
          <figcaption>As uploaded</figcaption>
        </figure>
        <figure>
          <Picture
            src={pageUrl(drawingId, 1)}
            alt={`${path} after normalisation`}
            missing="Page not available"
          />
          <figcaption>After normalisation</figcaption>
          {(drawing !== null || error !== null) && <Credit credit={drawing?.credit ?? null} />}
        </figure>
      </div>
      <ul>
        {steps.length === 0 ? (
          // No stage checks rotation, so the screen never claims the upload was upright (R1-3-5).
          <li>No turn, deskew or perspective correction applied (rotation is not checked)</li>
        ) : (
          steps.map((step) => <li key={step}>{step}</li>)
        )}
        <li>
          {normalised.width} × {normalised.height} px
        </li>
      </ul>
    </section>
  );
}
