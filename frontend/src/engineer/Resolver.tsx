import { formatValue, resolverModel, resolverName, type AnswerView } from '../api';

/** resolver.md RS-20..23: Carbon's pick or "could not tell" beside an uncertain answer, else its note. The
 * answer's value, level and check stay as they are; the model id only in the tooltip. */
export function ResolverLines({ a }: { a: AnswerView }) {
  const r = a.resolved;
  if (!r)
    return a.resolver_note ? <p className="en-small en-resolvernote">{a.resolver_note}</p> : null;
  const who = resolverName(r.by);
  return (
    <p className="en-resolved">
      <b title={resolverModel(r.by)}>
        {r.verdict === 'picked' ? `Picked by ${who}` : `${who} could not tell`}
      </b>
      {r.verdict === 'picked' && r.value !== null && `: ${formatValue(r.value, a.unit)}`}.{' '}
      {r.reason}
    </p>
  );
}
