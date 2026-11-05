/** 后端接口封装：只做 fetch + 错误归一化，不掺业务逻辑。 */

const TOKEN_KEY = 'pm.token';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  suggestions: string[];

  constructor(message: string, status = 0, suggestions: string[] = []) {
    super(message);
    this.status = status;
    this.suggestions = suggestions;
  }
}

type Options = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
};

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? {Authorization: `Bearer ${token}`} : {}),
    },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });

  if (res.status === 401 && token) {
    // 令牌过期：清掉，让界面回到未登录态而不是反复报错
    setToken(null);
    throw new ApiError('登录已失效，请重新登录', 401);
  }

  if (!res.ok) {
    let message = `请求失败（${res.status}）`;
    let suggestions: string[] = [];
    try {
      const data = await res.json();
      const detail = data?.detail;
      if (typeof detail === 'string') message = detail;
      else if (detail?.message) {
        message = detail.message;
        suggestions = detail.suggestions || [];
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        message = detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('；');
      }
    } catch {
      /* 非 JSON 响应，保留默认文案 */
    }
    throw new ApiError(message, res.status, suggestions);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type KnowledgePoint = {
  id: string;
  title: string;
  summary: string;
  aliases: string[];
  actors: string[];
};

export type GenerateResult = {
  props: any;
  meta: {
    source: 'catalog' | 'llm' | 'capture';
    knowledgePoint: string;
    durationSec: number;
    totalFrames: number;
    elapsedMs: number;
    notes: string[];
    animationId?: string;
  };
};

export type AuthUser = {id: number; email: string; role?: string};

export const authApi = {
  register: (email: string, password: string) =>
    api<{token: string; user: AuthUser}>('/api/auth/register', {
      method: 'POST',
      body: {email, password},
    }),
  login: (email: string, password: string) =>
    api<{token: string; user: AuthUser}>('/api/auth/login', {
      method: 'POST',
      body: {email, password},
    }),
  me: () => api<AuthUser>('/api/auth/me'),
};

export const motionApi = {
  catalog: () => api<KnowledgePoint[]>('/api/knowledge-points'),
  generate: (payload: {topic?: string; prompt?: string; durationSec: number}) =>
    api<GenerateResult>('/api/generate', {method: 'POST', body: payload}),
  settings: () =>
    api<{
      baseUrl: string;
      model: string;
      hasKey: boolean;
      maskedKey: string;
      defaults: {baseUrl: string; model: string};
    }>('/api/settings'),
  saveSettings: (body: {baseUrl?: string; model?: string; apiKey?: string}) =>
    api('/api/settings', {method: 'PUT', body}),
  animations: () =>
    api<{id: string; knowledge_point: string; title: string; duration_sec: number; created_at: string}[]>(
      '/api/animations',
    ),
  animation: (id: string) => api<any>(`/api/animations/${id}`),
  remove: (id: string) => api(`/api/animations/${id}`, {method: 'DELETE'}),
  render: (props: unknown) =>
    api<{id: string; status: string; url?: string; error?: string}>('/api/renders', {
      method: 'POST',
      body: {props},
    }),
  renderStatus: (id: string) =>
    api<{id: string; status: string; url?: string; error?: string}>(`/api/renders/${id}`),
};

// ---------------------------------------------------------------- 抓包

export type CapturePacket = {
  index: number;
  ts: number;
  time: string;
  src: string;
  dst: string;
  srcPort: number | null;
  dstPort: number | null;
  proto: string;
  length: number;
  summary: string;
  flags: string;
  payloadLen: number;
  sessionId: string;
  fields: Record<string, string>;
};

export type CaptureSession = {
  id: string;
  proto: string;
  client: string;
  server: string;
  clientPort: number | null;
  serverPort: number | null;
  label: string;
  packetCount: number;
  startTs: number;
  endTs: number;
  durationMs: number;
  packetIndexes: number[];
};

export type CaptureParsed = {
  filename: string;
  size: number;
  packetCount: number;
  sessionCount: number;
  truncated: boolean;
  sessions: CaptureSession[];
  packets: CapturePacket[];
};

/** 上传 pcap：必须走 multipart，不能复用 api()（那里固定了 JSON）。 */
export async function uploadCapture(file: File): Promise<{captureId: string | null; parsed: CaptureParsed}> {
  const token = getToken();
  const form = new FormData();
  form.append('file', file);

  const res = await fetch('/api/captures', {
    method: 'POST',
    headers: token ? {Authorization: `Bearer ${token}`} : undefined,
    body: form,
  });

  if (!res.ok) {
    let message = `上传失败（${res.status}）`;
    try {
      const data = await res.json();
      if (typeof data?.detail === 'string') message = data.detail;
    } catch {
      /* 忽略非 JSON */
    }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as {captureId: string | null; parsed: CaptureParsed};
}

export const captureApi = {
  /** 把选中的会话翻译成动画剧本 */
  animate: (session: CaptureSession, packets: CapturePacket[], durationSec = 12) =>
    api<GenerateResult>('/api/captures/animate', {
      method: 'POST',
      body: {session, packets, durationSec},
    }),
  list: () =>
    api<{id: string; filename: string; packet_count: number; session_count: number; created_at: string}[]>(
      '/api/captures',
    ),
  get: (id: string) => api<{id: string; parsed: CaptureParsed}>(`/api/captures/${id}`),
  remove: (id: string) => api(`/api/captures/${id}`, {method: 'DELETE'}),
};

// ---------------------------------------------------------------- AI 教师

export type ChatTurn = {role: 'user' | 'assistant'; content: string};

export type TutorAskBody = {
  question: string;
  topic?: string;
  /** 当前正在看的剧本：模型据此引用真实 seq/ack，而不是自己编 */
  props?: unknown;
  history?: ChatTurn[];
};

/**
 * 提问并流式接收回答。
 *
 * 用 fetch + ReadableStream 而不是 EventSource：后者只能 GET，
 * 而问题、上下文、历史都要放 body 里。
 */
export async function askTutor(
  body: TutorAskBody,
  onToken: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  const res = await fetch('/api/tutor/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? {Authorization: `Bearer ${token}`} : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let message = `提问失败（${res.status}）`;
    try {
      const data = await res.json();
      if (typeof data?.detail === 'string') message = data.detail;
    } catch {
      /* 非 JSON */
    }
    throw new ApiError(message, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // SSE 用空行分隔事件；一次 read 可能拿到半个事件，所以要留 buffer
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});

    let idx = buffer.indexOf('\n\n');
    while (idx >= 0) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      idx = buffer.indexOf('\n\n');

      const lines = raw.split('\n');
      const event = lines.find((l) => l.startsWith('event:'))?.slice(6).trim() || 'token';
      const data = lines
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).replace(/^ /, ''))
        .join('\n');
      if (!data) continue;
      if (event === 'token') onToken(data + '\n');
      else if (event === 'error') throw new ApiError(data.replace(/^\[ERROR\]\s*/, ''));
    }
  }
}

// ---------------------------------------------------------------- 管理员

export type AdminUser = {
  id: number;
  email: string;
  role: string;
  created_at: string;
  last_login_at: string | null;
  failed_attempts: number;
  locked: string | null;
  has_key: boolean;
};

export const adminApi = {
  users: () => api<AdminUser[]>('/api/admin/users'),
  stats: () => api<{users: number; animations: number; captures: number; backend: string}>('/api/admin/stats'),
  setRole: (id: number, role: string) =>
    api(`/api/admin/users/${id}/role`, {method: 'POST', body: {role}}),
};
