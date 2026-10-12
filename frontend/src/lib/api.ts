import { User, Journal } from '../types';

// Storing auth token in localStorage.
// Security note: Acknowledged XSS tradeoff for this project environment.
const TOKEN_KEY = 'publishaid_auth_token';

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

export interface AuthResponse {
  accessToken: string;
  tokenType: string;
  user: User;
}

export interface RegisterPayload {
  fullName: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface BrowseJournalsParams {
  search?: string;
  category?: string;
  quartile?: string;
  publisher?: string;
  openAccessType?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

export interface BrowseJournalsResponse {
  items: Journal[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
  categories: string[];
  publishers: string[];
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Ignore storage errors (e.g. private browsing restrictions)
  }
}

export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore storage errors
  }
}

async function parseErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && data.detail) {
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map((err: any) => err.msg || JSON.stringify(err)).join(', ');
      }
      return JSON.stringify(data.detail);
    }
  } catch {
    // Response was not JSON
  }
  return `Request failed with status ${res.status} (${res.statusText || 'Error'})`;
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  isProtected = false
): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401 && isProtected) {
      clearStoredToken();
    }
    const message = await parseErrorMessage(response);
    throw new Error(message);
  }

  return response.json();
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (res.accessToken) {
    setStoredToken(res.accessToken);
  }
  return res;
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (res.accessToken) {
    setStoredToken(res.accessToken);
  }
  return res;
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me', { method: 'GET' }, true);
}

export async function browseJournals(params: BrowseJournalsParams = {}): Promise<BrowseJournalsResponse> {
  const query = new URLSearchParams();
  if (params.search && params.search.trim()) query.set('search', params.search.trim());
  if (params.category && params.category !== 'all') query.set('category', params.category);
  if (params.quartile && params.quartile !== 'all') query.set('quartile', params.quartile);
  if (params.publisher && params.publisher !== 'all') query.set('publisher', params.publisher);
  if (params.openAccessType && params.openAccessType !== 'all') query.set('open_access_type', params.openAccessType);
  if (params.sortBy) query.set('sort_by', params.sortBy);
  if (params.sortOrder) query.set('sort_order', params.sortOrder);
  if (params.page) query.set('page', String(params.page));
  if (params.limit) query.set('limit', String(params.limit));

  const qs = query.toString();
  const endpoint = `/journals/browse${qs ? `?${qs}` : ''}`;
  return apiRequest<BrowseJournalsResponse>(endpoint, { method: 'GET' }, true);
}

export async function getJournalById(journalId: string | number): Promise<Journal> {
  return apiRequest<Journal>(`/journals/${journalId}`, { method: 'GET' }, true);
}
