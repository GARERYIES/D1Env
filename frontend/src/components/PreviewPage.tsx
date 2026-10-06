import type { DemoScenario, PlanResolution } from '../types';
import { displayBytes } from './HostPage';

export function PreviewPage({ resolution, scenario, pending, start }: { resolution: PlanResolution | null; scenario: DemoScenario; pending: boolean; start: () => void }) {
  const plan = resolution?.plan;
  const executable = plan?.mode === 'mock' && plan?.verified_scope === 'mock' && resolution?.blockers.length === 0;
  return <>
    <div className="page-heading"><span className="eyebrow">04 / 审阅</span><h1>看清楚，再开始。</h1><p>以下内容由服务端解析。演示只写本项目的作业数据，不启动真实容器。</p></div>
    {scenario === 'verify_failure' && <div className="notice warning">故障注入测试 · 验证步骤失败</div>}
    {pending && <div className="notice neutral" role="status">正在生成可复核的部署计划…</div>}
    {resolution?.blockers.map((blocker) => <article className="notice error" key={blocker.code}><strong>{blocker.code}</strong><p>{blocker.message}</p><p>{blocker.remediation}</p></article>)}
    {plan && <>
      <div className="preview-heading"><div><span className="tag mock-tag">MOCK / 软件演示</span><h2>演示任务计划</h2></div><div><small>预计下载量</small><strong>{displayBytes(plan.download_bytes)}</strong></div></div>
      <ol className="operation-list">{plan.operations.map((operation, index) => <li key={operation.operation_id}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{operation.label}</strong><small>{operation.kind} · {operation.reversible ? '可撤销本次演示资源' : '不可撤销'}</small></div><span className="tag neutral-tag">MOCK</span></li>)}</ol>
      <div className="impact-grid">{[['写入目录', plan.directories], ['演示服务', plan.services], ['所需权限', plan.permissions], ['网络改动', [plan.network === 'none' ? '无 · 不修改网卡或机器人网络' : plan.network]]].map(([label, values]) => <section key={String(label)}><h3>{label}</h3>{(values as string[]).map((value) => <p key={value}>{value}</p>)}</section>)}</div>
      <details className="plan-details"><summary>核对计划标识与证据范围</summary><dl><dt>计划 ID</dt><dd className="mono">{plan.plan_id}</dd><dt>配置版本</dt><dd>{plan.profile_revision}</dd><dt>验证范围</dt><dd>{plan.verified_scope}</dd><dt>配置摘要</dt><dd className="mono">{plan.config_digest}</dd></dl></details>
    </>}
    <div className="page-actions"><span>重复点击复用同一作业。失败后可显式重试。</span><button className="primary" type="button" disabled={pending || !executable} onClick={start}>开始 MOCK 演示 <span aria-hidden="true">→</span></button></div>
  </>;
}
