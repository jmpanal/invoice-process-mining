const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8010';

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export const API_URL = API_BASE;

async function errorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return `${response.status} ${response.statusText}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === 'string') return parsed.detail;
  } catch {
    return text;
  }
  return text;
}
