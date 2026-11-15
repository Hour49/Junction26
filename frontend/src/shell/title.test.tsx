import { cleanup, render } from '@testing-library/react';
import { act } from 'react';
import { afterEach, expect, it } from 'vitest';
import { parseRoute } from './route';
import { rememberProjectName, titleOf, useDocumentTitle } from './title';
import { NotFound } from './NotFound';

afterEach(cleanup);
const P = 'a1b2c3d4e5f6';

it('R4-E4 titleOf: screen · project · Vellum, and just Vellum without a project', () => {
  expect(titleOf(parseRoute(`#/p/${P}/documents`), 'Flat sample')).toBe(
    'Documents · Flat sample · Vellum',
  );
  expect(titleOf(parseRoute(`#/p/${P}/chat`), undefined)).toBe('Chat · Vellum');
  expect(titleOf(parseRoute('#/'), undefined)).toBe('Vellum');
  expect(titleOf(parseRoute('#/workspaces'), undefined)).toBe('Vellum');
  expect(titleOf(parseRoute('#/nope'), undefined)).toBe('Vellum');
});

it('R4-E4 the hook sets document.title and follows the project name once it is known', () => {
  const route = parseRoute(`#/p/${P}`);
  const Probe = () => {
    useDocumentTitle(route);
    return null;
  };
  render(<Probe />);
  expect(document.title).toBe('Ingest · Vellum');
  act(() => {
    rememberProjectName(P, 'Flat sample');
  });
  expect(document.title).toBe('Ingest · Flat sample · Vellum');
});

it('R4-E3 the not-found screen has an h1', () => {
  const { container } = render(<NotFound hash="#/nope" />);
  expect(container.querySelector('h1')?.textContent).toBe('Page not found');
  expect(container.querySelector('h2')).toBeNull();
});
