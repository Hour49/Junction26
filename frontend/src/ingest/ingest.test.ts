import { describe, expect, it } from 'vitest';
import { project } from '../api/fixtures';
import { formatCost, formatMs, formatSize, progressOf, stageCounts } from './ingest';
import { variants } from './testing';

describe('ingest.ts', () => {
  it('IN-17 progressOf counts ready, flagged, text_only and set_aside as finished', () => {
    const states = ['ready', 'flagged', 'text_only', 'set_aside', 'queued', 'running'] as const;
    expect(progressOf(states.map((state) => ({ state })))).toEqual({ done: 4, total: 6 });
    expect(progressOf(project.files)).toEqual({ done: 3, total: 3 });
  });

  it('IN-30 stageCounts: every stage in API order, files per latest stage, null stage is waiting', () => {
    const { waiting, stages } = stageCounts(project.files);
    expect(stages.map((s) => s.stage)).toEqual([
      'unpack',
      'hash',
      'identify',
      'group',
      'route',
      'cache',
      'normalise',
      'extract',
      'second_count',
      'takeoff',
      'write',
    ]);
    expect(waiting).toBe(0);
    expect(stages.find((s) => s.stage === 'write')?.count).toBe(project.files.length);
    expect(stageCounts(variants.queued.files).waiting).toBe(project.files.length);
  });

  it('IN-34 formatMs, formatCost and formatSize', () => {
    expect(formatMs(0.6838)).toBe('0.68 ms');
    expect(formatMs(12.5)).toBe('12.5 ms');
    expect(formatMs(1234)).toBe('1.2 s');
    expect(formatCost(0)).toBe('$0.00');
    expect(formatCost(0.004)).toBe('<$0.01');
    expect(formatCost(0.123)).toBe('$0.12');
    expect(formatSize(2263)).toBe('2.2 KB');
    expect(formatSize(1048576)).toBe('1.0 MB');
  });
});
