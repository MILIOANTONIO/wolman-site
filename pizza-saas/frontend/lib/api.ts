export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// FastAPI restituisce "detail" come stringa per i nostri HTTPException, ma
// come array di oggetti {msg, loc, ...} per gli errori di validazione Pydantic
// automatici (422) - senza questa normalizzazione l'errore appariva come
// "[object Object]" invece del messaggio vero.
function extractErrorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d))).join("; ");
  }
  return `Errore ${status}`;
}

// "Failed to fetch" (Chrome) / "NetworkError" (Firefox) sono i messaggi
// grezzi del browser quando la richiesta non arriva nemmeno al server
// (server spento, CORS, nessuna connessione) - li traduciamo in un
// messaggio comprensibile invece di mostrarli così come sono.
async function safeFetch(url: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(url, options);
  } catch {
    throw new Error("Impossibile contattare il server. Verifica che sia acceso e riprova.");
  }
}

async function request(path: string, options: RequestInit = {}) {
  const res = await safeFetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(body, res.status));
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body?: unknown) => request(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: (path: string, body?: unknown) => request(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: (path: string) => request(path, { method: "DELETE" }),
};

export async function uploadFile(path: string, file: File, fields: Record<string, string> = {}) {
  const form = new FormData();
  form.append("file", file);
  const query = new URLSearchParams(fields).toString();
  const res = await safeFetch(`${API_URL}${path}?${query}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(body, res.status));
  }
  return res.json();
}

export async function fetchAudioBlobUrl(path: string): Promise<string> {
  const res = await safeFetch(`${API_URL}${path}`, { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(body, res.status));
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function uploadFiles(path: string, files: File[]) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await safeFetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(body, res.status));
  }
  return res.json();
}
