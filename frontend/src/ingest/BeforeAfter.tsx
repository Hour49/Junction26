import { useState } from 'react';
import { pageUrl, previewUrl, type Normalised } from '../api';
import { normalisedSteps } from './ingest';
import { PANEL } from './ui';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

function Picture({ src, alt, missing }: { src: string; alt: string; missing: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) return <p>{missing}</p>;
  return (
    <img
      className="block h-auto max-w-full rounded-xl border border-border"
      src={src}
      alt={alt}
      onError={() => {
        setBroken(true);
      }}
    />
  );
}

/** The upload next to the normalised page, with what normalisation did (no credit on screens: IN-80). */
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
  const steps = normalisedSteps(normalised);
  return (
    <Card role="region" aria-label="Before and after" className={cn(PANEL, 'block')}>
      <div className="grid grid-cols-2 gap-4 max-[720px]:grid-cols-1 [&_figcaption]:mt-1.5 [&_figcaption]:text-[13px] [&_figcaption]:text-muted-foreground [&_figure]:m-0">
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
    </Card>
  );
}
