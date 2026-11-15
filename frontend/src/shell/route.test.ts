import { describe, expect, it } from 'vitest';
import { packOf, parseRoute, routeHref, withPack } from './route';

const P = '5e0c1a2b3d4f';
const D = 'adeefbbcc17559fc';

describe('parseRoute', () => {
  it('SH-1 maps the five route shapes', () => {
    for (const hash of ['', '#', '#/']) expect(parseRoute(hash).name).toBe('home');
    expect(parseRoute(`#/p/${P}`)).toMatchObject({ name: 'project', projectId: P });
    expect(parseRoute(`#/p/${P}/f/f3`)).toMatchObject({ name: 'file', projectId: P, fileId: 'f3' });
    for (const role of ['engineer', 'surveyor'])
      expect(parseRoute(`#/p/${P}/d/${D}/${role}`)).toMatchObject({
        name: 'workspace',
        projectId: P,
        drawingId: D,
        role: 'engineer',
      });
  });

  it('SH-2 ids off their pattern, a workspace without role and other paths are not found', () => {
    for (const hash of [
      '#/p/XYZ',
      `#/p/${P}0`,
      `#/p/${P}/f/3`,
      `#/p/${P}/d/${D.slice(1)}/engineer`,
      `#/p/${P}/d/${D}`,
      `#/p/${P}/d/${D}/admin`,
      '#/nope',
    ])
      expect(parseRoute(hash).name).toBe('not-found');
    expect(parseRoute(`#/p/${P}/`).name).toBe('project');
    expect(parseRoute(`#/p/${P}/d/${D}/surveyor/`).name).toBe('workspace');
    // an old surveyor link is the engineer view of the same drawing (P8)
    expect(routeHref(parseRoute(`#/p/${P}/d/${D}/surveyor?q=door`))).toBe(
      `#/p/${P}/d/${D}/engineer?q=door`,
    );
  });

  it('SH-3 the query parses and round-trips a takeoff key through routeHref', () => {
    const key = 'area:room|name=küche';
    const route = parseRoute(`#/p/${P}/d/${D}/engineer`);
    route.query.set('q', key);
    const href = routeHref(route);
    expect(href).toBe(`#/p/${P}/d/${D}/engineer?q=area%3Aroom%7Cname%3Dk%C3%BCche`);
    const back = parseRoute(href);
    expect(back).toMatchObject({ name: 'workspace', role: 'engineer' });
    expect(back.query.get('q')).toBe(key);
  });

  it('SH-53 account route, and ?view on a project, round-trip', () => {
    for (const hash of ['#/workspaces', '#/workspaces/'])
      expect(parseRoute(hash).name).toBe('account');
    expect(parseRoute('#/workspaces/x').name).toBe('not-found');
    const project = parseRoute(`#/p/${P}?view=advanced`);
    expect(project.name).toBe('project');
    expect(project.query.get('view')).toBe('advanced');
    for (const hash of ['#/workspaces', `#/p/${P}?view=advanced`])
      expect(routeHref(parseRoute(hash))).toBe(hash);
  });

  it('SH-77 the old conflicts and issues routes land on the project route with their query', () => {
    const conflicts = parseRoute(`#/p/${P}/conflicts?q=a&pack=fi&d=${D}`);
    expect(conflicts).toMatchObject({ name: 'project', projectId: P });
    expect(conflicts.query.get('q')).toBe('a');
    expect(conflicts.query.get('d')).toBe(D);
    expect(packOf(conflicts)).toBe('fi');
    for (const hash of [`#/p/${P}/issues?pack=fi`, `#/p/${P}/issues/`, `#/p/${P}/conflicts/`])
      expect(parseRoute(hash)).toMatchObject({ name: 'project', projectId: P });
    expect(routeHref(parseRoute(`#/p/${P}/issues?pack=fi`))).toBe(`#/p/${P}?pack=fi`);
    for (const hash of ['#/p/XYZ/conflicts', `#/p/${P}/conflicts/x`, `#/p/${P}/issues/x`])
      expect(parseRoute(hash).name).toBe('not-found');
  });

  it('SH-80 the about route, with or without ?project', () => {
    for (const hash of ['#/about', '#/about/']) expect(parseRoute(hash).name).toBe('about');
    expect(parseRoute('#/about/x').name).toBe('not-found');
    expect(routeHref(parseRoute(`#/about?project=${P}`))).toBe(`#/about?project=${P}`);
  });

  it('SH-76 the documents route', () => {
    for (const hash of [`#/p/${P}/documents`, `#/p/${P}/documents/`])
      expect(parseRoute(hash)).toMatchObject({ name: 'documents', projectId: P });
    for (const hash of ['#/p/XYZ/documents', `#/p/${P}/documents/x`])
      expect(parseRoute(hash).name).toBe('not-found');
    expect(routeHref(parseRoute(`#/p/${P}/documents?pack=fi`))).toBe(`#/p/${P}/documents?pack=fi`);
  });

  it('SH-64 the chat route', () => {
    for (const hash of [`#/p/${P}/chat`, `#/p/${P}/chat/`])
      expect(parseRoute(hash)).toMatchObject({ name: 'chat', projectId: P });
    for (const hash of ['#/p/XYZ/chat', `#/p/${P}/chat/x`])
      expect(parseRoute(hash).name).toBe('not-found');
    expect(routeHref(parseRoute(`#/p/${P}/chat`))).toBe(`#/p/${P}/chat`);
  });

  it('SH-66 the checks route, packOf and withPack', () => {
    for (const name of ['checks'] as const) {
      for (const hash of [`#/p/${P}/${name}`, `#/p/${P}/${name}/`])
        expect(parseRoute(hash)).toMatchObject({ name, projectId: P });
      for (const hash of [`#/p/XYZ/${name}`, `#/p/${P}/${name}/x`])
        expect(parseRoute(hash).name).toBe('not-found');
      expect(routeHref(parseRoute(`#/p/${P}/${name}?pack=fi`))).toBe(`#/p/${P}/${name}?pack=fi`);
    }
    expect(packOf(parseRoute(`#/p/${P}/checks?pack=fi`))).toBe('fi');
    expect(packOf(parseRoute(`#/p/${P}`))).toBeNull();
    const surveyor = `#/p/${P}/d/${D}/engineer?q=a`;
    expect(withPack(surveyor, 'fi')).toBe(`#/p/${P}/d/${D}/engineer?q=a&pack=fi`);
    expect(withPack(`${surveyor}&pack=fi`, null)).toBe(surveyor);
    expect(withPack(`#/p/${P}?pack=fi`, 'ch')).toBe(`#/p/${P}?pack=ch`);
    expect(withPack(`#/p/${P}`, null)).toBe(`#/p/${P}`);
    expect(withPack(`#/p/${P}/chat`, 'a b')).toBe(`#/p/${P}/chat?pack=a+b`);
  });
});
