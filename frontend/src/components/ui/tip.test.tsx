import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { stubResizeObserver } from '../../test/resizeObserver';
import { Tip } from './tip';

beforeEach(stubResizeObserver);
afterEach(cleanup);

const open = () => screen.queryAllByRole('tooltip').length > 0;

/**
 * A finger tap in the order a phone browser sends it (Chromium, traced in e2e/tip-tap.spec.ts): the pointer goes
 * down and up, then the compatibility mousedown focuses the element, then the click.
 */
function tap(el: HTMLElement) {
  fireEvent.pointerDown(el, { pointerType: 'touch' });
  fireEvent.pointerUp(el, { pointerType: 'touch' });
  act(() => {
    el.focus();
  });
  fireEvent.click(el);
}

it('shows on hover and hides on leave', async () => {
  render(
    <Tip text="Ask a question.">
      <button>Ask</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Ask' });
  expect(open()).toBe(false);
  fireEvent.pointerMove(b, { pointerType: 'mouse' });
  expect((await screen.findAllByText('Ask a question.')).length).toBeGreaterThan(0);
  expect(open()).toBe(true);
  fireEvent.pointerLeave(b, { pointerType: 'mouse' });
  fireEvent.pointerMove(document.body, { clientX: 900, clientY: 900 });
  await waitFor(() => {
    expect(open()).toBe(false);
  });
});

it('shows on keyboard focus, describes the trigger, and Escape closes it', async () => {
  render(
    <Tip text="Add a photo.">
      <button>Photo</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Photo' });
  b.focus();
  await screen.findByRole('tooltip');
  expect(b.getAttribute('aria-describedby')).toBeTruthy();
  fireEvent.keyDown(document.activeElement ?? b, { key: 'Escape' });
  expect(open()).toBe(false);
});

it('shows on a tap on a label and closes on the next tap', async () => {
  render(
    <Tip text="Tapped." wrap>
      <span>3 rooms</span>
    </Tip>,
  );
  const label = screen.getByText('3 rooms').parentElement as HTMLElement;
  tap(label);
  await screen.findByRole('tooltip');
  expect(label.dataset.state).toMatch(/open/);
  tap(label);
  expect(label.dataset.state).toBe('closed');
  await waitFor(() => {
    expect(open()).toBe(false);
  });
});

it('a tap on a working button runs it and shows no tip', () => {
  const run = vi.fn();
  render(
    <Tip text="Ask a question.">
      <button onClick={run}>Ask</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Ask' });
  tap(b);
  expect(run).toHaveBeenCalledTimes(1);
  expect(b.dataset.state).toBe('closed');
  expect(open()).toBe(false);
});

it('a tap on a locked button shows why it is locked', async () => {
  render(
    <Tip text="Type your name first." wrap>
      <button disabled>Sign off</button>
    </Tip>,
  );
  // the wrapper's [&>*]:pointer-events-none sends the tap to the wrapper, not the disabled button
  const wrapper = screen.getByRole('button', { name: 'Sign off' }).parentElement as HTMLElement;
  tap(wrapper);
  await screen.findByRole('tooltip');
  expect(wrapper.dataset.state).toMatch(/open/);
});

it('closes on a tap outside after a tap opened it', async () => {
  render(
    <>
      <Tip text="Tapped." wrap>
        <span>3 rooms</span>
      </Tip>
      <p>elsewhere</p>
    </>,
  );
  const label = screen.getByText('3 rooms').parentElement as HTMLElement;
  tap(label);
  await screen.findByRole('tooltip');
  fireEvent.pointerDown(screen.getByText('elsewhere'), { pointerType: 'touch' });
  await waitFor(() => {
    expect(open()).toBe(false);
  });
});

it('a touch that turned into a scroll does not block the tip afterwards', async () => {
  render(
    <Tip text="Add a photo.">
      <button>Photo</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Photo' });
  fireEvent.pointerDown(b, { pointerType: 'touch' });
  fireEvent.pointerCancel(b, { pointerType: 'touch' }); // the browser took the touch for a scroll: no click
  fireEvent.pointerUp(document.body, { pointerType: 'touch' });
  fireEvent.keyDown(document.body, { key: 'Tab' }); // keyboard focus opens the tip
  b.focus();
  await screen.findByRole('tooltip');
});

it('closes on a tap outside even when the opening tap never produced a click', async () => {
  render(
    <>
      <Tip text="Tapped.">
        <button>Tap</button>
      </Tip>
      <p>elsewhere</p>
    </>,
  );
  const b = screen.getByRole('button', { name: 'Tap' });
  fireEvent.keyDown(document.body, { key: 'Tab' });
  b.focus();
  await screen.findByRole('tooltip');
  // a touch that starts on the button but is dragged away: pointerdown, no click
  fireEvent.pointerDown(b, { pointerType: 'touch' });
  fireEvent.pointerDown(screen.getByText('elsewhere'), { pointerType: 'touch' });
  await waitFor(() => {
    expect(open()).toBe(false);
  });
});

it('works on a disabled button through the wrapping span', async () => {
  render(
    <Tip text="Type your name first." wrap>
      <button disabled>Sign off</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Sign off' });
  const wrapper = b.parentElement as HTMLElement;
  expect(wrapper.tabIndex).toBe(0);
  fireEvent.keyDown(document.body, { key: 'Tab' });
  wrapper.focus();
  await screen.findByRole('tooltip');
  expect(wrapper.getAttribute('aria-describedby')).toBeTruthy();
  expect(screen.getAllByText('Type your name first.').length).toBeGreaterThan(0);
});

it('R4-E17 a focus the page gives after a pointer press opens no tip; keyboard focus does', async () => {
  render(
    <Tip text="Country rules.">
      <button>Country</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Country' });
  fireEvent.pointerDown(document.body, { pointerType: 'mouse' }); // the click that picked a country
  b.focus(); // the closed popover returns focus to its button
  await new Promise((r) => setTimeout(r, 300));
  expect(screen.queryByRole('tooltip')).toBeNull();
  b.blur();
  fireEvent.keyDown(document.body, { key: 'Tab' });
  b.focus();
  expect((await screen.findByRole('tooltip')).textContent).toContain('Country rules.');
});

it('R2-D6 the wrapper a locked button gets to show its tip is a named Tab stop, not an unnamed one', () => {
  render(
    <Tip text="Type a question first." wrap>
      <button disabled aria-label="Ask" />
    </Tip>,
  );
  const wrapper = screen.getByRole('button', { name: 'Ask' }).parentElement as HTMLElement;
  expect(wrapper.tabIndex).toBe(0);
  expect(wrapper.getAttribute('role')).toBe('group');
  expect(wrapper.getAttribute('aria-label')).toBe('Type a question first.');
});

it('R2-D3 a label, number or badge with a tip is not a Tab stop; a screen reader still gets the tip', () => {
  render(
    <Tip text="Files that finished reading." wrap>
      <span>Files through</span>
    </Tip>,
  );
  const label = screen.getByText('Files through').parentElement as HTMLElement;
  expect(label.tabIndex).toBe(-1);
  expect(label.getAttribute('aria-description')).toBe('Files that finished reading.');
});
