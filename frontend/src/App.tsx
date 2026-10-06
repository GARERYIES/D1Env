import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, D1EnvApi } from './api';
import { EvidencePanel } from './components/EvidencePanel';
import { HostPage } from './components/HostPage';
import { ModePage } from './components/ModePage';
import { PreviewPage } from './components/PreviewPage';
import { ResultsPage, terminalStates } from './components/ResultsPage';
import { RobotPage } from './components/RobotPage';
import { WizardSteps } from './components/WizardSteps';
import type { Catalog, DemoScenario, DeploymentRequest, DoctorResponse, JobEvent, JobSnapshot, PlanResolution, ReportResponse } from './types';

interface Failure { phase: string; error: ApiError }

export default function App() {
  const api = useMemo(() => new D1EnvApi(), []);
  const [ready, setReady] = useState(false);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [step, setStep] = useState(0);
  const [profileId, setProfileId] = useState('demo');
  const [scenario, setScenario] = useState<DemoScenario>('success');
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [doctorPending, setDoctorPending] = useState(false);
  const [resolution, setResolution] = useState<PlanResolution | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [maskIdentifiers, setMaskIdentifiers] = useState(true);
  const [reportMasked, setReportMasked] = useState(true);
  const [actionPending, setActionPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const actionLock = useRef(false);
  const idempotencyKey = useRef<string | null>(null);
  const doctorLock = useRef(false);
  const previewLock = useRef(false);
  const currentJobId = useRef<string | null>(null);
  const requestGeneration = useRef(0);

  const request: DeploymentRequest = { mode: 'mock', profile_id: profileId, target_id: 'local', task: 'demo', demo_scenario: scenario };
  const showError = (phase: string, error: unknown) => setFailure({ phase, error: error instanceof ApiError ? error : new ApiError('UI_REQUEST_FAILED', '未完成本次请求', '查看本地服务状态，再重试当前步骤') });

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        await api.initialize();
        const receivedCatalog = await api.catalog();
        if (!live) return;
        setCatalog(receivedCatalog);
        setReady(true);
        const savedId = localStorage.getItem('d1env.currentJob');
        if (savedId) {
          const [restored, restoredEvents] = await Promise.all([api.job(savedId), api.events(savedId)]);
          if (!live) return;
          currentJobId.current = restored.job_id;
          setJob(restored);
          setEvents(restoredEvents);
          if (restored.error_code === 'MOCK_READINESS_FAILED') setScenario('verify_failure');
          setStep(4);
        }
      } catch (error) {
        if (live) showError('本地会话 / 作业恢复', error);
      }
    })();
    return () => { live = false; };
  }, [api]);

  async function inspectDoctor() {
    if (doctorLock.current || !ready) return;
    doctorLock.current = true;
    setDoctorPending(true);
    setFailure(null);
    try { setDoctor(await api.doctor(request)); }
    catch (error) { showError('执行电脑只读检测', error); }
    finally { doctorLock.current = false; setDoctorPending(false); }
  }

  async function previewPlan() {
    if (previewLock.current || !ready) return null;
    previewLock.current = true;
    setPreviewPending(true);
    setFailure(null);
    const generation = requestGeneration.current;
    try {
      const result = await api.preview(request);
      if (generation !== requestGeneration.current) return null;
      setResolution(result);
      return result;
    } catch (error) { showError('部署预览', error); return null; }
    finally { previewLock.current = false; setPreviewPending(false); }
  }

  useEffect(() => {
    if (ready && step === 2 && !doctor && !doctorPending && !failure) void inspectDoctor();
    if (ready && step === 3 && !resolution && !previewPending && !failure) void previewPlan();
  }, [ready, step, doctor, doctorPending, resolution, previewPending, failure]);

  useEffect(() => {
    if (!job || !ready) return;
    const id = job.job_id;
    let stopped = false;
    let polling = false;
    let interval: number | undefined;
    async function poll() {
      if (polling || stopped) return;
      polling = true;
      try {
        const [latest, latestEvents] = await Promise.all([api.job(id), api.events(id)]);
        if (stopped || currentJobId.current !== id) return;
        setJob(latest);
        setEvents(latestEvents);
        if (terminalStates.has(latest.state) && interval !== undefined) window.clearInterval(interval);
      } catch (error) {
        if (!stopped && currentJobId.current === id) showError('作业状态读取', error);
      } finally { polling = false; }
    }
    interval = window.setInterval(() => void poll(), 400);
    void poll();
    return () => { stopped = true; window.clearInterval(interval); };
  }, [api, job?.job_id, ready]);

  async function startJob(retry = false) {
    if (actionLock.current) return;
    actionLock.current = true;
    setActionPending(true);
    setFailure(null);
    try {
      let planId: string;
      if (retry && job) {
        if (job.mode !== 'mock' || job.verified_scope !== 'mock') {
          throw new ApiError('JOB_SCOPE_MISMATCH', '原始作业不属于 MOCK 演示范围', '导出诊断报告并复核原始作业，不执行范围不明的计划');
        }
        // The backend revalidates the immutable request saved with this plan.
        planId = job.plan_id;
        idempotencyKey.current = null;
      } else {
        const resolved = !resolution ? await previewPlan() : resolution;
        const plan = resolved?.plan;
        if (!plan || resolved?.blockers.length || plan.mode !== 'mock' || plan.verified_scope !== 'mock') {
          setStep(3);
          return;
        }
        planId = plan.plan_id;
      }
      idempotencyKey.current ??= crypto.randomUUID();
      const started = await api.start(planId, idempotencyKey.current);
      currentJobId.current = started.job_id;
      localStorage.setItem('d1env.currentJob', started.job_id);
      setEvents([]);
      setReport(null);
      setJob(started);
      setStep(4);
    } catch (error) { showError('MOCK 演示提交', error); }
    finally { actionLock.current = false; setActionPending(false); }
  }

  async function cancelJob() {
    const id = job?.job_id;
    if (!id || actionLock.current) return;
    actionLock.current = true;
    setActionPending(true);
    setFailure(null);
    try {
      const cancelled = await api.cancel(id);
      if (currentJobId.current === id) setJob(cancelled);
    } catch (error) {
      showError('取消本次 MOCK 演示', error);
    } finally {
      actionLock.current = false;
      setActionPending(false);
    }
  }

  async function generateReport() {
    if (!job || actionLock.current) return;
    actionLock.current = true;
    setActionPending(true);
    setFailure(null);
    try {
      const result = await api.report(job.job_id, maskIdentifiers);
      setReport(result);
      setReportMasked(maskIdentifiers);
    }
    catch (error) { showError('去敏诊断报告', error); }
    finally { actionLock.current = false; setActionPending(false); }
  }

  function selectScenario(next: DemoScenario) {
    requestGeneration.current += 1;
    setScenario(next);
    setResolution(null);
    idempotencyKey.current = null;
    setFailure(null);
  }
  function selectProfile(id: string) {
    if (!catalog?.profiles.some((profile) => profile.profile_id === id && profile.kind === 'mock')) return;
    requestGeneration.current += 1;
    setProfileId(id);
    setDoctor(null);
    setResolution(null);
    idempotencyKey.current = null;
  }
  function newDemo() {
    if (job && !terminalStates.has(job.state)) return;
    requestGeneration.current += 1;
    currentJobId.current = null;
    localStorage.removeItem('d1env.currentJob');
    setJob(null); setEvents([]); setReport(null); setResolution(null); setFailure(null);
    idempotencyKey.current = null;
    setStep(0);
  }

  return <div className="app-shell">
    <header className="app-header"><a className="brand" href="/" aria-label="D1Env 首页"><span className="brand-mark" aria-hidden="true">D1</span><span>D1Env<small>机器人环境工作台</small></span></a><div className="header-right"><span className="local-label"><i /> 本地工作台</span><span className="release-tag">M0–M2 · 软件演示</span></div></header>
    <div className="mock-banner" data-testid="mock-watermark"><span>MOCK · 演示模式</span><p>当前为软件演示，无真实容器部署，未连接机器人。</p><strong>运动权限：未启用</strong></div>
    <div className="workspace-title"><div><span className="eyebrow">D1 ENVIRONMENT / FOUNDATION</span><h2>把每一步，部署得明白。</h2></div><span className="workspace-version">中文向导 <b>01</b></span></div>
    <WizardSteps current={step} onSelect={setStep} disabled={!ready || actionPending} />
    <div className="workspace-grid"><main className="main-panel">
      {!ready && !failure && <div className="loading-state" role="status">正在建立本地会话与读取配置…</div>}
      {failure && <section className="request-error" role="alert"><span className="eyebrow">请求未完成</span><h2>{failure.phase}失败</h2><strong>{failure.error.code}</strong><p>检测证据：{failure.error.message}</p><p>下一步：{failure.error.remediation}</p><small>没有收到有效响应时，界面不会推断部署成功。</small></section>}
      {ready && <>
        {step === 0 && <ModePage scenario={scenario} onScenario={selectScenario} next={() => setStep(1)} />}
        {step === 1 && <RobotPage profiles={catalog?.profiles ?? []} selectedId={profileId} onSelect={selectProfile} next={() => setStep(2)} />}
        {step === 2 && <HostPage result={doctor} pending={doctorPending} next={() => setStep(3)} refresh={() => void inspectDoctor()} />}
        {step === 3 && <PreviewPage resolution={resolution} scenario={scenario} pending={previewPending || actionPending} start={() => void startJob()} />}
        {step === 4 && <ResultsPage job={job} events={events} pending={actionPending} report={report} maskIdentifiers={maskIdentifiers} reportMasked={reportMasked} onMaskIdentifiers={setMaskIdentifiers} cancel={() => void cancelJob()} retry={() => void startJob(true)} newDemo={newDemo} exportReport={() => void generateReport()} />}
      </>}
    </main><EvidencePanel doctor={doctor} job={job} /></div>
    <footer className="app-footer"><span>D1Env / Foundation</span><span>依据可查 · 范围明确 · 默认只读</span><span>MOCK ≠ 真机验证</span></footer>
  </div>;
}
