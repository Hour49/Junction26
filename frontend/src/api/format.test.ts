import { afterEach, expect, it } from 'vitest';
import { formatTime, formatValue } from './format';
import { projectList } from './fixtures';

const zone = process.env.TZ;
afterEach(() => {
  process.env.TZ = zone;
});

it('SH-43 formatValue and formatTime follow the shared rule', () => {
  expect(formatValue(2, 'count')).toBe('2');
  expect(formatValue(52.27, 'm2')).toBe('52.27 m²');
  expect(formatValue(22.401, 'm2')).toBe('22.40 m²');
  expect(formatValue(30.0, 'm2')).toBe('30.00 m²');
  expect(formatValue(1.5, 'ft2')).toBe('1.50 ft²');
  expect(formatValue(3, null)).toBe('3');
  process.env.TZ = 'Europe/Helsinki';
  expect(formatTime(projectList.projects[0]?.created_at ?? '')).toBe('2026-11-14 08:00 UTC');
});
