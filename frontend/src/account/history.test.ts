import { must } from '../ingest/testing';
import { describe, expect, it } from 'vitest';
import type { ConflictEntry, ProjectReview, Takeoff } from '../api';
import {
  project,
  projectFailed,
  projectList,
  projectReview,
  projectRunning,
  takeoff,
} from '../api/fixtures';
import { formatMs, formatSize, progressOf } from '../ingest/ingest';
import { historyEvents, workspaceKind, workspacePill, workspaceStats } from './history';

const summary = must(projectList.projects[0]);
const conflict = must(projectReview.conflicts[0]);

function withConflict(changes: Partial<ConflictEntry>): ProjectReview {
  return { ...projectReview, conflicts: [{ ...conflict, ...changes }] };
}

describe('workspaceKind', () => {
  it('AC-2 an archive reads "Archive · 11 files · 5 drawings"', () => {
    expect(workspaceKind(summary)).toBe('Archive · 11 files · 5 drawings');
  });
  it('AC-3 one file reads "Single file · 1 file · 1 drawing"', () => {
    expect(workspaceKind({ ...summary, files: 1, drawings: 1 })).toBe(
      'Single file · 1 file · 1 drawing',
    );
  });
});

describe('workspacePill', () => {
  it('AC-4 each state has its word', () => {
    expect(workspacePill('queued').word).toBe('Reading');
    expect(workspacePill('running').word).toBe('Reading');
    expect(workspacePill('done').word).toBe('Ready');
    expect(workspacePill('failed').word).toBe('Failed');
  });
});

describe('workspaceStats', () => {
  it('AC-11 sums the fixture', () => {
    const toReview = projectReview.drawings.reduce((n, d) => n + d.to_review, 0);
    const signed = projectReview.drawings.reduce((n, d) => n + d.signed, 0);
    const total = projectReview.drawings.reduce((n, d) => n + d.quantities, 0);
    expect(workspaceStats(project, projectReview)).toEqual([
      { label: 'Files', value: String(project.files.length) },
      { label: 'Drawings', value: String(project.drawings.length) },
      { label: 'Questions', value: '0', pending: 'GET /api/projects/{id}/questions' },
      { label: 'To review', value: String(toReview) },
      { label: 'Signed off', value: `${String(signed)} of ${String(total)}` },
    ]);
  });
  it('AC-15 without a review the review stats read "–"', () => {
    const stats = workspaceStats(project, null);
    expect(stats.map((s) => s.value)).toEqual([
      String(project.files.length),
      String(project.drawings.length),
      '–',
      '–',
      '–',
    ]);
  });
});

describe('historyEvents', () => {
  it('AC-16 upload, analysis done, decided by rule', () => {
    const size = project.files.reduce((n, f) => n + f.size, 0);
    const events = historyEvents(project, projectReview, []);
    expect(events.map((e) => [e.title, e.detail])).toEqual([
      [
        'Uploaded sample-project.zip',
        `${String(project.files.length)} files · ${formatSize(size)}`,
      ],
      [
        'Analysis done',
        `5 drawings · 3 ready, 4 flagged, 2 set aside, 2 text only · ${formatMs(project.ms)}`,
      ],
      [
        'Decided by rule: area of room (name 1.01)',
        "plans/flat-b.pdf · kept 30.00 m² · the printed label over the outline at the sheet's scale",
      ],
    ]);
    expect(must(events[0]).time).toBe('08:00');
  });

  it('AC-16 zero counts are left out of the analysis line', () => {
    const p = { ...project, counts: { ready: 3, flagged: 0, set_aside: 0, text_only: 0 } };
    const done = historyEvents(p, null, []).find((e) => e.kind === 'done');
    expect(done?.detail).toBe(`5 drawings · 3 ready · ${formatMs(project.ms)}`);
  });

  it('AC-17 a settled conflict gives "Conflict settled" and no rule event', () => {
    const review = withConflict({ settled: { value: 22.401, at: '2026-11-14T09:30:00Z' } });
    const events = historyEvents(project, review, []);
    const settled = events.find((e) => e.kind === 'settled');
    expect(settled).toMatchObject({
      title: 'Conflict settled: area of room (name 1.01)',
      detail: 'plans/flat-b.pdf · kept 22.40 m²',
      time: '09:30',
    });
    expect(events.some((e) => e.title.startsWith('Decided by rule'))).toBe(false);
  });

  it('AC-18 a conflict that needs a person', () => {
    const review = withConflict({
      needs_person: true,
      conflict: { ...conflict.conflict, resolution: null },
    });
    const needs = historyEvents(project, review, []).find((e) => e.kind === 'needs');
    expect(needs).toMatchObject({
      title: 'Conflict waiting for you: area of room (name 1.01)',
      detail: 'plans/flat-b.pdf · 22.40 m² vs 30.00 m²',
    });
  });

  it('AC-19 a signed takeoff row', () => {
    const row =
      takeoff.quantities.find((q) => q.label === 'door count') ?? must(takeoff.quantities[0]);
    const signed: Takeoff = {
      ...takeoff,
      quantities: [
        {
          ...row,
          label: 'door count',
          unit: 'count',
          signed: { by: 'Ana', at: '2026-11-14T09:40:00Z', value: 2 },
        },
      ],
    };
    const event = historyEvents(project, projectReview, [signed]).find((e) => e.kind === 'signed');
    expect(event).toMatchObject({
      title: 'Signed off: door count',
      detail: `${takeoff.file} · 2 · by Ana`,
      time: '09:40',
    });
  });

  it('AC-20 sorted by time, equal times keep the table order', () => {
    const review = withConflict({ settled: { value: 22.401, at: '2026-11-14T07:00:00Z' } });
    const kinds = historyEvents(project, review, []).map((e) => e.kind);
    expect(kinds).toEqual(['settled', 'upload', 'done']);
  });

  it('AC-21 running and failed', () => {
    const running = historyEvents(projectRunning, null, []);
    const { done, total } = progressOf(projectRunning.files);
    expect(running.find((e) => e.kind === 'reading')?.detail).toBe(
      `${String(done)} of ${String(total)} files`,
    );
    expect(running.some((e) => e.title === 'Analysis done')).toBe(false);
    const failed = historyEvents(projectFailed, null, []).find((e) => e.kind === 'failed');
    expect(failed).toMatchObject({ title: 'Ingest failed', detail: projectFailed.error });
  });
});
