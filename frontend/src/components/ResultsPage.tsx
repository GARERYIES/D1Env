import type { JobEvent, JobSnapshot, ProbeScenario, ReportResponse } from '../types';
import { modeLabel, scopeMatchesMode } from '../presentation';

const states: Record<string, string> = { PLANNED: '计划已保存', PREFLIGHT: '演示前置检查', ACQUIRING: '准备演示资源', CONFIGURING: '配置演示任务', STARTING: '启动演示步骤', VERIFYING: '验证演示结果', SUCCEEDED: '演示流程完成（MOCK），未部署真机', FAILED: '演示步骤失败', BLOCKED: '演示被阻塞', CANCELLED: '演示已取消', INTERRUPTED: '作业已中断，需要人工复核' };
const softwareStates: Record<string, string> = { PLANNED: '软件计划已保存', PREFLIGHT: '软件前置检查', ACQUIRING: '核验软件工件', CONFIGURING: '准备测试配置', STARTING: '启动测试服务', VERIFYING: '检查 ROS 消息新鲜度', SUCCEEDED: '软件环境检查通过，未连接真机', FAILED: '软件测试未通过', BLOCKED: '软件测试被阻塞', CANCELLED: '测试服务已停止或作业已取消', INTERRUPTED: '软件作业已中断，需要复核' };
export const terminalStates = new Set(['SUCCEEDED', 'FAILED', 'BLOCKED', 'CANCELLED', 'INTERRUPTED']);

