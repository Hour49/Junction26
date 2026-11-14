import { useState } from 'react';
import {
  postRelevance,
  previewUrl,
  readAsPlan,
  type FileStatus,
  type RelevanceRequest,
} from '../api';
import {
  CLASS_LABEL,
  callError,
  callLine,
  canCall,
  canReadAsPlan,
  classLine,
  looksLike,
  planChance,
  readError,
  readLine,
} from './triage';
import { MUTED, PANEL, SUMMARY } from './ui';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

const CARD = cn(PANEL, 'grid gap-2');
const H3 = 'mt-3 mb-0 text-base';
/** The call row: wraps on a desktop, one column on a phone. */
const ROW =
  'mt-2 flex flex-wrap items-end gap-x-3 gap-y-2 max-[720px]:flex-col max-[720px]:flex-nowrap max-[720px]:items-stretch [&>p]:basis-full';

const NAME_KEY = 'countersign.surveyorName'; // the surveyor's key: one typed name for every call

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}

function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, the call still works
  }
}

/** The trace's triage card (file-triage.md flow 3-6); `onFile` takes a POST's answer. */
export function TriageCard(props: {
  projectId: string;
  file: FileStatus;
  onFile: (file: FileStatus) => void;
}) {
  const { projectId, file, onFile } = props;
  const [name, setName] = useState(savedName);
  const [sending, setSending] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [noPreview, setNoPreview] = useState(false);
  const t = file.triage;
  if (!t || (t.class === 'floor_plan' && !looksLike(t))) return null;
  if (t.class === 'floor_plan')
    return (
      <Card role="region" aria-label="Is it a floor plan?" className={CARD}>
        <h2 className="v-h3">{classLine(t)}</h2>
        <p className={MUTED}>
          Chance of a floor plan {planChance(t.p_plan)} ({t.method})
        </p>
      </Card>
    );

  const send = async (
    busy: string,
    request: () => Promise<FileStatus>,
    wording: (e: unknown) => string,
  ) => {
    setSending(busy);
    setFailed(null);
    try {
      onFile(await request());
    } catch (e) {
      setFailed(wording(e));
    } finally {
      setSending(null);
    }
  };
  const relevance = (body: RelevanceRequest) =>
    send('Saving your call…', () => postRelevance(projectId, file.id, body), callError);
  const by = () => {
    const typed = name.trim();
    saveName(typed);
    return typed;
  };
  const call = (verdict: 'related' | 'unrelated') => {
    // undo defaults to false server-side; the body is relevance_request.json as is
    void relevance({ verdict, by: by() } as RelevanceRequest);
  };
  const read = () => {
    if (!window.confirm(`Read ${file.path} as a floor plan? This can't be undone.`)) return;
    void send('Asking for the reading…', () => readAsPlan(projectId, file.id, by()), readError);
  };
  const d = t.description;
  const said = callLine(t);
  const offerCall = !said && canCall(file);
  const offerRead = canReadAsPlan(file);
  const blocked = sending !== null || name.trim() === '';

  return (
    <Card role="region" aria-label="Is it a floor plan?" className={CARD}>
      {t.read_as_plan ? (
        <>
          <h2 className="v-h3">Read as a floor plan on {t.read_as_plan.by}’s call</h2>
          <p className={MUTED}>
            Triage said: {CLASS_LABEL[t.class]} ({planChance(t.p_plan)} chance of a floor plan)
          </p>
        </>
      ) : (
        <>
          <h2 className="v-h3">{classLine(t)}</h2>
          <p className={MUTED}>
            Chance of a floor plan {planChance(t.p_plan)} ({t.method})
          </p>
        </>
      )}
      {noPreview ? (
        <p>Preview not available</p>
      ) : (
        <img
          className="block h-auto max-w-[min(100%,400px)] rounded-xl border border-border"
          // the API's widths are 400/1600/3200: 400 at 1x, 1600 for dense screens (never 1600 at 1x)
          src={previewUrl(projectId, file.id, 400)}
          srcSet={`${previewUrl(projectId, file.id, 400)} 400w, ${previewUrl(projectId, file.id, 1600)} 1600w`}
          sizes="(max-width: 400px) 100vw, 400px"
          alt={`${file.path} as uploaded`}
          onError={() => {
            setNoPreview(true);
          }}
        />
      )}
      <h3 className={H3}>What is on it</h3>
      {d ? (
        <>
          <p>{d.text}</p>
          <p>Subject: {d.subject}</p>
          {d.text_seen.length > 0 && (
            <details>
              <summary className={SUMMARY}>Text printed on it ({d.text_seen.length})</summary>
              <ul>
                {d.text_seen.map((s, i) => (
                  <li key={String(i)}>{s}</li>
                ))}
              </ul>
              {d.language && <p>language: {d.language}</p>}
            </details>
          )}
        </>
      ) : (
        <p>{t.note}</p>
      )}
      {said && (
        <div className={ROW}>
          <p>{said}</p>
          <Button
            variant="secondary"
            size="pill"
            className="font-medium"
            disabled={sending !== null}
            onClick={() => void relevance({ undo: true })}
          >
            Undo the call
          </Button>
        </div>
      )}
      {t.read_as_plan && <p>{readLine(t.read_as_plan)}</p>}
      {offerCall && <h3 className={H3}>Your call</h3>}
      {(offerCall || offerRead) && (
        <div className={ROW}>
          <Label className="grid gap-1 text-sm leading-normal font-normal">
            Your name
            <Input
              type="text"
              className="h-11 rounded-xl bg-card px-3 text-base md:text-base"
              maxLength={100}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </Label>
          {offerCall && (
            <>
              <Button
                size="pill"
                disabled={blocked}
                onClick={() => {
                  call('related');
                }}
              >
                It is related
              </Button>
              <Button
                variant="secondary"
                size="pill"
                className="font-medium"
                disabled={blocked}
                onClick={() => {
                  call('unrelated');
                }}
              >
                It is not related
              </Button>
            </>
          )}
          {offerRead && (
            <Button
              variant="secondary"
              size="pill"
              className="font-medium"
              disabled={blocked}
              onClick={read}
            >
              Read it as a floor plan
            </Button>
          )}
          {offerCall && (
            <p className={MUTED}>
              Your call replaces the suggestion and settles this file&apos;s issue. It does not read
              the file as a plan.
            </p>
          )}
        </div>
      )}
      {sending && <p>{sending}</p>}
      {failed && (
        <p role="alert" className="font-semibold text-danger">
          {failed}
        </p>
      )}
    </Card>
  );
}
