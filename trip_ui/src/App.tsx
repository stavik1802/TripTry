import React, { useState, useEffect, useRef } from "react";

/**
 * TripPlanner UI — self‑contained TSX file
 *
 * Fix: define missing `useLocalStorage` hook and other helpers (API_BASE resolver,
 * Spinner, Button, types, extractInnerResponse). Removed optional chaining and
 * import.meta to avoid parser issues.
 *
 * Behavior: posts `{ user_request, user_id }` to `${API_BASE}/process` and
 * renders ONLY the `response_text` from your backend payload.
 */

// ----------------- Minimal cross‑env declarations for TS -----------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const process: any | undefined;
declare global {
  interface Window {
    __API_BASE__?: string;
    __TRIP_UI_SELFTEST__?: boolean;
  }
}

// --------------------------- API base resolver ---------------------------
function normalizeBase(x: string | undefined | null): string | undefined {
  if (!x) return undefined;
  return String(x).replace(/\/$/, "");
}

function resolveApiBase(): string {
  let fromEnv: string | undefined;
  try {
    if (typeof process !== "undefined" && process && process.env) {
      fromEnv = process.env.VITE_API_BASE
        || process.env.REACT_APP_API_BASE
        || process.env.NEXT_PUBLIC_API_BASE;
    }
  } catch (_) { /* ignore */ }

  let fromWindow: string | undefined;
  try {
    if (typeof window !== "undefined" && window.__API_BASE__) {
      fromWindow = window.__API_BASE__;
    }
  } catch (_) { /* ignore */ }

  return normalizeBase(fromEnv) || normalizeBase(fromWindow) || "http://localhost:8000";
}

export function _resolveApiBaseForTest(
  viteLikeEnvVal: string | null,
  windowVal: string | null,
  nodeEnvVal: string | null,
): string {
  return normalizeBase(nodeEnvVal)
      || normalizeBase(viteLikeEnvVal)
      || normalizeBase(windowVal)
      || "http://localhost:8000";
}

const API_BASE = resolveApiBase();

// ----------------------------- Self‑tests -----------------------------
try {
  if (typeof window !== "undefined" && !window.__TRIP_UI_SELFTEST__) {
    window.__TRIP_UI_SELFTEST__ = true;
    const a = _resolveApiBaseForTest("http://a/", null, null); console.assert(a === "http://a");
    const b = _resolveApiBaseForTest(null, "http://b/", null); console.assert(b === "http://b");
    const c = _resolveApiBaseForTest(null, null, null); console.assert(c === "http://localhost:8000");
    const d = _resolveApiBaseForTest(null, null, "http://env/"); console.assert(d === "http://env");
  }
} catch (_) { /* ignore */ }

// --------------------------- Local storage hook ---------------------------
function useLocalStorage<T>(key: string, initialValue: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = typeof localStorage !== "undefined" ? localStorage.getItem(key) : null;
      return raw ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      return initialValue as T;
    }
  });
  useEffect(() => {
    try {
      if (typeof localStorage !== "undefined") {
        localStorage.setItem(key, JSON.stringify(value));
      }
    } catch {
      /* ignore */
    }
  }, [key, value]);
  return [value, setValue];
}

// ------------------------------- UI helpers -------------------------------
function Spinner(): JSX.Element {
  return <div className="animate-spin h-5 w-5 rounded-full border-2 border-gray-300 border-t-transparent" />;
}

function Button({ children, onClick, type, disabled }: { children: React.ReactNode; onClick?: () => void; type?: "button" | "submit"; disabled?: boolean; }): JSX.Element {
  const cls = "inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2 text-sm font-medium shadow bg-indigo-600 text-white hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-100 disabled:opacity-50";
  return <button type={type || "button"} onClick={onClick} disabled={!!disabled} className={cls}>{children}</button>;
}

// --------------------------------- Types ---------------------------------
interface Summary {
  cities?: string[];
  duration?: number;
  budget?: number;
  currency?: string;
  has_itinerary?: boolean;
  has_pois?: boolean;
  has_restaurants?: boolean;
  has_transportation?: boolean;
}

interface InnerResponse {
  status?: string;
  tier?: string;
  response_text?: string;
  summary?: Summary;
  [k: string]: unknown;
}

interface ApiResult {
  status?: string;
  response?: InnerResponse | { response?: InnerResponse };
  session_id?: string;
  agents_used?: string[];
  [k: string]: unknown;
}

function extractInnerResponse(result: ApiResult | null | undefined): InnerResponse | undefined {
  if (!result) return undefined;
  const r1 = (result as any).response;
  if (r1 && typeof r1 === "object" && (r1 as any).response) {
    return (r1 as any).response as InnerResponse;
  }
  if (r1 && typeof r1 === "object") {
    return r1 as InnerResponse;
  }
  return result as unknown as InnerResponse;
}

// --------------- Non‑fatal tests for response extraction ---------------
try {
  const sampleA: ApiResult = { status: "success", response: { response_text: "hi" } };
  console.assert((extractInnerResponse(sampleA) || {}).response_text === "hi", "extract A fail");
  const sampleB: ApiResult = { status: "success", response: { response: { response_text: "nested" } } } as any;
  console.assert((extractInnerResponse(sampleB) || {}).response_text === "nested", "extract B fail");
} catch (_) { /* ignore */ }

