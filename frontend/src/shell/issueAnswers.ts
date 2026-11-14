import { useSyncExternalStore } from 'react';

// shortcut: typed answers live in memory only (shared.md "Answers store", Open point 26): a reload forgets them;
// replace with the API's answer field when API ask A1 lands.
const byProject = new Map<string, ReadonlyMap<string, string>>();
const listeners = new Set<() => void>();
const NONE: ReadonlyMap<string, string> = new Map();

/** The answer typed for an issue in this tab, or null. */
export function answerOf(projectId: string, issueId: string): string | null {
  return byProject.get(projectId)?.get(issueId) ?? null;
}

/** Stores (or with null, clears) an issue's typed answer; every `useIssueAnswers` of that project re-renders. */
export function setAnswer(projectId: string, issueId: string, text: string | null): void {
  const next = new Map(byProject.get(projectId) ?? NONE);
  if (text === null) next.delete(issueId);
  else next.set(issueId, text);
  byProject.set(projectId, next); // a new map per change: React sees the snapshot change
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** The project's typed answers, issue id → text (the `answers` of `needsYou(issues, answers)`). */
export function useIssueAnswers(projectId: string): ReadonlyMap<string, string> {
  return useSyncExternalStore(subscribe, () => byProject.get(projectId) ?? NONE);
}
