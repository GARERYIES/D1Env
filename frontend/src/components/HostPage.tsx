import type { DoctorResponse, ExecutableMode, RosArtifactMetadata } from '../types';
import type { D1EnvApi } from '../api';
import { RosImageImport } from './RosImageImport';
import { RuntimeSetupPanel } from './RuntimeSetupPanel';

function booleanObservation(value: boolean | null) { return value === null ? '未知' : value ? '已检测到' : '未检测到'; }
export function displayBytes(value: number | null) { return value === null ? '未知' : `${(value / 1073741824).toFixed(1)} GB`; }

export function HostPage({ mode, result, pending, artifact, importPending, imported, locked, onImport, next, refresh, api, preparePending, onPreparePending, onPrepared }: { mode: ExecutableMode; result: DoctorResponse | null; pending: boolean; artifact: RosArtifactMetadata | null; importPending: boolean; imported: boolean; locked: boolean; onImport: (file: File) => void; next: () => void; refresh: () => void; api: D1EnvApi; preparePending: boolean; onPreparePending: (pending: boolean) => void; onPrepared: () => void }) {
  const facts = result?.facts;
  return <>
    <div className="page-heading"><span className="eyebrow">03 / 执行电脑</span><h1>先了解执行电脑。</h1><p>检测来自本地后端所在的电脑，浏览器访问端与执行端明确区分。电脑检查只读；软件模式可点击准备运行环境，再部署指定的软件测试。</p></div>
    <div className="host-card"><div className="host-title"><span className="computer-icon" aria-hidden="true">▣</span><div><h2>本地执行电脑</h2><p>目标 local · 后端本机</p></div><span className="tag neutral-tag">{pending ? '检测中…' : result ? '检测已返回' : '待检测'}</span></div>
      <dl className="host-facts"><div><dt>操作系统</dt><dd>{facts ? `${facts.os_name ?? '未知'} ${facts.os_version ?? ''}` : '待检测'}</dd></div><div><dt>CPU 架构</dt><dd>{facts?.architecture ?? '未知'}</dd></div><div><dt>可用磁盘</dt><dd>{displayBytes(facts?.disk_free_bytes ?? null)}</dd></div><div><dt>Docker</dt><dd>{booleanObservation(facts?.docker_available ?? null)}</dd></div><div><dt>Docker 访问</dt><dd>{booleanObservation(facts?.docker_accessible ?? null)}</dd></div><div><dt>Compose</dt><dd>{booleanObservation(facts?.compose_available ?? null)}</dd></div></dl>
      <p className="muted">浏览器访问端：当前浏览器；其系统信息不参与后端兼容判定。</p>
      {mode === 'software_test' && <dl className="host-facts"><div><dt>Docker 执行环境</dt><dd>{facts?.docker_os ?? '未知'}</dd></div><div><dt>Docker CPU 架构</dt><dd>{facts?.docker_architecture ?? '未知'}</dd></div><div><dt>Docker 版本</dt><dd>{facts?.docker_version ?? '未知'}</dd></div></dl>}
      <details><summary>网卡、GPU 与观测时间</summary><dl><dt>本机网卡名称</dt><dd>{facts ? facts.interfaces.join('、') || '未观测到网卡名称' : '待检测'}</dd><dt>GPU 观测</dt><dd>{booleanObservation(facts?.gpu_available ?? null)} · 当前 CPU 测试不需要 GPU</dd><dt>观测时间</dt><dd>{facts?.checked_at ?? '未知'}</dd></dl></details>
    </div>
    {mode === 'software_test' && <RuntimeSetupPanel api={api} locked={locked || importPending} onPrepared={onPrepared} onPending={onPreparePending} />}
    {result && <div className="check-details">{result.checks.map((check) => <article key={check.code}><div className="section-row"><strong>{check.code}</strong><span className={`tiny-status status-${check.status.toLowerCase()}`}>{check.status}</span></div><p>{check.reason}</p><p className="muted">下一步：{check.remediation}</p><details><summary>检测证据 · {check.origin}</summary><pre>{JSON.stringify(check.evidence, null, 2)}</pre><small>观测时间：{check.observed_at}</small></details></article>)}</div>}
    {mode === 'software_test' && <RosImageImport metadata={artifact} pending={importPending} imported={imported} locked={locked || preparePending} onImport={onImport} />}
    <div className="notice neutral">{mode === 'mock' ? 'Docker 未安装或 macOS 只支持界面开发时，仍可完成 MOCK 软件演示；这些观测不会被改写为通过。' : 'Mac 本机系统与 Docker 中的 Linux 执行环境分开记录；缺少 Docker、权限或正确架构时，真实软件计划会被阻塞。'}</div>
    <div className="page-actions"><button className="secondary" type="button" disabled={pending || importPending || preparePending} onClick={refresh}>{pending ? '只读检测中…' : '重新检测电脑'}</button><button className="primary" type="button" disabled={pending || importPending || preparePending || !result} onClick={next}>下一步：部署预览 <span aria-hidden="true">→</span></button></div>
  </>;
}
