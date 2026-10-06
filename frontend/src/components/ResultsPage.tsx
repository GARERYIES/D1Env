import type { JobEvent, JobSnapshot, ReportResponse } from '../types';

const states: Record<string, string> = { PLANNED: '计划已保存', PREFLIGHT: '演示前置检查', ACQUIRING: '准备演示资源', CONFIGURING: '配置演示任务', STARTING: '启动演示步骤', VERIFYING: '验证演示结果', SUCCEEDED: '演示流程完成（MOCK），未部署真机', FAILED: '演示步骤失败', BLOCKED: '演示被阻塞', CANCELLED: '演示已取消', INTERRUPTED: '作业已中断，需要人工复核' };
export const terminalStates = new Set(['SUCCEEDED', 'FAILED', 'BLOCKED', 'CANCELLED', 'INTERRUPTED']);

function download(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ResultsPage({ job, events, pending, report, maskIdentifiers, reportMasked, onMaskIdentifiers, cancel, retry, newDemo, exportReport }: { job: JobSnapshot | null; events: JobEvent[]; pending: boolean; report: ReportResponse | null; maskIdentifiers: boolean; reportMasked: boolean; onMaskIdentifiers: (mask: boolean) => void; cancel: () => void; retry: () => void; newDemo: () => void; exportReport: () => void }) {
  const terminal = job ? terminalStates.has(job.state) : false;
  const failure = job && ['FAILED', 'BLOCKED', 'INTERRUPTED'].includes(job.state);
  const verifiedMock = job?.mode === 'mock' && job.verified_scope === 'mock';
  const failureEvidence = [...events].reverse().find((event) => event.evidence.remediation || event.evidence.error_code);
  const nextAction = typeof failureEvidence?.evidence.remediation === 'string' ? failureEvidence.evidence.remediation : '检查本次 MOCK 故障证据，再按原始计划重试。中断状态不会自动记为成功。';
  return <>
    <div className="page-heading"><span className="eyebrow">05 / 结果</span><h1>{job ? states[job.state] === states.SUCCEEDED && !verifiedMock ? '结果范围待复核' : states[job.state] : '运行结果会出现在这里。'}</h1><p>{job ? '状态来自服务端持久化作业。刷新页面可恢复同一任务。' : '先审阅部署预览，再开始 MOCK 演示。'}</p></div>
    {job && <>
      <div className={`job-summary ${failure ? 'failure' : ''}`}><span className="result-symbol" aria-hidden="true">{failure ? '!' : job.state === 'SUCCEEDED' && verifiedMock ? '✓' : terminal ? '—' : '↻'}</span><div><div className="section-row"><strong data-testid="job-state">{job.state}</strong><span className="tag mock-tag">{job.mode.toUpperCase()} / {job.verified_scope}</span></div><p>作业 <span className="mono" data-testid="job-id">{job.job_id}</span></p><small>最后观测：{job.updated_at}</small></div></div>
      {failure && <section className="failure-help"><div className="section-row"><h2>失败环节与下一步</h2><span className="error-code">{job.error_code ?? job.state}</span></div><p>失败环节：{job.current_operation_id ?? failureEvidence?.operation_id ?? '查看下方步骤证据'}</p><p>下一步：{nextAction}</p><small>MOCK 故障注入不代表真实硬件或 Docker 故障。</small></section>}
      <div className="result-proof-grid"><div><span>演示执行</span><strong>{job.state}</strong></div><div><span>真实 Docker</span><strong>未验证</strong></div><div><span>真机数据</span><strong>UNKNOWN</strong></div><div><span>运动权限</span><strong>未启用</strong></div></div>
      <section className="job-events"><div className="section-row"><h2>步骤与观测证据</h2><span className="tag neutral-tag">{events.length} 条事件</span></div>{events.length === 0 && <p className="muted">等待服务端事件，没有观测时不会推断成功。</p>}{events.map((event) => <article key={event.seq}><div className="event-meta"><span>{String(event.seq).padStart(2, '0')}</span><strong>{event.operation_id ?? event.event_type}</strong><span>{event.origin} · {event.mode}</span><time>{event.timestamp}</time></div><p className="event-message">{event.message}</p><details><summary>检测证据</summary><pre>{JSON.stringify(event.evidence, null, 2)}</pre></details></article>)}</section>
      <div className="export-options"><label><input type="checkbox" checked={maskIdentifiers} disabled={pending} onChange={(event) => onMaskIdentifiers(event.target.checked)} />遮盖 IP / 序列号</label><span>会话令牌、密钥等凭据始终去敏。</span></div>
      <div className="job-actions">{!terminal && <button type="button" className="secondary" disabled={pending} onClick={cancel}>取消本次演示</button>}{failure && <button type="button" className="primary" disabled={pending} onClick={retry}>重试 MOCK 演示</button>}{terminal && <button type="button" className="secondary" disabled={pending} onClick={newDemo}>新建演示</button>}<button type="button" className="secondary" disabled={pending} onClick={exportReport}>生成去敏诊断报告</button></div>
      <p className="muted">取消只清理本作业拥有的演示资源。软件停止请求不等于硬件急停。</p>
      {report && <section className="report-preview"><div className="section-row"><h2>诊断报告预览</h2><span className="tag mock-tag">MOCK</span></div><p>范围：{report.report.verified_scope} · {reportMasked ? '已请求遮盖用户标识' : '未请求遮盖用户标识'}</p><ul>{report.report.redactions.map((item, index) => <li key={index}>{item}</li>)}</ul><p className="muted">未验证：{report.report.unverified_items.join('；')}</p><div className="job-actions"><button type="button" className="secondary" onClick={() => download(JSON.stringify(report.report, null, 2), `d1env-mock-${job.job_id}.json`, 'application/json')}>下载 JSON</button><button type="button" className="secondary" onClick={() => download(report.markdown, `d1env-mock-${job.job_id}.md`, 'text/markdown;charset=utf-8')}>下载 Markdown</button></div></section>}
    </>}
  </>;
}
