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
        role,
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
  });

  it('SH-3 the query parses and round-trips a takeoff key through routeHref', () => {
    const key = 'area:room|name=küche';
    const route = parseRoute(`#/p/${P}/d/${D}/surveyor`);
    route.query.set('q', key);
    const href = routeHref(route);
    expect(href).toBe(`#/p/${P}/d/${D}/surveyor?q=area%3Aroom%7Cname%3Dk%C3%BCche`);
    const back = parseRoute(href);
    expect(back).toMatchObject({ name: 'workspace', role: 'surveyor' });
    expect(back.query.get('q')).toBe(key);
  });

  it('SH-53 account and conflicts routes, and ?view on a project, round-trip', () => {
    for (const hash of ['#/workspaces', '#/workspaces/'])
      expect(parseRoute(hash).name).toBe('account');
    expect(parseRoute(`#/p/${P}/conflicts`)).toMatchObject({ name: 'conflicts', projectId: P });
    for (const hash of ['#/workspaces/x', '#/p/XYZ/conflicts', `#/p/${P}/conflicts/x`])
      expect(parseRoute(hash).name).toBe('not-found');
    const project = parseRoute(`#/p/${P}?view=advanced`);
    expect(project.name).toBe('project');
    expect(project.query.get('view')).toBe('advanced');
    for (const hash of ['#/workspaces', `#/p/${P}/conflicts`, `#/p/${P}?view=advanced`])
      expect(routeHref(parseRoute(hash))).toBe(hash);
  });

  it('SH-64 the chat route', () => {
    for (const hash of [`#/p/${P}/chat`, `#/p/${P}/chat/`])
      expect(parseRoute(hash)).toMatchObject({ name: 'chat', projectId: P });
    for (const hash of ['#/p/XYZ/chat', `#/p/${P}/chat/x`])
      expect(parseRoute(hash).name).toBe('not-found');
    expect(routeHref(parseRoute(`#/p/${P}/chat`))).toBe(`#/p/${P}/chat`);
  });

  it('SH-66 checks and issues routes, packOf and withPack', () => {
    for (const name of ['checks', 'issues'] as const) {
      for (const hash of [`#/p/${P}/${name}`, `#/p/${P}/${name}/`])
        expect(parseRoute(hash)).toMatchObject({ name, projectId: P });
      for (const hash of [`#/p/XYZ/${name}`, `#/p/${P}/${name}/x`])
        expect(parseRoute(hash).name).toBe('not-found');
      expect(routeHref(parseRoute(`#/p/${P}/${name}?pack=fi`))).toBe(`#/p/${P}/${name}?pack=fi`);
    }
    expect(packOf(parseRoute(`#/p/${P}/checks?pack=fi`))).toBe('fi');
    expect(packOf(parseRoute(`#/p/${P}`))).toBeNull();
    const surveyor = `#/p/${P}/d/${D}/surveyor?q=a`;
    expect(withPack(surveyor, 'fi')).toBe(`#/p/${P}/d/${D}/surveyor?q=a&pack=fi`);
    expect(withPack(`${surveyor}&pack=fi`, null)).toBe(surveyor);
    expect(withPack(`#/p/${P}?pack=fi`, 'ch')).toBe(`#/p/${P}?pack=ch`);
    expect(withPack(`#/p/${P}`, null)).toBe(`#/p/${P}`);
    expect(withPack(`#/p/${P}/chat`, 'a b')).toBe(`#/p/${P}/chat?pack=a+b`);
  });
});
