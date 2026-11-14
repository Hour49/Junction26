import { useCallback, useEffect, useRef, useState } from 'react';
import { getDrawing, getTakeoff, type DrawingEntry, type DrawingView, type Takeoff } from '../api';
import { isFinished } from '../ingest/ingest';

type Kind = 'takeoff' | 'drawing';

export interface DrawingData {
  takeoffs: ReadonlyMap<string, Takeoff>;
  views: ReadonlyMap<string, DrawingView>;
  /** `<kind>:<drawing id>` of each failed request. */
  failed: ReadonlySet<string>;
  retry: (kind: Kind, drawingId: string) => void;
}

/**
 * Each finished drawing's takeoff and DrawingView, requested once, and only after `need` first asks for that
 * kind (the steps that show them). Unmount aborts what is in flight and forgets it (StrictMode remounts).
 */
export function useDrawingData(
  drawings: readonly DrawingEntry[],
  needTakeoff: boolean,
  needDrawing: boolean,
): DrawingData {
  const [takeoffs, setTakeoffs] = useState<ReadonlyMap<string, Takeoff>>(new Map());
  const [views, setViews] = useState<ReadonlyMap<string, DrawingView>>(new Map());
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const asked = useRef(new Set<string>());
  const controllers = useRef(new Set<AbortController>());
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const need = { takeoff: needTakeoff, drawing: needDrawing };
    for (const d of drawings) {
      if (!isFinished(d)) continue;
      for (const kind of ['takeoff', 'drawing'] as const) {
        const id = `${kind}:${d.drawing_id}`;
        if (!need[kind] || asked.current.has(id)) continue;
        asked.current.add(id);
        const controller = new AbortController();
        controllers.current.add(controller);
        const done = () => controllers.current.delete(controller);
        const fail = (error: unknown) => {
          if (controller.signal.aborted) return;
          console.warn(`${kind} not loaded`, d.drawing_id, error);
          setFailed((s) => new Set(s).add(id));
        };
        const opts = { signal: controller.signal };
        if (kind === 'takeoff')
          getTakeoff(d.drawing_id, opts)
            .then((t) => {
              setTakeoffs((m) => new Map(m).set(d.drawing_id, t));
            }, fail)
            .finally(done);
        else
          getDrawing(d.drawing_id, opts)
            .then((v) => {
              setViews((m) => new Map(m).set(d.drawing_id, v));
            }, fail)
            .finally(done);
      }
    }
  }, [drawings, needTakeoff, needDrawing, tick]);

  useEffect(() => {
    const askedNow = asked.current;
    const all = controllers.current;
    return () => {
      for (const c of all) c.abort();
      all.clear();
      askedNow.clear();
    };
  }, []);

  const retry = useCallback((kind: Kind, drawingId: string) => {
    const id = `${kind}:${drawingId}`;
    asked.current.delete(id);
    setFailed((s) => new Set([...s].filter((x) => x !== id)));
    setTick((t) => t + 1);
  }, []);

  return { takeoffs, views, failed, retry };
}
