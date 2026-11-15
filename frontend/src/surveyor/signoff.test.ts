// R4-B10: the sign-off says which value the surveyor saw, so the server can refuse a value changed since.
import { describe, expect, it } from 'vitest';
import { signoffBody } from './signoff';

describe('signoffBody', () => {
  it('sends the value on screen under the field the server reads', () => {
    expect(signoffBody({ key: 'door', value: 2 }, 'Ana', false, 'seen')).toEqual({
      quantity: 'door',
      by: 'Ana',
      seen: 2,
    });
  });
  it('R4-B10 by default sends expected_value, and expected_unit when the row has its unit', () => {
    expect(signoffBody({ key: 'door', value: 2, unit: 'count' }, 'Ana', false)).toEqual({
      quantity: 'door',
      by: 'Ana',
      expected_value: 2,
      expected_unit: 'count',
    });
    expect(signoffBody({ key: 'door', value: 2 }, 'Ana', false)).toEqual({
      quantity: 'door',
      by: 'Ana',
      expected_value: 2,
    });
  });
  it('no value with an undo, nor while the server takes no such field (null)', () => {
    expect(signoffBody({ key: 'door', value: 2 }, 'Ana', true, 'seen')).toEqual({
      quantity: 'door',
      by: 'Ana',
      undo: true,
    });
    expect(signoffBody({ key: 'door', value: 2 }, 'Ana', false, null)).toEqual({
      quantity: 'door',
      by: 'Ana',
    });
  });
});
