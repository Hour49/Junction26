const UNITS: Record<string, string> = { m: 'm', m2: 'm²', m3: 'm³', ft: 'ft', ft2: 'ft²' };

/** A value as every screen shows it: a count as an integer, anything else with 2 decimals and its unit. */
export function formatValue(value: number, unit: string | null): string {
  if (unit === null || unit === 'count') return String(Math.round(value));
  return `${value.toFixed(2)} ${UNITS[unit] ?? unit}`;
}

/** `YYYY-MM-DD HH:MM UTC`, whatever the browser's time zone. */
export function formatTime(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return `${at.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}
