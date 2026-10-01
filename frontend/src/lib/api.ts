/** Thin client for the Django API. Every error has { error, code } with a sentence we can show as-is. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

type Listener = (code: string) => void;
const listeners = new Set<Listener>();
/** The app listens for "locked" and "signed_out" to show the lock or welcome screen. */
export const onAuthProblem = (fn: Listener) => { listeners.add(fn); return () => { listeners.delete(fn); }; };

function csrf(): string {
  return document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1] ?? '';
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers: {
      ...(isForm || body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(method === 'GET' ? {} : { 'X-CSRFToken': decodeURIComponent(csrf()) }),
    },
    body: isForm ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    const code = data?.code ?? 'error';
    if (code === 'locked' || code === 'signed_out') listeners.forEach((l) => l(code));
    throw new ApiError(res.status, code, data?.error ?? "Something went wrong. Check your connection and try again.");
  }
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>('GET', p),
  post: <T>(p: string, b?: unknown) => request<T>('POST', p, b ?? {}),
  patch: <T>(p: string, b: unknown) => request<T>('PATCH', p, b),
  del: <T>(p: string) => request<T>('DELETE', p),
};
