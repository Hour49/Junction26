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
  wrapper.focus();
  await screen.findByRole('tooltip');
  expect(wrapper.getAttribute('aria-describedby')).toBeTruthy();
  expect(screen.getAllByText('Type your name first.').length).toBeGreaterThan(0);
});
