import type {
  AuthResponse,
  User,
  Agent,
  AgentWithKey,
  MetricSnapshot,
  Alert,
  AgentEvent,
  EventFilters,
  PaginatedResponse,
  DashboardOverview,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('bannin_access_token');
}

function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('bannin_refresh_token');
}

function setTokens(access: string, refresh: string): void {
  localStorage.setItem('bannin_access_token', access);
  localStorage.setItem('bannin_refresh_token', refresh);
}

function clearTokens(): void {
  localStorage.removeItem('bannin_access_token');
  localStorage.removeItem('bannin_refresh_token');
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) return refreshPromise;

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const refreshToken = getRefreshToken();
      if (!refreshToken) return false;

      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken }),
      });

      if (!res.ok) return false;

      const json = (await res.json()) as AuthResponse;
      setTokens(json.data.accessToken, json.data.refreshToken);
      return true;
    } catch {
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers: extraHeaders } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && token) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getAccessToken()}`;
      res = await fetch(`${API_URL}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } else {
      clearTokens();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new ApiError(401, 'UNAUTHORIZED', 'Session expired');
    }
  }

  if (!res.ok) {
    let errorBody: { error?: { code?: string; message?: string } } = {};
    try {
      errorBody = await res.json();
    } catch {
      // Response may not be JSON
    }
    throw new ApiError(
      res.status,
      errorBody.error?.code ?? 'UNKNOWN',
      errorBody.error?.message ?? `Request failed with status ${res.status}`,
    );
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

interface RegisterInput {
  username: string;
  displayName: string;
  password: string;
  email?: string;
}

interface LoginInput {
  identifier: string;
  password: string;
}

interface UpdateProfileInput {
  displayName?: string;
  email?: string | null;
}

interface ChangePasswordInput {
  currentPassword: string;
  newPassword: string;
}

interface CreateAgentInput {
  name: string;
}

interface UpdateAgentInput {
  name?: string;
}

export const api = {
  auth: {
    register: (data: RegisterInput) =>
      request<AuthResponse>('/api/auth/register', { method: 'POST', body: data }),
    login: (data: LoginInput) =>
      request<AuthResponse>('/api/auth/login', { method: 'POST', body: data }),
    refresh: () => {
      const refreshToken = getRefreshToken();
      return request<AuthResponse>('/api/auth/refresh', {
        method: 'POST',
        body: { refreshToken },
      });
    },
    me: () => request<{ data: User }>('/api/auth/me'),
    updateProfile: (data: UpdateProfileInput) =>
      request<{ data: User }>('/api/auth/me', { method: 'PATCH', body: data }),
    verify: (token: string) => request<{ data: { message: string } }>(`/api/auth/verify/${encodeURIComponent(token)}`),
    resendVerification: () =>
      request<{ data: { message: string } }>('/api/auth/resend-verification', { method: 'POST' }),
    changePassword: (data: ChangePasswordInput) =>
      request<{ data: { message: string } }>('/api/auth/password', { method: 'PATCH', body: data }),
    deleteAccount: (password: string) =>
      request<{ data: { message: string } }>('/api/auth/me', { method: 'DELETE', body: { password } }),
    forgotPassword: (email: string) =>
      request<{ data: { message: string } }>('/api/auth/forgot-password', { method: 'POST', body: { email } }),
    resetPassword: (token: string, newPassword: string) =>
      request<{ data: { message: string } }>('/api/auth/reset-password', { method: 'POST', body: { token, newPassword } }),
  },
  agents: {
    list: () => request<{ data: Agent[] }>('/api/agents'),
    create: (data: CreateAgentInput) =>
      request<{ data: AgentWithKey }>('/api/agents', { method: 'POST', body: data }),
    get: (id: string) => request<{ data: Agent }>(`/api/agents/${encodeURIComponent(id)}`),
    update: (id: string, data: UpdateAgentInput) =>
      request<{ data: Agent }>(`/api/agents/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: data,
      }),
    delete: (id: string) =>
      request<void>(`/api/agents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    regenerateKey: (id: string) =>
      request<{ data: { apiKey: string } }>(
        `/api/agents/${encodeURIComponent(id)}/regenerate-key`,
        { method: 'POST' },
      ),
    metrics: (id: string) =>
      request<{ data: MetricSnapshot }>(`/api/agents/${encodeURIComponent(id)}/metrics`),
    metricsHistory: (id: string, minutes = 30) =>
      request<{ data: MetricSnapshot[] }>(
        `/api/agents/${encodeURIComponent(id)}/metrics/history?minutes=${minutes}`,
      ),
    alerts: (id: string, page = 1) =>
      request<PaginatedResponse<Alert>>(
        `/api/agents/${encodeURIComponent(id)}/alerts?limit=20&offset=${(page - 1) * 20}`,
      ),
    events: (id: string, params?: EventFilters) => {
      const qs = new URLSearchParams();
      if (params?.type) qs.set('type', params.type);
      if (params?.severity) qs.set('severity', params.severity);
      if (params?.since) qs.set('since', params.since);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      return request<PaginatedResponse<AgentEvent>>(
        `/api/agents/${encodeURIComponent(id)}/events?${qs.toString()}`,
      );
    },
  },
  events: {
    list: (params?: EventFilters) => {
      const qs = new URLSearchParams();
      if (params?.type) qs.set('type', params.type);
      if (params?.severity) qs.set('severity', params.severity);
      if (params?.since) qs.set('since', params.since);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      return request<PaginatedResponse<AgentEvent>>(`/api/events?${qs.toString()}`);
    },
    search: (query: string, limit = 20, offset = 0) =>
      request<PaginatedResponse<AgentEvent>>(
        `/api/events/search?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`,
      ),
    timeline: (params?: EventFilters) => {
      const qs = new URLSearchParams();
      if (params?.type) qs.set('type', params.type);
      if (params?.severity) qs.set('severity', params.severity);
      if (params?.since) qs.set('since', params.since);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      return request<PaginatedResponse<AgentEvent>>(`/api/events/timeline?${qs.toString()}`);
    },
  },
  notifications: {
    subscribePush: (subscription: PushSubscriptionJSON) =>
      request<void>('/api/notifications/push', { method: 'POST', body: subscription }),
    unsubscribePush: (endpoint: string) =>
      request<void>('/api/notifications/push', {
        method: 'DELETE',
        body: { endpoint },
      }),
    test: () => request<void>('/api/notifications/test', { method: 'POST' }),
  },
  dashboard: {
    overview: () => request<{ data: DashboardOverview }>('/api/dashboard/overview'),
  },
} as const;

async function waitForTokenRefresh(): Promise<void> {
  if (isRefreshing && refreshPromise) {
    await refreshPromise;
  }
}

export { ApiError, clearTokens, setTokens, getAccessToken, waitForTokenRefresh, refreshAccessToken };