// -------------------------------- App --------------------------------
export default function App(): JSX.Element {
  const [query, setQuery] = useState<string>("Plan a 4-day NYC food trip for 2 adults next month. Include two dinner picks per day.");
  const [userId, setUserId] = useState<string>("stav");
  const [isNewSession, setIsNewSession] = useState<boolean>(true);
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<ApiResult | null>(null);
  const [history, setHistory] = useLocalStorage<Array<{ ts: number; query: string; ok: boolean; sessionId?: string }>>("trip-ui:history", []);

  const controllerRef = useRef<AbortController | null>(null);

  async function handleSubmit(e?: React.FormEvent<HTMLFormElement> | React.MouseEvent<HTMLButtonElement>): Promise<void> {
    if (e && (e as React.FormEvent<HTMLFormElement>).preventDefault) (e as React.FormEvent<HTMLFormElement>).preventDefault();
    setLoading(true); setError(""); setResult(null);
    if (controllerRef.current && controllerRef.current.abort) controllerRef.current.abort();
    controllerRef.current = new AbortController();
    try {
      const res = await fetch(`${API_BASE}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          user_request: query, 
          user_id: userId || undefined,
          session_id: sessionId || undefined 
        }),
        signal: controllerRef.current.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ApiResult = await res.json();
      setResult(data);
      
      // Update session ID if we got one back
      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
        setIsNewSession(false);
      }
      
      setHistory(([...history, { ts: Date.now(), query, ok: true, sessionId: data.session_id }]).slice(-12));
    } catch (err: unknown) {
      const message = (err && (err as any).message) || String(err);
      setError(message);
      setHistory(([...history, { ts: Date.now(), query, ok: false }]).slice(-12));
    } finally {
      setLoading(false);
    }
  }

  const r = extractInnerResponse(result);

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50 via-slate-50 to-slate-100">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">TripPlanner — Multi‑Agent Demo</h1>
        <form onSubmit={handleSubmit} className="mb-4">
          <textarea
            className="w-full min-h-[120px] rounded-2xl border border-slate-300 bg-white p-3 shadow-sm focus:outline-none focus:ring-4 focus:ring-indigo-100"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex gap-2 mt-2">
            <input
              className="flex-1 rounded-2xl border border-slate-300 bg-white px-3 py-2 shadow-sm focus:outline-none focus:ring-4 focus:ring-indigo-100"
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value);
                if (e.target.value !== userId) {
                  setIsNewSession(true);
                  setSessionId("");
                }
              }}
              placeholder="User ID (e.g., stav)"
            />
            <input
              className="flex-1 rounded-2xl border border-slate-300 bg-white px-3 py-2 shadow-sm focus:outline-none focus:ring-4 focus:ring-indigo-100"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="Session ID (for follow-ups)"
            />
            <Button 
              type="submit" 
              disabled={loading || !query.trim()}
              onClick={() => setIsNewSession(false)}
            >
              {loading ? <Spinner /> : "Run"}
            </Button>
            <Button 
              type="button" 
              onClick={() => {
                setSessionId("");
                setIsNewSession(true);
                setResult(null);
                setError("");
              }}
              disabled={loading}
              className="bg-green-600 text-white hover:bg-green-700"
            >
              New Session
            </Button>
          </div>
        </form>

        {error ? (
          <div className="text-rose-600 font-mono text-sm mb-4">{error}</div>
        ) : null}

        {/* Session Info */}
        {sessionId ? (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-3 mb-4">
            <div className="text-sm text-blue-800">
              <strong>Session ID:</strong> {sessionId}
              <br />
              <strong>User ID:</strong> {userId}
              <br />
              <strong>Status:</strong> {isNewSession ? "New conversation" : "Active conversation - you can ask follow-up questions!"}
            </div>
          </div>
        ) : (
          <div className="bg-gray-50 border border-gray-200 rounded-2xl p-3 mb-4">
            <div className="text-sm text-gray-700">
              <strong>User ID:</strong> {userId}
              <br />
              <strong>Status:</strong> Ready to start a new conversation
            </div>
          </div>
        )}

        {/* Follow-up Examples */}
        {result && !loading ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4 mb-4">
            <div className="text-sm text-yellow-800 mb-2">
              <strong>Try these follow-up questions:</strong>
            </div>
            <div className="space-y-1 text-xs">
              <button 
                className="block text-left text-blue-600 hover:text-blue-800 underline"
                onClick={() => setQuery("Can you add more restaurant recommendations?")}
              >
                • Can you add more restaurant recommendations?
              </button>
              <button 
                className="block text-left text-blue-600 hover:text-blue-800 underline"
                onClick={() => setQuery("What about the budget breakdown?")}
              >
                • What about the budget breakdown?
              </button>
              <button 
                className="block text-left text-blue-600 hover:text-blue-800 underline"
                onClick={() => setQuery("Show me transportation options between cities")}
              >
                • Show me transportation options between cities
              </button>
            </div>
          </div>
        ) : null}

        {/* Show only the response_text */}
        {r && r.response_text ? (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 whitespace-pre-wrap text-slate-800 leading-relaxed">
            {r.response_text}
          </div>
        ) : null}
      </div>
    </div>
  );
}