function download(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ResultsPage({ job, events, scenario, pending, report, maskIdentifiers, reportMasked, onMaskIdentifiers, cancel, stop, retry, repreview, newDemo, exportReport }: { job: JobSnapshot | null; events: JobEvent[]; scenario: ProbeScenario; pending: boolean; report: ReportResponse | null; maskIdentifiers: boolean; reportMasked: boolean; onMaskIdentifiers: (mask: boolean) => void; cancel: () => void; stop: () => void; retry: () => void; repreview: () => void; newDemo: () => void; exportReport: () => void }) {
  const terminal = job ? terminalStates.has(job.state) : false;
  const failure = job && ['FAILED', 'BLOCKED', 'INTERRUPTED'].includes(job.state);
  const software = job?.mode === 'software_test';
  const validScope = !!job && scopeMatchesMode(job.mode, job.verified_scope);
  const currentSoftwareReady = software && validScope && job?.state === 'SUCCEEDED' && job.current_software_ready === true;
  const softwareHealthUnknown = software && job?.state === 'SUCCEEDED' && !currentSoftwareReady;
  const canRetry = software ? terminal && job?.state !== 'SUCCEEDED' : failure;
  const softwareEvidence = Object.assign({}, ...events.filter((event) => event.origin === 'docker').map((event) => event.evidence)) as Record<string, unknown>;
  const currentHealth = job?.current_health_evidence ?? {};
  const healthCode = typeof currentHealth.error_code === 'string' ? currentHealth.error_code : typeof currentHealth.code === 'string' ? currentHealth.code : 'CURRENT_HEALTH_UNKNOWN';
  const failureEvidence = [...events].reverse().find((event) => event.evidence.remediation || event.evidence.error_code);
  const nextAction = typeof failureEvidence?.evidence.remediation === 'string' ? failureEvidence.evidence.remediation : software ? '核对当前软件服务与消息证据，重新预览或按原始计划重试。缺失或过期消息不会记为成功。' : '检查本次 MOCK 故障证据，再按原始计划重试。中断状态不会自动记为成功。';
  return <>
    <div className="page-heading"><span className="eyebrow">05 / 结果</span><h1>{job ? !validScope ? '结果范围待复核' : softwareHealthUnknown ? '部署曾完成，当前软件状态未知' : software ? softwareStates[job.state] : states[job.state] : '运行结果会出现在这里。'}</h1><p>{job ? software ? '状态来自服务端当前软件检查。页面每三秒读取；服务失效会撤销历史成功。' : '状态来自服务端持久化作业。刷新页面可恢复同一任务。' : '先审阅部署预览，再启动所选范围的任务。'}</p></div>
    {job && <>
      {software && scenario === 'no_publisher' && <div className="notice warning">故障注入测试 · 无发布者</div>}
      <div className={`job-summary ${failure ? 'failure' : ''} ${job.state === 'CANCELLED' || softwareHealthUnknown ? 'neutral' : ''}`}><span className="result-symbol" aria-hidden="true">{failure ? '!' : job.state === 'SUCCEEDED' && validScope && (!software || currentSoftwareReady) ? '✓' : terminal ? '—' : '↻'}</span><div><div className="section-row"><strong data-testid="job-state">{job.state}{softwareHealthUnknown ? ' / 当前 UNKNOWN' : ''}</strong><span className={`tag ${software ? 'software-tag' : 'mock-tag'}`}>{modeLabel(job.mode)} / {job.verified_scope}</span></div><p>作业 <span className="mono" data-testid="job-id">{job.job_id}</span></p><small>状态事件时间：{job.updated_at}</small></div></div>
      {softwareHealthUnknown && <section className="notice warning"><strong>{healthCode}</strong><p>本次未取得当前软件通信通过的证据。若目标被其他作业占用，请稍后刷新；历史部署记录不会作为当前正常状态。</p><details><summary>本次软件检查证据</summary><pre>{JSON.stringify(currentHealth, null, 2)}</pre></details></section>}
      {failure && <section className="failure-help"><div className="section-row"><h2>失败环节与下一步</h2><span className="error-code">{job.error_code ?? job.state}</span></div><p>失败环节：{job.current_operation_id ?? failureEvidence?.operation_id ?? '查看下方步骤证据'}</p><p>下一步：{nextAction}</p><small>{software ? '软件故障或故障注入仅描述当前 Docker/ROS 测试，不是 D1 真机状态。' : 'MOCK 故障注入不代表真实硬件或 Docker 故障。'}</small></section>}
      <div className="result-proof-grid"><div><span>{software ? '软件执行' : '演示执行'}</span><strong>{job.state}</strong></div><div><span>真实 Docker</span><strong>{software && validScope ? currentSoftwareReady ? '当前软件检查通过' : softwareHealthUnknown ? 'UNKNOWN' : job.state === 'CANCELLED' ? '测试已停止' : '未通过 / 待验证' : '未验证'}</strong></div><div><span>真机数据</span><strong>UNKNOWN</strong></div><div><span>运动权限</span><strong>未启用</strong></div></div>
      {software && <div className="software-layers"><section><h3>工件核验记录</h3><strong>{softwareEvidence.artifact_verified === true ? '已核验（历史记录）' : 'UNKNOWN'}</strong></section><section><h3>容器运行</h3><strong>{currentSoftwareReady && currentHealth.containers_running === true ? '当前检查通过' : 'UNKNOWN / 已停止或待验证'}</strong></section><section><h3>ROS 软件消息</h3><strong>{currentSoftwareReady && currentHealth.software_ready === true ? '新鲜度检查通过' : 'UNKNOWN / 未就绪'}</strong></section><section><h3>D1 功能</h3><strong>未实施 / 未验证</strong></section></div>}
      <section className="job-events"><div className="section-row"><h2>步骤与观测证据</h2><span className="tag neutral-tag">{events.length} 条事件</span></div>{events.length === 0 && <p className="muted">等待服务端事件，没有观测时不会推断成功。</p>}{events.map((event) => <article key={event.seq}><div className="event-meta"><span>{String(event.seq).padStart(2, '0')}</span><strong>{event.operation_id ?? event.event_type}</strong><span>{event.origin} · {event.mode}</span><time>{event.timestamp}</time></div><p className="event-message">{event.message}</p><details><summary>检测证据</summary><pre>{JSON.stringify(event.evidence, null, 2)}</pre></details></article>)}</section>
      <div className="export-options"><label><input type="checkbox" checked={maskIdentifiers} disabled={pending} onChange={(event) => onMaskIdentifiers(event.target.checked)} />遮盖 IP / 序列号</label><span>会话令牌、密钥等凭据始终去敏。</span></div>
      <div className="job-actions">{!terminal && <button type="button" className="secondary" disabled={pending} onClick={cancel}>{software ? '取消本次软件测试' : '取消本次演示'}</button>}{software && terminal && validScope && <button type="button" className="secondary" disabled={pending} onClick={stop}>{job.state === 'SUCCEEDED' ? '停止测试服务' : '清理本作业遗留服务'}</button>}{canRetry && <button type="button" className="primary" disabled={pending} onClick={retry}>{software ? '重试真实软件测试' : '重试 MOCK 演示'}</button>}{software && terminal && job.state !== 'SUCCEEDED' && <button type="button" className="secondary" disabled={pending} onClick={repreview}>重新预览软件计划</button>}{terminal && !(software && job.state === 'SUCCEEDED') && <button type="button" className="secondary" disabled={pending} onClick={newDemo}>{software ? '新建软件测试' : '新建演示'}</button>}<button type="button" className="secondary" disabled={pending} onClick={exportReport}>生成去敏诊断报告</button></div>
      {software && failure && <p className="muted">重试前需要确认原作业资源已清空。若清理记录不完整，请先清理本作业遗留服务；其他旧作业可从顶部历史入口恢复并清理。</p>}
      <p className="muted">{software ? '停止或取消只清理当前作业拥有的容器与网络，保留镜像及用户数据。' : '取消只清理本作业拥有的演示资源。'}软件停止请求不等于硬件急停。</p>
      {report && <section className="report-preview"><div className="section-row"><h2>诊断报告预览</h2><span className={`tag ${report.report.mode === 'mock' ? 'mock-tag' : 'software-tag'}`}>{modeLabel(report.report.mode)}</span></div><p>范围：{report.report.verified_scope} · {reportMasked ? '已请求遮盖用户标识' : '未请求遮盖用户标识'}</p><ul>{report.report.redactions.map((item, index) => <li key={index}>{item}</li>)}</ul><p className="muted">未验证：{report.report.unverified_items.join('；')}</p><div className="job-actions"><button type="button" className="secondary" onClick={() => download(JSON.stringify(report.report, null, 2), `d1env-${report.report.verified_scope}-${job.job_id}.json`, 'application/json')}>下载 JSON</button><button type="button" className="secondary" onClick={() => download(report.markdown, `d1env-${report.report.verified_scope}-${job.job_id}.md`, 'text/markdown;charset=utf-8')}>下载 Markdown</button></div></section>}
    </>}
  </>;
}
