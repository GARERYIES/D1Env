import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, D1EnvApi } from './api';
import { EvidencePanel } from './components/EvidencePanel';
import { HostPage } from './components/HostPage';
import { JobHistory } from './components/JobHistory';
import { ModePage } from './components/ModePage';
import { PreviewPage } from './components/PreviewPage';
import { ResultsPage, terminalStates } from './components/ResultsPage';
import { RobotPage } from './components/RobotPage';
import { WizardSteps } from './components/WizardSteps';
import { scopeMatchesMode } from './presentation';
import type { Catalog, DemoScenario, DeploymentPlan, DeploymentRequest, DoctorResponse, ExecutableMode, JobEvent, JobSnapshot, PlanResolution, ProbeScenario, ReportResponse, RosArtifactMetadata } from './types';

interface Failure { phase: string; error: ApiError }

export default function App() {
  const api = useMemo(() => new D1EnvApi(), []);
  const [ready, setReady] = useState(false);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [step, setStep] = useState(0);
  const [mode, setMode] = useState<ExecutableMode>('mock');
  const [profileId, setProfileId] = useState('demo');
  const [scenario, setScenario] = useState<DemoScenario>('success');
  const [probeScenario, setProbeScenario] = useState<ProbeScenario>('success');
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [doctorPending, setDoctorPending] = useState(false);
  const [artifact, setArtifact] = useState<RosArtifactMetadata | null>(null);
  const [importPending, setImportPending] = useState(false);
  const [imageImported, setImageImported] = useState(false);
  const [preparePending, setPreparePending] = useState(false);
  const [resolution, setResolution] = useState<PlanResolution | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [maskIdentifiers, setMaskIdentifiers] = useState(true);
  const [reportMasked, setReportMasked] = useState(true);
  const [actionPending, setActionPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyPending, setHistoryPending] = useState(false);
  const [historyJobs, setHistoryJobs] = useState<JobSnapshot[]>([]);
  const historyLock = useRef(false);
  const actionLock = useRef(false);
  const idempotencyKey = useRef<string | null>(null);
  const doctorLock = useRef(false);
  const previewLock = useRef(false);
  const currentJobId = useRef<string | null>(null);
  const requestGeneration = useRef(0);
  const jobMutationVersion = useRef(0);
  const currentSnapshot = useRef<JobSnapshot | null>(null);
  const softwareHealthObservedAt = useRef<number | null>(null);

  const request: DeploymentRequest = { mode, profile_id: profileId, target_id: 'local', task: mode === 'software_test' ? 'ros_probe' : 'demo', demo_scenario: mode === 'mock' ? scenario : 'success', probe_scenario: mode === 'software_test' ? probeScenario : 'success' };
  const locked = !!job && (!terminalStates.has(job.state) || (job.mode === 'software_test' && job.state === 'SUCCEEDED'));
  const showError = (phase: string, error: unknown) => setFailure({ phase, error: error instanceof ApiError ? error : new ApiError('UI_REQUEST_FAILED', '未完成本次请求', '查看本地服务状态，再重试当前步骤') });

  function recordSnapshot(snapshot: JobSnapshot) {
    currentSnapshot.current = snapshot;
    softwareHealthObservedAt.current = snapshot.mode === 'software_test' && snapshot.state === 'SUCCEEDED' && snapshot.current_software_ready === true ? Date.now() : null;
    setJob(snapshot);
  }

  function invalidateSoftwareHealth(id: string, code: string, cause?: unknown) {
    const current = currentSnapshot.current;
    if (currentJobId.current !== id || !current || current.mode !== 'software_test' || current.state !== 'SUCCEEDED') return;
    recordSnapshot({ ...current, current_software_ready: null, current_health_evidence: {
      status: 'UNKNOWN', code, message: code === 'CURRENT_HEALTH_EXPIRED' ? '超过五秒未取得新的当前软件健康证据，请等待下一次只读复核。' : '本次软件健康读取未完成，历史成功不代表当前通信正常。',
      ...(cause instanceof ApiError ? { cause_code: cause.code } : {}),
    } });
  }

  function applyRestoredJob(restored: JobSnapshot, savedPlan: DeploymentPlan, restoredEvents: JobEvent[]) {
    if (!scopeMatchesMode(restored.mode, restored.verified_scope) || !scopeMatchesMode(savedPlan.mode, savedPlan.verified_scope) || savedPlan.plan_id !== restored.plan_id || savedPlan.mode !== restored.mode || savedPlan.request.mode !== restored.mode || savedPlan.request.profile_id !== savedPlan.profile_id) {
      throw new ApiError('JOB_SCOPE_MISMATCH', '保存的作业与原始计划范围不一致', '导出诊断报告并复核原始作业，不按默认演示配置重建任务');
    }
    requestGeneration.current += 1;
    jobMutationVersion.current += 1;
    currentJobId.current = restored.job_id;
    recordSnapshot(restored);
    localStorage.setItem('d1env.currentJob', restored.job_id);
    setMode(restored.mode as ExecutableMode); setProfileId(savedPlan.request.profile_id);
    setScenario(savedPlan.request.demo_scenario ?? 'success'); setProbeScenario(savedPlan.request.probe_scenario ?? 'success');
    setResolution({ plan: savedPlan, blockers: [] }); setEvents(restoredEvents);
    setDoctor(null); setReport(null); setFailure(null); setStep(4);
    idempotencyKey.current = null;
  }

  async function loadHistory() {
    if (!ready || historyLock.current || actionLock.current) return;
    historyLock.current = true; setHistoryOpen(true); setHistoryPending(true);
    try { setHistoryJobs((await api.jobs()).filter((item) => item.mode === 'software_test')); }
    catch (error) { showError('历史软件作业读取', error); }
    finally { historyLock.current = false; setHistoryPending(false); }
  }

  async function restoreHistoryJob(id: string) {
    if (actionLock.current) return;
    actionLock.current = true; setActionPending(true); setHistoryPending(true);
    try {
      const restored = await api.job(id);
      const [savedPlan, restoredEvents] = await Promise.all([api.jobPlan(id), api.events(id)]);
      if (restored.mode !== 'software_test') throw new ApiError('JOB_SCOPE_MISMATCH', '所选历史作业不是软件测试', '重新读取软件作业记录');
      applyRestoredJob(restored, savedPlan, restoredEvents); setHistoryOpen(false);
    } catch (error) { showError('历史软件作业恢复', error); }
    finally { actionLock.current = false; setActionPending(false); setHistoryPending(false); }
  }

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        await api.initialize();
        const receivedCatalog = await api.catalog();
        if (!live) return;
        setCatalog(receivedCatalog);
        const savedId = localStorage.getItem('d1env.currentJob');
        if (savedId) {
          const [restored, restoredEvents] = await Promise.all([api.job(savedId), api.events(savedId)]);
          const savedPlan = await api.jobPlan(savedId);
          if (!live) return;
          applyRestoredJob(restored, savedPlan, restoredEvents);
        } else if (localStorage.getItem('d1env.currentRuntimePrepare')) {
          const softwareProfile = receivedCatalog.profiles.find((profile) => profile.kind === 'software' && profile.profile_id === 'ros-probe');
          if (!softwareProfile) throw new ApiError('PROFILE_UNAVAILABLE', '保存的环境准备任务缺少对应软件配置。', '复核发行包与准备任务，不按 MOCK 配置重建真实准备任务。');
          setMode('software_test'); setProfileId(softwareProfile.profile_id); setStep(2);
        }
        if (live) setReady(true);
      } catch (error) {
        if (live) showError('本地会话 / 作业恢复', error);
      }
    })();
    return () => { live = false; };
  }, [api]);

  useEffect(() => {
    if (!job || job.mode !== 'software_test' || job.state !== 'SUCCEEDED' || job.current_software_ready !== true) return;
    const id = job.job_id;
    const expire = () => {
      if (softwareHealthObservedAt.current !== null && Date.now() - softwareHealthObservedAt.current >= 5000) invalidateSoftwareHealth(id, 'CURRENT_HEALTH_EXPIRED');
    };
    const remaining = Math.max(0, 5000 - (Date.now() - (softwareHealthObservedAt.current ?? 0)));
    const timer = window.setTimeout(expire, remaining);
    document.addEventListener('visibilitychange', expire);
    return () => { window.clearTimeout(timer); document.removeEventListener('visibilitychange', expire); };
  }, [job]);

  async function inspectDoctor() {
    if (doctorLock.current || !ready) return;
    if (!profileId) { showError('执行电脑只读检测', new ApiError('PROFILE_UNAVAILABLE', '尚无当前模式的可执行配置', '请在配置页等待可信工件与对应配置加入')); return; }
    doctorLock.current = true;
    setDoctorPending(true);
    setFailure(null);
    const generation = requestGeneration.current;
    try {
      const [observation, metadata] = await Promise.allSettled([api.doctor(request), mode === 'software_test' ? api.rosArtifact() : Promise.resolve(null)]);
      if (generation !== requestGeneration.current) return;
      if (observation.status === 'fulfilled') setDoctor(observation.value);
      else showError('执行电脑只读检测', observation.reason);
      if (metadata.status === 'fulfilled') setArtifact(metadata.value);
      else setArtifact({ trusted_bundle: null, blocked_reason: '未取得可信发行元数据，请检查本地服务后重新检测电脑；当前不能导入镜像。' });
    }
    finally { doctorLock.current = false; setDoctorPending(false); }
  }

  async function importImage(file: File) {
    const bundle = artifact?.trusted_bundle;
    if (!bundle || mode !== 'software_test' || locked || actionLock.current) return;
    if (file.size !== bundle.size_bytes) { showError('随包软件镜像导入', new ApiError('IMPORT_SIZE_MISMATCH', '所选文件大小与可信发行记录不符', '请重新选择发行包提供的完整 ROS 镜像文件')); return; }
    actionLock.current = true;
    setActionPending(true); setImportPending(true); setImageImported(false); setFailure(null);
    try {
      const result = await api.importRosImage(file);
      if (!['imported', 'reused'].includes(String(result.status)) || result.image_id !== bundle.image_id || result.architecture !== bundle.architecture || result.software_scope_only !== true) {
        throw new ApiError('IMPORT_RESULT_UNVERIFIED', '未取得匹配发行镜像的软件导入证据', '重新检测软件工件并复核服务端记录，不根据不完整响应推断导入成功');
      }
      setImageImported(true);
      setResolution(null);
    } catch (error) { showError('随包软件镜像导入', error); }
    finally { actionLock.current = false; setActionPending(false); setImportPending(false); }
  }

  async function previewPlan() {
    if (previewLock.current || !ready) return null;
    if (!profileId) { showError('部署预览', new ApiError('PROFILE_UNAVAILABLE', '尚无当前模式的可执行配置', '请在配置页等待可信工件与对应配置加入')); return null; }
    previewLock.current = true;
    setPreviewPending(true);
    setFailure(null);
    const generation = requestGeneration.current;
    try {
      const result = await api.preview(request);
      if (generation !== requestGeneration.current) return null;
      setResolution(result);
      return result;
    } catch (error) { if (generation === requestGeneration.current) showError('部署预览', error); return null; }
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
      if (polling || stopped || actionLock.current) return;
      if (currentSnapshot.current && terminalStates.has(currentSnapshot.current.state) && !(currentSnapshot.current.mode === 'software_test' && currentSnapshot.current.state === 'SUCCEEDED')) {
        window.clearInterval(interval);
        // Retrieve terminal events once before ending the poll cycle.
        if (events.length > 0) return;
      }
      polling = true;
      const mutationVersion = jobMutationVersion.current;
      try {
        const [latest, latestEvents] = await Promise.all([api.job(id), api.events(id)]);
        if (stopped || currentJobId.current !== id || mutationVersion !== jobMutationVersion.current) return;
        recordSnapshot(latest);
        setEvents(latestEvents);
        setFailure((previous) => previous?.phase === '作业状态读取' ? null : previous);
        if (terminalStates.has(latest.state) && !(latest.mode === 'software_test' && latest.state === 'SUCCEEDED') && interval !== undefined) window.clearInterval(interval);
      } catch (error) {
        if (!stopped && currentJobId.current === id && mutationVersion === jobMutationVersion.current) {
          invalidateSoftwareHealth(id, 'CURRENT_HEALTH_UNAVAILABLE', error);
          showError('作业状态读取', error);
        }
      } finally { polling = false; }
    }
    interval = window.setInterval(() => void poll(), job.mode === 'software_test' ? 3000 : 400);
    void poll();
    return () => { stopped = true; window.clearInterval(interval); };
  }, [api, job?.job_id, job?.mode, ready]);

  async function startJob(retry = false) {
    if (actionLock.current) return;
    actionLock.current = true;
    setActionPending(true);
    setFailure(null);
    try {
      let planId: string;
      if (retry && job) {
        if (!scopeMatchesMode(job.mode, job.verified_scope)) {
          throw new ApiError('JOB_SCOPE_MISMATCH', '原始作业不属于已实施的软件范围', '导出诊断报告并复核原始作业，不执行范围不明的计划');
        }
        // The backend revalidates the immutable request saved with this plan.
        planId = job.plan_id;
        idempotencyKey.current = null;
      } else {
        const resolved = !resolution ? await previewPlan() : resolution;
        const plan = resolved?.plan;
        if (!plan || resolved?.blockers.length || plan.mode !== mode || !scopeMatchesMode(plan.mode, plan.verified_scope) || plan.request.profile_id !== profileId) {
          setStep(3);
          return;
        }
        planId = plan.plan_id;
      }
      idempotencyKey.current ??= crypto.randomUUID();
      const started = await api.start(planId, idempotencyKey.current);
      if (!scopeMatchesMode(started.mode, started.verified_scope) || started.mode !== mode) throw new ApiError('JOB_SCOPE_MISMATCH', '服务端返回的作业范围与所选模式不一致', '复核服务端作业及原始计划，界面不会降级为演示成功');
      currentJobId.current = started.job_id;
      recordSnapshot(started);
      localStorage.setItem('d1env.currentJob', started.job_id);
      setEvents([]);
      setReport(null);
      setStep(4);
    } catch (error) { showError(mode === 'mock' ? 'MOCK 演示提交' : '真实软件测试提交', error); }
    finally { actionLock.current = false; setActionPending(false); }
  }

  async function cancelJob() {
    const id = job?.job_id;
    if (!id || actionLock.current) return;
    actionLock.current = true;
    jobMutationVersion.current += 1;
    setActionPending(true);
    setFailure(null);
    try {
      const cancelled = await api.cancel(id);
      if (currentJobId.current === id) recordSnapshot(cancelled);
    } catch (error) {
      showError(mode === 'mock' ? '取消本次 MOCK 演示' : '取消本次软件测试', error);
    } finally {
      actionLock.current = false;
      setActionPending(false);
    }
  }

  async function stopJob() {
    const id = job?.job_id;
    if (!id || job?.mode !== 'software_test' || actionLock.current) return;
    actionLock.current = true;
    jobMutationVersion.current += 1;
    setActionPending(true); setFailure(null);
    try {
      const stopped = await api.stop(id);
      if (currentJobId.current === id) {
        recordSnapshot(stopped);
        setEvents(await api.events(id));
      }
    } catch (error) { showError('停止本次测试服务', error); }
    finally { actionLock.current = false; setActionPending(false); }
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

  function detachFinishedJob() {
    if (!job) return;
    currentJobId.current = null;
    currentSnapshot.current = null;
    localStorage.removeItem('d1env.currentJob');
    setJob(null); setEvents([]); setReport(null);
  }

  function selectScenario(next: DemoScenario) {
    if (locked) return;
    detachFinishedJob();
    requestGeneration.current += 1;
    setScenario(next);
    setResolution(null);
    idempotencyKey.current = null;
    setFailure(null);
  }
  function selectProbeScenario(next: ProbeScenario) {
    if (locked) return;
    detachFinishedJob();
    requestGeneration.current += 1;
    setProbeScenario(next); setResolution(null); setFailure(null);
    idempotencyKey.current = null;
  }
  function selectMode(next: ExecutableMode) {
    if (locked) return;
    detachFinishedJob();
    requestGeneration.current += 1;
    setMode(next);
    setProfileId(catalog?.profiles.find((profile) => profile.kind === (next === 'mock' ? 'mock' : 'software'))?.profile_id ?? '');
    setDoctor(null); setResolution(null); setFailure(null);
    idempotencyKey.current = null;
  }
  function selectProfile(id: string) {
    if (locked || !catalog?.profiles.some((profile) => profile.profile_id === id && profile.kind === (mode === 'mock' ? 'mock' : 'software'))) return;
    detachFinishedJob();
    requestGeneration.current += 1;
    setProfileId(id);
    setDoctor(null);
    setResolution(null);
    idempotencyKey.current = null;
  }
  function newDemo() {
    if (locked) return;
    requestGeneration.current += 1;
    currentJobId.current = null;
    currentSnapshot.current = null;
    localStorage.removeItem('d1env.currentJob');
    setJob(null); setEvents([]); setReport(null); setResolution(null); setFailure(null);
    idempotencyKey.current = null;
    setStep(0);
  }
  function repreview() {
    if (locked) return;
    requestGeneration.current += 1;
    setResolution(null); setFailure(null); setStep(3);
    idempotencyKey.current = null;
  }

  return <div className="app-shell">
    <header className="app-header"><a className="brand" href="/" aria-label="D1Env 首页"><span className="brand-mark" aria-hidden="true">D1</span><span>D1Env<small>机器人环境工作台</small></span></a><div className="header-right"><button className="history-entry" type="button" disabled={!ready || actionPending || historyPending} onClick={() => void loadHistory()}>查看历史软件作业</button><span className="local-label"><i /> 本地工作台</span><span className="release-tag">M3 · 软件部署与检查</span></div></header>
    <div className={`mock-banner ${mode === 'software_test' ? 'software-banner' : ''}`} data-testid="mode-watermark"><span data-testid={mode === 'mock' ? 'mock-watermark' : undefined}>{mode === 'mock' ? 'MOCK · 演示模式' : '真实软件测试 · Docker/ROS'}</span><p>{mode === 'mock' ? '当前为软件演示，无真实容器部署，未连接机器人。' : '仅验证 CPU ROS 软件通信，未连接真机，未验证 D1 功能。'}</p><strong>运动权限：未启用</strong></div>
    <div className="workspace-title"><div><span className="eyebrow">D1 ENVIRONMENT / FOUNDATION</span><h2>把每一步，部署得明白。</h2></div><span className="workspace-version">中文向导 <b>01</b></span></div>
    <WizardSteps current={step} onSelect={setStep} disabled={!ready || actionPending} />
    {historyOpen && <JobHistory jobs={historyJobs} pending={historyPending || actionPending} close={() => setHistoryOpen(false)} restore={(id) => void restoreHistoryJob(id)} />}
    <div className="workspace-grid"><main className="main-panel">
      {!ready && !failure && <div className="loading-state" role="status">正在建立本地会话与读取配置…</div>}
      {failure && <section className="request-error" role="alert"><span className="eyebrow">请求未完成</span><h2>{failure.phase}失败</h2><strong>{failure.error.code}</strong><p>检测证据：{failure.error.message}</p><p>下一步：{failure.error.remediation}</p><small>没有收到有效响应时，界面不会推断部署成功。</small></section>}
      {ready && <>
        {step === 0 && <ModePage mode={mode} scenario={scenario} probeScenario={probeScenario} locked={locked} onMode={selectMode} onScenario={selectScenario} onProbeScenario={selectProbeScenario} next={() => setStep(1)} />}
        {step === 1 && <RobotPage mode={mode} locked={locked} profiles={catalog?.profiles ?? []} selectedId={profileId} onSelect={selectProfile} next={() => setStep(2)} />}
        {step === 2 && <HostPage mode={mode} result={doctor} pending={doctorPending} artifact={artifact} importPending={importPending} imported={imageImported} locked={locked} onImport={(file) => void importImage(file)} next={() => setStep(3)} refresh={() => void inspectDoctor()} api={api} preparePending={preparePending} onPreparePending={setPreparePending} onPrepared={() => { setResolution(null); void inspectDoctor(); }} />}
        {step === 3 && <PreviewPage mode={mode} resolution={resolution} scenario={scenario} probeScenario={probeScenario} pending={previewPending || actionPending} start={() => void startJob()} />}
        {step === 4 && <ResultsPage job={job} events={events} scenario={probeScenario} pending={actionPending} report={report} maskIdentifiers={maskIdentifiers} reportMasked={reportMasked} onMaskIdentifiers={setMaskIdentifiers} cancel={() => void cancelJob()} stop={() => void stopJob()} retry={() => void startJob(true)} repreview={repreview} newDemo={newDemo} exportReport={() => void generateReport()} />}
      </>}
    </main><EvidencePanel mode={mode} doctor={doctor} job={job} /></div>
    <footer className="app-footer"><span>D1Env / Foundation</span><span>依据可查 · 范围明确 · 默认只读</span><span>{mode === 'mock' ? 'MOCK ≠ 真机验证' : '软件检查 ≠ D1 真机验证'}</span></footer>
  </div>;
}
