import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it } from 'vitest';
import { stubResizeObserver } from '../../test/resizeObserver';
import { Tip } from './tip';

beforeEach(stubResizeObserver);
afterEach(cleanup);

const open = () => screen.queryAllByRole('tooltip').length > 0;

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

it('shows on a tap and closes on the next tap', async () => {
  render(
    <Tip text="Tapped.">
      <button>Tap</button>
    </Tip>,
  );
  const b = screen.getByRole('button', { name: 'Tap' });
  fireEvent.pointerDown(b, { pointerType: 'touch' });
  fireEvent.click(b);
  await screen.findByRole('tooltip');
  fireEvent.pointerDown(b, { pointerType: 'touch' });
  fireEvent.click(b);
  expect(open()).toBe(false);
});

it('closes on a tap outside after a tap opened it', async () => {
  render(
    <>
      <Tip text="Tapped.">
        <button>Tap</button>
      </Tip>
      <p>elsewhere</p>
    </>,
  );
  const b = screen.getByRole('button', { name: 'Tap' });
  fireEvent.pointerDown(b, { pointerType: 'touch' });
  fireEvent.click(b);
  await screen.findByRole('tooltip');
  fireEvent.pointerDown(screen.getByText('elsewhere'), { pointerType: 'touch' });
  await waitFor(() => {
    expect(open()).toBe(false);
  });
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
