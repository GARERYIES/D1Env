import { useEffect, useRef, useState } from 'react';
import { ApiError, D1EnvApi } from '../api';
import type { RuntimeStage, RuntimeStatus, RuntimeTask, RuntimeUserAction } from '../types';

const stageLabels: Record<RuntimeStage, string> = {
  detect: '检测并复用已有环境', license: '等待许可确认', download: '下载可信安装包', verify: '核对安装包完整性',
  install: '打开原生安装过程', native_setup: '等待原生许可与系统授权', start: '启动本机运行环境',
  wait_ready: '等待运行环境响应', import_image: '自动准备配套软件镜像', complete: '准备流程结束',
};
const states = new Set(['RUNNING', 'WAITING_USER', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED']);
const terminalStates = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED']);
const taskPointer = 'd1env.currentRuntimePrepare';
const requestPointer = 'd1env.runtimePrepareKey';

function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function readyValue(value: unknown) { return value === null || typeof value === 'boolean'; }
function nullableText(value: unknown) { return value === null || typeof value === 'string'; }
function checkedProgress(value: RuntimeTask['progress']) {
  return value === undefined || value === null || (object(value) && typeof value.downloaded_bytes === 'number' && Number.isSafeInteger(value.downloaded_bytes) && value.downloaded_bytes >= 0 && typeof value.total_bytes === 'number' && Number.isSafeInteger(value.total_bytes) && value.total_bytes > 0 && value.downloaded_bytes <= value.total_bytes);
}
function checkedInstaller(value: RuntimeStatus['installer']) {
  return value === null || (object(value) && nullableText(value.version) && nullableText(value.sha256) && nullableText(value.license_url) && (value.blocked_reason === undefined || nullableText(value.blocked_reason)) && (value.size_bytes === null || (typeof value.size_bytes === 'number' && Number.isSafeInteger(value.size_bytes) && value.size_bytes >= 0)));
}
function checkedTask(value: RuntimeTask): RuntimeTask {
  if (!object(value) || value.scope !== 'runtime_environment' || typeof value.task_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$/.test(value.task_id) || typeof value.request_key !== 'string' || !states.has(value.state) || typeof value.stage !== 'string' || !Object.prototype.hasOwnProperty.call(stageLabels, value.stage) || !readyValue(value.environment_ready) || ![null, 'accept_license', 'check_again'].includes(value.user_action) || !object(value.evidence) || !Array.isArray(value.events) || !value.events.every(object) || typeof value.message !== 'string' || typeof value.remediation !== 'string' || typeof value.updated_at !== 'string' || !nullableText(value.error_code) || !checkedProgress(value.progress)) {
    throw new ApiError('RUNTIME_RESPONSE_UNVERIFIED', '未取得可核对的运行环境准备任务。', '重新读取本地服务的准备任务，不按不完整响应判断准备成功。');
  }
  return value;
}
function checkedStatus(value: RuntimeStatus): RuntimeStatus {
  if (!object(value) || !readyValue(value.environment_ready) || !object(value.platform) || typeof value.platform.supported !== 'boolean' || !nullableText(value.platform.os) || !nullableText(value.platform.architecture) || !checkedInstaller(value.installer) || !object(value.evidence) || typeof value.message !== 'string' || typeof value.remediation !== 'string' || typeof value.observed_at !== 'string') {
    throw new ApiError('RUNTIME_RESPONSE_UNVERIFIED', '未取得当前执行电脑的运行环境观测。', '重新读取本地服务状态；未知观测不能判断为准备完成。');
  }
  if (value.task !== null) checkedTask(value.task);
  if (value.environment_ready === true && value.platform.supported !== true) throw new ApiError('RUNTIME_RESPONSE_UNVERIFIED', '当前平台未支持，返回的准备成功状态没有有效兼容证据。', '使用已验证平台并重新读取状态；未知平台不能显示准备成功。');
  return value;
}
function combinedReady(earlier: boolean | null, later: boolean | null): boolean | null {
  return earlier === true && later === true ? true : earlier === false || later === false ? false : null;
}
function officialLicenseUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['www.docker.com', 'docker.com', 'docs.docker.com'].includes(url.hostname) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function RuntimeSetupPanel({ api, locked, onPrepared, onPending }: { api: D1EnvApi; locked: boolean; onPrepared: () => void; onPending: (pending: boolean) => void }) {
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [task, setTask] = useState<RuntimeTask | null>(null);
  const [pending, setPending] = useState(false);
  const [reading, setReading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const actionLock = useRef(false);
  const mutation = useRef(0);
  const currentTaskId = useRef<string | null>(null);
  const readyObservedAt = useRef<number | null>(null);
  const refreshedTask = useRef<string | null>(null);
  const onPreparedRef = useRef(onPrepared);
  const onPendingRef = useRef(onPending);
  onPreparedRef.current = onPrepared; onPendingRef.current = onPending;

  function failed(cause: unknown) {
    readyObservedAt.current = null;
    setError(cause instanceof ApiError ? cause : new ApiError('RUNTIME_REQUEST_FAILED', '未完成运行环境准备观测。', '检查本地服务并显式重试；不会自动重开安装过程。'));
  }
  function receivedTask(value: RuntimeTask) {
    const verified = checkedTask(value);
    currentTaskId.current = verified.task_id;
    localStorage.setItem(taskPointer, verified.task_id);
    setTask(verified); setError(null);
    readyObservedAt.current = verified.state === 'SUCCEEDED' && verified.environment_ready === true ? Date.now() : null;
    if (verified.state === 'SUCCEEDED' && verified.environment_ready === true && refreshedTask.current !== verified.task_id) {
      refreshedTask.current = verified.task_id; onPreparedRef.current();
    }
  }

  async function readCurrent(isLive = () => true) {
    if (actionLock.current) return;
    const version = mutation.current;
    setReading(true);
    try {
        const observation = checkedStatus(await api.runtimeStatus());
        if (!isLive() || mutation.current !== version) return;
        const id = observation.task?.task_id ?? localStorage.getItem(taskPointer);
        if (id) {
          const recovered = checkedTask(await api.runtimeTask(id));
          if (!isLive() || mutation.current !== version) return;
          if (recovered.task_id !== id) throw new ApiError('RUNTIME_TASK_MISMATCH', '读取的准备任务身份与保存指针不符。', '复核本地任务记录；不自动创建新任务。');
          const ready = combinedReady(observation.environment_ready, recovered.environment_ready);
          setStatus({ ...observation, environment_ready: ready });
          receivedTask({ ...recovered, environment_ready: ready });
        } else {
          setStatus(observation); setError(null);
          readyObservedAt.current = observation.environment_ready === true ? Date.now() : null;
        }
      } catch (cause) { if (isLive() && mutation.current === version) failed(cause); }
      finally { if (isLive() && mutation.current === version) setReading(false); }
  }

  useEffect(() => {
    let live = true;
    void readCurrent(() => live);
    return () => { live = false; };
  }, [api]);

  useEffect(() => {
    if (!task) return;
    const id = task.task_id;
    let stopped = false;
    let polling = false;
    const poll = async () => {
      if (stopped || polling || actionLock.current) return;
      polling = true;
      const version = mutation.current;
      try {
        const latest = checkedTask(await api.runtimeTask(id));
        const observation = latest.state === 'SUCCEEDED' ? checkedStatus(await api.runtimeStatus()) : null;
        if (stopped || currentTaskId.current !== id || mutation.current !== version) return;
        if (latest.task_id !== id) throw new ApiError('RUNTIME_TASK_MISMATCH', '当前读取的准备任务身份不匹配。', '重新读取本地服务，不使用其他任务的准备结果。');
        const ready = observation ? combinedReady(latest.environment_ready, observation.environment_ready) : latest.environment_ready;
        if (observation) setStatus({ ...observation, environment_ready: ready });
        receivedTask({ ...latest, environment_ready: ready });
      } catch (cause) { if (!stopped && currentTaskId.current === id && mutation.current === version) failed(cause); }
      finally { polling = false; }
    };
    const timer = window.setInterval(() => { void poll(); }, 3000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [api, task?.task_id]);

  const currentlyReady = !error && (task ? task.state === 'SUCCEEDED' && task.environment_ready === true : status?.environment_ready === true);
  useEffect(() => {
    if (!currentlyReady) return;
    const expire = () => {
      if (readyObservedAt.current !== null && Date.now() - readyObservedAt.current >= 10000) failed(new ApiError('RUNTIME_OBSERVATION_EXPIRED', '超过十秒未取得新的运行环境准备观测。', '等待只读复核或重新打开执行电脑页；历史准备不代表当前环境可用。'));
    };
    const timer = window.setTimeout(expire, Math.max(0, 10000 - (Date.now() - (readyObservedAt.current ?? 0))));
    document.addEventListener('visibilitychange', expire);
    return () => { window.clearTimeout(timer); document.removeEventListener('visibilitychange', expire); };
  }, [currentlyReady, task, status]);

  const activeTask = !!task && !terminalStates.has(task.state);
  const installerBlocked = status?.installer?.blocked_reason;
  const hostEvidence = object(status?.evidence.host) ? status.evidence.host : status?.evidence;
  const existingLocalDocker = hostEvidence?.docker_accessible === true && hostEvidence?.endpoint_local === true;
  const canPrepare = !locked && !pending && !reading && !!status && status.platform.supported === true && (!installerBlocked || existingLocalDocker) && !activeTask;
  const licenseUrl = officialLicenseUrl(status?.installer?.license_url);

  async function mutate(kind: 'prepare' | 'cancel' | RuntimeUserAction) {
    if (actionLock.current || locked || (kind === 'prepare' && !canPrepare) || (kind !== 'prepare' && !task)) return;
    if (kind === 'accept_license' && !licenseUrl) return;
    actionLock.current = true; mutation.current += 1;
    setPending(true); onPendingRef.current(true); setError(null);
    try {
      if (kind === 'prepare') {
        let requestKey = localStorage.getItem(requestPointer);
        if (!requestKey || (task && terminalStates.has(task.state))) requestKey = crypto.randomUUID();
        localStorage.setItem(requestPointer, requestKey);
        receivedTask(await api.prepareRuntime(requestKey));
      } else if (kind === 'cancel') receivedTask(await api.cancelRuntime(task!.task_id));
      else receivedTask(await api.continueRuntime(task!.task_id, kind));
    } catch (cause) { failed(cause); }
    finally { actionLock.current = false; setPending(false); onPendingRef.current(false); }
  }

  const currentLabel = error || (task?.state === 'SUCCEEDED' && task.environment_ready !== true) || (!task && status?.environment_ready === null) ? 'UNKNOWN' : currentlyReady ? '仅运行环境已准备' : reading ? '读取中' : '尚未准备';
  return <section className="runtime-setup-card" aria-label="准备运行环境">
    <div className="section-row"><h2>准备运行环境</h2><span className="tag neutral-tag" data-testid="runtime-current-state">{currentLabel}</span></div>
    <p>点击一次，由 D1Env 检测和复用已有环境；需要时下载、校验并打开 Docker 原生安装过程，再准备配套软件镜像。MOCK 演示不需要这一步。</p>
    <p className="muted">Docker 拥有本机高权限操作能力。许可适用性与系统授权由你在明确提示中确认；本页不收集系统密码。</p>
    {status && <dl className="import-facts"><div><dt>执行平台</dt><dd>{status.platform.os ?? '未知'} / {status.platform.architecture ?? '未知'}</dd></div><div><dt>安装包版本 / 大小</dt><dd>{status.installer?.version ?? '未知'} / {status.installer?.size_bytes === null || status.installer?.size_bytes === undefined ? '未知' : `${status.installer.size_bytes.toLocaleString('zh-CN')} 字节`}</dd></div><div><dt>安装包 SHA-256</dt><dd className="mono">{status.installer?.sha256 ?? '未取得可信摘要'}</dd></div></dl>}
    {licenseUrl && <a className="runtime-license-link" href={licenseUrl} target="_blank" rel="noopener noreferrer">阅读 Docker 许可条件</a>}
    {installerBlocked && <div className="notice warning">{installerBlocked}</div>}
    {task && <div className="runtime-task-status"><div className="section-row"><strong data-testid="runtime-stage">{stageLabels[task.stage]}</strong><span className="tag neutral-tag">{task.state}</span></div><p>{task.message}</p><p className="muted">下一步：{task.remediation}</p>{task.stage === 'download' && (task.progress ? <div className="runtime-download-progress"><p>已下载 {(task.progress.downloaded_bytes / 1000000).toFixed(1)} MB / {(task.progress.total_bytes / 1000000).toFixed(1)} MB</p><progress aria-label="安装包下载进度" value={task.progress.downloaded_bytes} max={task.progress.total_bytes} /></div> : <p className="muted">下载进度未知；尚未取得可核对的字节数。</p>)}{task.error_code && <strong className="runtime-error-code">{task.error_code}</strong>}<details><summary>准备任务与实际阶段证据</summary><dl><dt>任务范围</dt><dd>runtime_environment · 不包含 ROS 通信与 D1 功能检查</dd><dt>任务 ID</dt><dd className="mono">{task.task_id}</dd><dt>记录时间</dt><dd>{task.updated_at}</dd></dl><pre>{JSON.stringify(task.evidence, null, 2)}</pre>{task.events.map((event, index) => <pre key={index}>{JSON.stringify(event, null, 2)}</pre>)}</details></div>}
    {reading && <p className="muted">正在核对本机入口与官方签名，首次检查可能需要约一分钟。</p>}
    {!task && status && <p>{status.message}<br /><span className="muted">下一步：{status.remediation}</span></p>}
    {error && <div className="notice error" role="status"><strong>{error.code}</strong><p>检测证据：{error.message}</p><p>下一步：{error.remediation}</p><small>当前观测为 UNKNOWN；不会重新执行安装或推断成功。</small></div>}
    {currentlyReady && <div className="notice neutral">运行环境已准备；尚未启动 ROS 通信检查。</div>}
    <div className="runtime-actions"><button className="primary" type="button" disabled={!canPrepare} onClick={() => { void mutate('prepare'); }}>{pending ? '正在提交准备请求…' : '准备运行环境'}</button><button className="secondary" type="button" disabled={pending || reading} onClick={() => { void readCurrent(); }}>重新读取准备状态</button>
      {task?.state === 'WAITING_USER' && task.user_action === 'accept_license' && <button className="secondary" type="button" disabled={pending || locked || !licenseUrl || !!error} onClick={() => { void mutate('accept_license'); }}>已阅读许可并确认适用，继续准备</button>}
      {task?.user_action === 'check_again' && <button className="secondary" type="button" disabled={pending || locked || !!error} onClick={() => { void mutate('check_again'); }}>已完成原生提示，重新检查</button>}
      {activeTask && <button className="secondary" type="button" disabled={pending || locked} onClick={() => { void mutate('cancel'); }}>取消本次环境准备</button>}
    </div>
    <p className="muted">环境和镜像准备完成后，继续部署预览与 ROS 软件测试；真机数据仍为 UNKNOWN，运动未启用。手动镜像导入保留在下方作为备用。</p>
  </section>;
}
