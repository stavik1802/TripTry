import React, { useState, useEffect, useRef } from "react";

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

const API_BASE = resolveApiBase();

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

function Button({ children, onClick, type, disabled, className }: { 
  children: React.ReactNode; 
  onClick?: () => void; 
  type?: "button" | "submit"; 
  disabled?: boolean;
  className?: string;
}): JSX.Element {
  const baseCls = "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium shadow focus:outline-none focus:ring-2 disabled:opacity-50";
  const defaultCls = "bg-indigo-600 text-white hover:bg-indigo-700 focus:ring-indigo-100";
  const cls = `${baseCls} ${className || defaultCls}`;
  return <button type={type || "button"} onClick={onClick} disabled={!!disabled} className={cls}>{children}</button>;
}

// --------------------------------- Types ---------------------------------
interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: number;
  sessionId?: string;
}

interface Session {
  id: string;
  name: string;
  messages: Message[];
  createdAt: number;
  lastActivity: number;
  userId: string;
}

interface ApiResult {
  status?: string;
  response?: {
    response_text?: string;
    [k: string]: unknown;
  };
  session_id?: string;
  [k: string]: unknown;
}

// -------------------------------- Multi-Session Chat App --------------------------------
export default function MultiSessionApp(): JSX.Element {
  const [sessions, setSessions] = useLocalStorage<Session[]>('trip-ui:sessions', []);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [userId, setUserId] = useState<string>('stav');
  const [inputMessage, setInputMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [showInfoBar, setShowInfoBar] = useState<boolean>(true);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessions]);

  // Get active session
  const activeSession = sessions.find(s => s.id === activeSessionId);

  // Create new session
  const createNewSession = () => {
    const sessionId = `session_${Date.now()}`;
    const newSession: Session = {
      id: sessionId,
      name: `New Chat`,
      messages: [],
      createdAt: Date.now(),
      lastActivity: Date.now(),
      userId: userId
    };
    
    setSessions(prev => [...prev, newSession]);
    setActiveSessionId(sessionId);
    setError('');
  };

  // Delete session
  const deleteSession = (sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    if (activeSessionId === sessionId) {
      const remaining = sessions.filter(s => s.id !== sessionId);
      setActiveSessionId(remaining.length > 0 ? remaining[0].id : '');
    }
  };

  // Rename session
  const renameSession = (sessionId: string, newName: string) => {
    setSessions(prev => prev.map(s => 
      s.id === sessionId ? { ...s, name: newName, lastActivity: Date.now() } : s
    ));
  };

  // Send message
  const sendMessage = async () => {
    if (!inputMessage.trim() || !activeSession || loading) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: inputMessage.trim(),
      timestamp: Date.now(),
      sessionId: activeSession.id
    };

    // Update session name to first question if this is the first message
    const isFirstMessage = activeSession.messages.length === 0;
    const sessionName = isFirstMessage 
      ? (inputMessage.trim().length > 50 
          ? inputMessage.trim().substring(0, 47) + '...' 
          : inputMessage.trim())
      : activeSession.name;

    // Add user message to session
    setSessions(prev => prev.map(s => 
      s.id === activeSession.id 
        ? { 
            ...s, 
            messages: [...s.messages, userMessage], 
            lastActivity: Date.now(),
            name: sessionName
          }
        : s
    ));

    setInputMessage('');
    setLoading(true);
    setError('');

    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    controllerRef.current = new AbortController();

    try {
      const res = await fetch(`${API_BASE}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_request: inputMessage.trim(),
          user_id: userId,
          session_id: activeSession.id
        }),
        signal: controllerRef.current.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const data: ApiResult = await res.json();
      
      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        type: 'assistant',
        content: data.response?.response?.response_text || data.response?.response_text || 'No response received',
        timestamp: Date.now(),
        sessionId: activeSession.id
      };

      // Add assistant message to session
      setSessions(prev => prev.map(s => 
        s.id === activeSession.id 
          ? { ...s, messages: [...s.messages, assistantMessage], lastActivity: Date.now() }
          : s
      ));

    } catch (err: unknown) {
      const message = (err && (err as any).message) || String(err);
      setError(message);
      
      const errorMessage: Message = {
        id: `msg_${Date.now()}_error`,
        type: 'assistant',
        content: `Error: ${message}`,
        timestamp: Date.now(),
        sessionId: activeSession.id
      };

      setSessions(prev => prev.map(s => 
        s.id === activeSession.id 
          ? { ...s, messages: [...s.messages, errorMessage], lastActivity: Date.now() }
          : s
      ));
    } finally {
      setLoading(false);
    }
  };

  // Handle Enter key
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // --------------------------- Export helpers ---------------------------
  async function exportLatest(format: 'json' | 'md' | 'html' | 'pdf') {
    try {
      if (!activeSession) throw new Error('No active session');
      const url = `${API_BASE}/trip/export?session_id=${encodeURIComponent(activeSession.id)}&fmt=${encodeURIComponent(format)}`;
      const res = await fetch(url);
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Export failed: HTTP ${res.status}${text ? ` - ${text}` : ''}`);
      }
      const blob = await res.blob();
      const ext = format === 'md' ? 'md' : format;
      const filename = `trip_${activeSession.id}_last.${ext}`;
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  }

  // Auto-create first session if none exist
  useEffect(() => {
    if (sessions.length === 0) {
      createNewSession();
    } else if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    }
  }, []);

  return (
    <div className="h-screen bg-gradient-to-b from-indigo-50 via-slate-50 to-slate-100 flex">
      {/* Sidebar - Session List (left) */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-800 mb-4">Travel Assistant Chat</h1>
          <div className="space-y-2">
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="User ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            <Button 
              onClick={createNewSession}
              className="w-full bg-green-600 text-white hover:bg-green-700"
            >
              + New Chat
            </Button>
          </div>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`p-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 group ${
                activeSessionId === session.id ? 'bg-indigo-50 border-indigo-200' : ''
              }`}
              onClick={() => setActiveSessionId(session.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <input
                    type="text"
                    value={session.name}
                    onChange={(e) => renameSession(session.id, e.target.value)}
                    className="w-full text-sm font-medium text-gray-800 bg-transparent border-none outline-none focus:bg-white focus:border focus:border-indigo-300 rounded px-1 py-0.5"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    {session.messages.length} messages • {new Date(session.lastActivity).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(session.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 p-1"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content: Chat (left) + Info Panel (right) */}
      <div className="flex-1 flex">
        {/* Chat Column */}
        <div className="flex-1 flex flex-col">
        {activeSession ? (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b border-gray-200 bg-white">
              <h2 className="text-lg font-semibold text-gray-800">{activeSession.name}</h2>
              <div className="text-sm text-gray-500">
                Session ID: {activeSession.id}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => exportLatest('json')} className="bg-gray-700 text-white hover:bg-gray-800">Export JSON</Button>
                <Button onClick={() => exportLatest('md')} className="bg-gray-600 text-white hover:bg-gray-700">Export MD</Button>
                <Button onClick={() => exportLatest('html')} className="bg-gray-500 text-white hover:bg-gray-600">Export HTML</Button>
                <Button onClick={() => exportLatest('pdf')} className="bg-gray-400 text-white hover:bg-gray-500">Export PDF (latest)</Button>
                <Button onClick={async () => {
                  try {
                    if (!activeSession) throw new Error('No active session');
                    const url = `${API_BASE}/trip/export?session_id=${encodeURIComponent(activeSession.id)}&fmt=pdf&all_responses=true`;
                    const res = await fetch(url);
                    if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
                    const blob = await res.blob();
                    const href = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = href;
                    a.download = `trip_${activeSession.id}_all_responses.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(href);
                  } catch (e: any) { setError(e?.message || String(e)); }
                }} className="bg-gray-400 text-white hover:bg-gray-500">Export PDF (all)</Button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {activeSession.messages.map(message => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-3xl px-4 py-2 rounded-2xl ${
                      message.type === 'user'
                        ? 'bg-indigo-600 text-white'
                        : message.content.startsWith('Error:')
                        ? 'bg-red-100 text-red-800'
                        : 'bg-white border border-gray-200 text-gray-800'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    <div className={`text-xs mt-1 ${
                      message.type === 'user' ? 'text-indigo-100' : 'text-gray-500'
                    }`}>
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-2 flex items-center gap-2">
                    <Spinner />
                    <span className="text-gray-600">Thinking...</span>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-gray-200 bg-white">
              {error && (
                <div className="text-red-600 text-sm mb-2">{error}</div>
              )}
              <div className="flex gap-2">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask about your trip planning..."
                  ref={inputRef}
                  className="flex-1 min-h-[60px] max-h-32 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-100 resize-none"
                  disabled={loading}
                />
                <Button 
                  onClick={sendMessage}
                  disabled={loading || !inputMessage.trim()}
                  className="self-end"
                >
                  {loading ? <Spinner /> : 'Send'}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <h3 className="text-lg font-medium mb-2">No active session</h3>
              <p>Create a new chat to get started!</p>
            </div>
          </div>
        )}
        </div>

        {/* Info Panel (right) */}
        <div className="w-96 border-l border-gray-200 bg-white flex flex-col">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <div className="font-semibold text-gray-800">About this assistant</div>
            <button
              className="text-xs text-indigo-700 hover:underline"
              onClick={() => setShowInfoBar(v => !v)}
            >
              {showInfoBar ? 'Hide' : 'Show'}
            </button>
          </div>
          {showInfoBar && (
            <div className="p-4 overflow-y-auto">
              <p className="text-sm text-gray-700">
                Your AI travel companion for general trip advice and planning. It can:
              </p>
              <ul className="list-disc ml-5 mt-2 text-sm text-gray-700 space-y-1">
                <li>Recommend cities and best times to visit</li>
                <li>Suggest restaurants and points of interest</li>
                <li>Build and optimize day-by-day itineraries</li>
                <li>Estimate intercity fares and trip budgets</li>
                <li>Export plans to JSON/Markdown/HTML/PDF</li>
              </ul>
              <div className="mt-4 text-xs font-medium text-gray-600">Sample questions</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  'Recommend 3 cities for a 4-day trip from Chicago in November',
                  'Find top 5 budget-friendly restaurants in Rome near Trevi Fountain',
                  'Create a 3-day Lisbon itinerary focused on museums and history',
                  'Estimate cost to travel from Paris to Amsterdam by train',
                  'Suggest family-friendly POIs in Tokyo within 2km of Shinjuku',
                  'Plan a weekend foodie tour in Mexico City under $400'
                ].map((q) => (
                  <button
                    key={q}
                    className="text-xs bg-gray-50 border border-gray-300 rounded-full px-3 py-1 hover:bg-gray-100"
                    onClick={() => {
                      setInputMessage(q);
                      setActiveSessionId(prev => prev || (sessions[0]?.id || ''));
                      setTimeout(() => inputRef.current?.focus(), 0);
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

