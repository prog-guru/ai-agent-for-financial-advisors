// lib/api.ts - Updated to include authentication
export type Person = { id: string; name: string; avatar?: string };
export type Meeting = {
  id: number;
  title: string;
  start_iso: string;
  end_iso: string;
  attendees: { people: Person[] };
};
export type Message = {
  id: number;
  role: "system" | "assistant" | "user";
  content: string;
  created_at: string; // ISO
};

export type ChatSendResponse = {
  messages: Message[];
  meetings: Meeting[];
};

// --- Base URL from env
const API_BASE = process.env.NEXT_PUBLIC_API_URL;
if (!API_BASE) {
  console.warn(
    "NEXT_PUBLIC_API_URL is not set. Set it in .env.local, e.g. NEXT_PUBLIC_API_URL=http://localhost:8001/api"
  );
}

// --- Low-level request helper with credentials
async function request<T>(
  path: string,
  opts: RequestInit = {},
  { timeoutMs = 15000 }: { timeoutMs?: number } = {}
): Promise<T> {
  if (!API_BASE) throw new Error("API base URL not configured");
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const merged: RequestInit = {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    credentials: "include", // Important: include cookies for authentication
    ...opts,
    signal: controller.signal,
  };

  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, merged as RequestInit);
  } catch (e: unknown) {
    clearTimeout(timeout);
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Request timed out");
    }
    const message = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error: ${message}`);
  } finally {
    clearTimeout(timeout);
  }

  let payload: unknown = null;
  const text = await res.text();
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!res.ok) {
    const detail =
      (typeof payload === "object" && payload !== null && "detail" in payload && (payload as any).detail) ||
      (typeof payload === "object" && payload !== null && "message" in payload && (payload as any).message) ||
      res.statusText ||
      "Request failed";
    throw new Error(`${res.status} ${detail}`);
  }

  return payload as T;
}

// ===== Public API =====

export async function fetchMeetings(): Promise<Meeting[]> {
  return request<Meeting[]>("/meetings", { method: "GET", cache: "no-store" });
}

export async function fetchMessages(): Promise<Message[]> {
  return request<Message[]>("/chat/messages", { method: "GET", cache: "no-store" });
}

export async function sendMessage(content: string): Promise<ChatSendResponse> {
  return request<ChatSendResponse>("/chat/messages", {
    method: "POST",
    body: JSON.stringify({ content, role: "user" }),
  });
}

export async function clearChat(): Promise<ChatSendResponse> {
  return request<ChatSendResponse>("/chat/clear", { method: "POST" });
}