import type { DemoScenario, ExecutableMode, PlanResolution, ProbeScenario } from '../types';
import { scopeMatchesMode } from '../presentation';
import { displayBytes } from './HostPage';

export function PreviewPage({ mode, resolution, scenario, probeScenario, pending, start }: { mode: ExecutableMode; resolution: PlanResolution | null; scenario: DemoScenario; probeScenario: ProbeScenario; pending: boolean; start: () => void }) {
  const plan = resolution?.plan;
  const executable = !!plan && plan.mode === mode && scopeMatchesMode(plan.mode, plan.verified_scope) && resolution?.blockers.length === 0;
  return <>
    <div className="page-heading"><span className="eyebrow">04 / 审阅</span><h1>看清楚，再开始。</h1><p>{mode === 'mock' ? '以下内容由服务端解析。演示只写本项目的作业数据，不启动真实容器。' : '以下内容由服务端解析。将使用可信工件启动本项目拥有的 ROS 测试服务；未部署 D1 驱动。'}</p></div>
    {mode === 'mock' && scenario === 'verify_failure' && <div className="notice warning">故障注入测试 · 验证步骤失败</div>}
    {mode === 'software_test' && probeScenario === 'no_publisher' && <div className="notice warning">故障注入测试 · 无发布者</div>}
    {pending && <div className="notice neutral" role="status">正在生成可复核的部署计划…</div>}
    {resolution?.blockers.map((blocker) => <article className="notice error" key={blocker.code}><strong>{blocker.code}</strong><p>{blocker.message}</p><p>{blocker.remediation}</p></article>)}
    {plan && <>
      <div className="preview-heading"><div><span className={`tag ${mode === 'mock' ? 'mock-tag' : 'software-tag'}`}>{mode === 'mock' ? 'MOCK / 软件演示' : '真实软件测试 / software'}</span><h2>{mode === 'mock' ? '演示任务计划' : 'CPU ROS 软件测试计划'}</h2></div><div><small>预计下载量</small><strong>{displayBytes(plan.download_bytes)}</strong></div></div>
      <ol className="operation-list">{plan.operations.map((operation, index) => <li key={operation.operation_id}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{operation.label}</strong><small>{operation.kind} · {operation.reversible ? '可撤销本次拥有的资源' : '不可撤销'}</small></div><span className="tag neutral-tag">{operation.kind === 'mock_step' ? 'MOCK' : 'Docker'}</span></li>)}</ol>
      {mode === 'software_test' && <><div className="notice warning">Docker daemon 操作权具有高权限风险。本次仅创建本项目容器与内部网络；不使用 privileged、host 网络或主机设备挂载。</div><section className="artifact-preview"><h3>计划使用的可信工件</h3>{plan.operations.filter((operation, index, operations) => operation.artifact && operations.findIndex((candidate) => candidate.artifact?.immutable_id === operation.artifact?.immutable_id) === index).map((operation) => <dl key={operation.artifact!.immutable_id}><dt>来源</dt><dd>{operation.artifact!.source ?? '未知'}</dd><dt>CPU 架构</dt><dd>{operation.artifact!.architecture ?? '未知'}</dd><dt>不可变工件 ID</dt><dd className="mono">{operation.artifact!.immutable_id ?? '未知'}</dd><dt>获取方式</dt><dd>{operation.artifact!.kind === 'local_build' ? '本地构建候选，启动前重新核验' : operation.artifact!.kind}</dd></dl>)}</section></>}
      <div className="impact-grid">{[['写入目录', plan.directories], [mode === 'mock' ? '演示服务' : '测试服务', plan.services], ['所需权限', plan.permissions], ['网络改动', [plan.network === 'none' ? '无 · 不修改网卡或机器人网络' : '项目内部网络 · 不公开端口，不修改机器人网络']]].map(([label, values]) => <section key={String(label)}><h3>{label}</h3>{(values as string[]).map((value) => <p key={value}>{value}</p>)}</section>)}</div>
      <details className="plan-details"><summary>核对计划标识与证据范围</summary><dl><dt>计划 ID</dt><dd className="mono">{plan.plan_id}</dd><dt>配置版本</dt><dd>{plan.profile_revision}</dd><dt>验证范围</dt><dd>{plan.verified_scope}</dd><dt>配置摘要</dt><dd className="mono">{plan.config_digest}</dd></dl></details>
    </>}
    <div className="page-actions"><span>重复点击复用同一作业。失败后可显式重试。</span><button className="primary" type="button" disabled={pending || !executable} onClick={start}>{mode === 'mock' ? '开始 MOCK 演示' : '启动真实软件测试'} <span aria-hidden="true">→</span></button></div>
  </>;
}
