import { LEVEL_WORD, type Level } from './agent';

const LEVEL_TONE: Record<Level['level'], string> = {
  high: ' v-pill--ok',
  medium: ' v-pill--warn',
  low: ' v-pill--danger',
};

/** "Confidence: High" with the level's text as its tooltip (ADR 0011, Bogdan 16:53). */
export function Confidence({ level }: { level: Level }) {
  return (
    <span className={`v-pill${LEVEL_TONE[level.level]}`} title={level.text ?? undefined}>
      Confidence: {LEVEL_WORD[level.level]}
      {level.text && <span className="en-sr">. {level.text}</span>}
    </span>
  );
}
