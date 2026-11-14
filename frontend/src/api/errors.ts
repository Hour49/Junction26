/** Every error body of the backend (docs/API.md "Errors"); not declared in the OpenAPI document. */
export interface ErrorBody {
  detail: string;
  code: string;
  errors?: unknown[];
}

/** A non-2xx answer, or no answer at all (`status` 0, `code` "network"). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly errors: unknown[] | undefined;

  constructor(status: number, code: string, detail: string, errors?: unknown[]) {
    super(`${detail} (${code})`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.errors = errors;
  }
}

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== 'object' || body === null) return false;
  const { detail, code } = body as Record<string, unknown>;
  return typeof detail === 'string' && typeof code === 'string';
}

/** One line for any error: an `ApiError`'s detail and code, else the message. */
export function errorText(error: unknown): { detail: string; code: string } {
  if (error instanceof ApiError) return { detail: error.detail, code: error.code };
  if (error instanceof Error) return { detail: error.message, code: 'client' };
  return { detail: typeof error === 'string' ? error : 'unknown error', code: 'client' };
}

export async function errorOf(response: Response): Promise<ApiError> {
  const text = await response.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    body = null; // not JSON (a proxy page): the fallback below
  }
  if (!isErrorBody(body)) {
    return new ApiError(
      response.status,
      `http-${String(response.status)}`,
      `the server answered ${String(response.status)}`,
    );
  }
  const errors = Array.isArray(body.errors) ? body.errors : undefined;
  return new ApiError(response.status, body.code, body.detail, errors);
}
