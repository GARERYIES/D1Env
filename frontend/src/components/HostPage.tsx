import type { DoctorResponse } from '../types';

function booleanObservation(value: boolean | null) { return value === null ? '未知' : value ? '已检测到' : '未检测到'; }
export function displayBytes(value: number | null) { return value === null ? '未知' : `${(value / 1073741824).toFixed(1)} GB`; }

export function HostPage({ result, pending, next, refresh }: { result: DoctorResponse | null; pending: boolean; next: () => void; refresh: () => void }) {
  const facts = result?.facts;
  return <>
    <div className="page-heading"><span className="eyebrow">03 / 只读检查</span><h1>先了解执行电脑。</h1><p>检测来自本地后端所在的电脑，浏览器访问端与执行端明确区分。不会安装或修改配置。</p></div>
    <div className="host-card"><div className="host-title"><span className="computer-icon" aria-hidden="true">▣</span><div><h2>本地执行电脑</h2><p>目标 local · 后端本机</p></div><span className="tag neutral-tag">{pending ? '检测中…' : result ? '检测已返回' : '待检测'}</span></div>
      <dl className="host-facts"><div><dt>操作系统</dt><dd>{facts ? `${facts.os_name ?? '未知'} ${facts.os_version ?? ''}` : '待检测'}</dd></div><div><dt>CPU 架构</dt><dd>{facts?.architecture ?? '未知'}</dd></div><div><dt>可用磁盘</dt><dd>{displayBytes(facts?.disk_free_bytes ?? null)}</dd></div><div><dt>Docker</dt><dd>{booleanObservation(facts?.docker_available ?? null)}</dd></div><div><dt>Docker 访问</dt><dd>{booleanObservation(facts?.docker_accessible ?? null)}</dd></div><div><dt>Compose</dt><dd>{booleanObservation(facts?.compose_available ?? null)}</dd></div></dl>
      <p className="muted">浏览器访问端：当前浏览器；其系统信息不参与后端兼容判定。</p>
      <details><summary>网卡、GPU 与观测时间</summary><dl><dt>本机网卡名称</dt><dd>{facts ? facts.interfaces.join('、') || '未观测到网卡名称' : '待检测'}</dd><dt>GPU 观测</dt><dd>{booleanObservation(facts?.gpu_available ?? null)} · MOCK 不需要 GPU</dd><dt>观测时间</dt><dd>{facts?.checked_at ?? '未知'}</dd></dl></details>
    </div>
    {result && <div className="check-details">{result.checks.map((check) => <article key={check.code}><div className="section-row"><strong>{check.code}</strong><span className={`tiny-status status-${check.status.toLowerCase()}`}>{check.status}</span></div><p>{check.reason}</p><p className="muted">下一步：{check.remediation}</p><details><summary>检测证据 · {check.origin}</summary><pre>{JSON.stringify(check.evidence, null, 2)}</pre><small>观测时间：{check.observed_at}</small></details></article>)}</div>}
    <div className="notice neutral">Docker 未安装或 macOS 只支持界面开发时，仍可完成 MOCK 软件演示；这些观测不会被改写为通过。</div>
    <div className="page-actions"><button className="secondary" type="button" disabled={pending} onClick={refresh}>{pending ? '只读检测中…' : '重新检测电脑'}</button><button className="primary" type="button" disabled={pending || !result} onClick={next}>下一步：部署预览 <span aria-hidden="true">→</span></button></div>
  </>;
}
