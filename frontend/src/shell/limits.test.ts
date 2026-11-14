import { expect, it } from 'vitest';
import { info } from '../api/fixtures';
import { uploadTooLarge } from './limits';

it('SH-22 uploadTooLarge refuses one byte over upload_mb', () => {
  const limit = info.limits.upload_mb * 2 ** 20;
  expect(uploadTooLarge(limit, info.limits)).toBeNull();
  const refusal = uploadTooLarge(limit + 1, info.limits);
  expect(refusal).toContain('200.0 MB');
  expect(refusal).toContain('the limit is 200 MB');
});
