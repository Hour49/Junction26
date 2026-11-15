import { useEffect, useSyncExternalStore } from 'react';
import { PRODUCT_NAME } from './strings';
import type { Route } from './route';

// Project names seen by the shell's own project request (the Documents badge asks for the project on every route
// change), so the tab title needs no request of its own.
const names = new Map<string, string>();
const listeners = new Set<() => void>();

/** Remember a project's name for the browser tab title. */
export function rememberProjectName(projectId: string, name: string): void {
  if (names.get(projectId) === name) return;
  names.set(projectId, name);
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const SCREEN: Partial<Record<Route['name'], string>> = {
  project: 'Ingest',
  chat: 'Chat',
  checks: 'Checks',
  documents: 'Documents',
  file: 'File',
  workspace: 'Drawing',
};

/** "<screen> · <project> · Vellum"; just "Vellum" on a screen without a project (R4-E4). */
export function titleOf(route: Route, projectName: string | undefined): string {
  const screen = SCREEN[route.name];
  if (!screen) return PRODUCT_NAME;
  return [screen, projectName, PRODUCT_NAME].filter(Boolean).join(' · ');
}

/** Keeps `document.title` in step with the route. */
export function useDocumentTitle(route: Route): void {
  const id = 'projectId' in route ? route.projectId : null;
  const name = useSyncExternalStore(subscribe, () => (id ? names.get(id) : undefined));
  const title = titleOf(route, name);
  useEffect(() => {
    document.title = title;
  }, [title]);
}
