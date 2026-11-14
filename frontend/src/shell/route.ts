import { useSyncExternalStore } from 'react';

export type Role = 'engineer' | 'surveyor';

export type Route =
  | { name: 'home'; query: URLSearchParams }
  | { name: 'account'; query: URLSearchParams }
  | { name: 'project'; projectId: string; query: URLSearchParams }
  | { name: 'conflicts'; projectId: string; query: URLSearchParams }
  | { name: 'file'; projectId: string; fileId: string; query: URLSearchParams }
  | { name: 'workspace'; projectId: string; drawingId: string; role: Role; query: URLSearchParams }
  | { name: 'not-found'; hash: string; query: URLSearchParams };

const PROJECT = '([0-9a-f]{12})';
const FILE = new RegExp(`^/p/${PROJECT}/f/(f\\d+)$`);
const WORKSPACE = new RegExp(`^/p/${PROJECT}/d/([0-9a-f]{16})/(engineer|surveyor)$`);
const PROJECT_ONLY = new RegExp(`^/p/${PROJECT}$`);
const CONFLICTS = new RegExp(`^/p/${PROJECT}/conflicts$`);

/** The route of a location hash (`#/p/<id>/d/<id>/engineer?q=door`); ids off their pattern are not found. */
export function parseRoute(hash: string): Route {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const mark = raw.indexOf('?');
  const pathPart = mark < 0 ? raw : raw.slice(0, mark);
  const query = new URLSearchParams(mark < 0 ? '' : raw.slice(mark + 1));
  const path = pathPart === '' ? '/' : pathPart.replace(/(.)\/$/, '$1');
  if (path === '/') return { name: 'home', query };
  if (path === '/workspaces') return { name: 'account', query };
  let m = PROJECT_ONLY.exec(path);
  if (m?.[1]) return { name: 'project', projectId: m[1], query };
  m = CONFLICTS.exec(path);
  if (m?.[1]) return { name: 'conflicts', projectId: m[1], query };
  m = FILE.exec(path);
  if (m?.[1] && m[2]) return { name: 'file', projectId: m[1], fileId: m[2], query };
  m = WORKSPACE.exec(path);
  if (m?.[1] && m[2] && m[3]) {
    const role = m[3] === 'surveyor' ? 'surveyor' : 'engineer';
    return { name: 'workspace', projectId: m[1], drawingId: m[2], role, query };
  }
  return { name: 'not-found', hash, query };
}

/** The route's path, without the query: the shell keys each screen by it. */
export function routePath(route: Route): string {
  switch (route.name) {
    case 'home':
      return '/';
    case 'account':
      return '/workspaces';
    case 'project':
      return `/p/${route.projectId}`;
    case 'conflicts':
      return `/p/${route.projectId}/conflicts`;
    case 'file':
      return `/p/${route.projectId}/f/${route.fileId}`;
    case 'workspace':
      return `/p/${route.projectId}/d/${route.drawingId}/${route.role}`;
    case 'not-found':
      return route.hash.replace(/^#/, '').split('?')[0] ?? '';
  }
}

/** The hash of a route; the query (e.g. a takeoff key in `q`) is percent-encoded. */
export function routeHref(route: Route): string {
  const query = route.query.toString();
  return `#${routePath(route)}${query ? `?${query}` : ''}`;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => {
    window.removeEventListener('hashchange', onChange);
  };
}

const currentHash = () => window.location.hash;

/** The location hash, re-read on every `hashchange`. */
export function useHash(): string {
  return useSyncExternalStore(subscribe, currentHash);
}
