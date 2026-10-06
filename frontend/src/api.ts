import type { Catalog, DeploymentRequest, DoctorResponse, JobEvent, JobSnapshot, PlanResolution, ReportResponse, SessionResponse } from './types';

export class ApiError extends Error {
  constructor(public code: string, message: string, public remediation: string) {
    super(message);
  }
}

export class D1EnvApi {
  private csrfToken: string | null = null;
  private initialization: Promise<SessionResponse> | null = null;

  initialize(): Promise<SessionResponse> {
    if (this.initialization) return this.initialization;
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const bootstrap = fragment.get('bootstrap');
    // Remove the credential before starting any asynchronous work or rendering views.
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
    this.initialization = (bootstrap
      ? this.request<SessionResponse>('/api/session/bootstrap', { token: bootstrap }, false)
      : this.request<SessionResponse>('/api/session'))
      .then((session) => {
        this.csrfToken = session.csrf_token;
        return session;
      });
    return this.initialization;
  }

  private async request<T>(path: string, body?: unknown, csrf = true): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      if (csrf) {
        if (!this.csrfToken) throw new ApiError('SESSION_REQUIRED', '本地会话尚未建立', '请从 D1Env 启动入口重新打开向导');
        headers['X-CSRF-Token'] = this.csrfToken;
      }
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, {
        method: body === undefined ? 'GET' : 'POST',
        credentials: 'same-origin', headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok) {
        const raw: unknown = await response.json().catch(() => null);
        const detail = raw && typeof raw === 'object' && 'detail' in raw ? raw.detail : null;
        const info = detail && typeof detail === 'object' ? detail as Record<string, unknown> : {};
        throw new ApiError(
          typeof info.code === 'string' ? info.code : typeof detail === 'string' && /^[A-Z][A-Z0-9_]{0,80}$/.test(detail) ? detail : `HTTP_${response.status}`,
          typeof info.message === 'string' ? info.message : '本地服务拒绝了请求',
          typeof info.remediation === 'string' ? info.remediation : '检查本地服务与会话状态，再从启动入口重新打开向导',
        );
      }
      return await response.json() as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError('LOCAL_API_UNREACHABLE', '未收到本地服务的有效响应', '确认 D1Env 本地服务仍在运行，然后重试；不会自动执行部署');
    } finally {
      window.clearTimeout(timeout);
    }
  }

  catalog() { return this.request<Catalog>('/api/catalog'); }
  doctor(request: DeploymentRequest) { return this.request<DoctorResponse>('/api/doctor', request); }
  preview(request: DeploymentRequest) { return this.request<PlanResolution>('/api/plans', request); }
  start(planId: string, key: string) { return this.request<JobSnapshot>('/api/jobs', { plan_id: planId, idempotency_key: key }); }
  job(id: string) { return this.request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}`); }
  events(id: string) { return this.request<JobEvent[]>(`/api/jobs/${encodeURIComponent(id)}/events`); }
  cancel(id: string) { return this.request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {}); }
  report(id: string, maskIdentifiers = true) { return this.request<ReportResponse>('/api/reports', { job_id: id, mask_identifiers: maskIdentifiers }); }
}
