import type { DemoScenario, ExecutableMode, ProbeScenario } from '../types';

export function ModePage({ mode, scenario, probeScenario, locked, onMode, onScenario, onProbeScenario, next }: { mode: ExecutableMode; scenario: DemoScenario; probeScenario: ProbeScenario; locked: boolean; onMode: (mode: ExecutableMode) => void; onScenario: (scenario: DemoScenario) => void; onProbeScenario: (scenario: ProbeScenario) => void; next: () => void }) {
  return <>
    <div className="page-heading"><span className="eyebrow">01 / 开始</span><h1>选择这次要验证的范围。</h1><p>先检查，再预览改动。MOCK 与真实软件服务分开记录，当前版本不会连接机器人。</p></div>
    <div className="mode-grid">
      <button className={`mode-card ${mode === 'mock' ? 'selected' : ''}`} type="button" aria-pressed={mode === 'mock'} disabled={locked} onClick={() => onMode('mock')}><span className="card-icon">◇</span><span className="tag mock-tag">默认 · MOCK</span><strong>软件演示体验</strong><span>真实检测这台电脑，用演示任务走完软件流程。</span><small>不需要机器人、Docker 或厂商 SDK</small>{mode === 'mock' && <span className="radio-mark" aria-hidden="true">✓</span>}</button>
      <button className={`mode-card ${mode === 'software_test' ? 'selected' : ''}`} type="button" aria-label="真实软件测试（Docker/ROS，未接真机）" aria-pressed={mode === 'software_test'} disabled={locked} onClick={() => onMode('software_test')}><span className="card-icon">▣</span><span className="tag software-tag">M3 · software</span><strong>真实软件测试</strong><span>在 Docker 中启动 CPU ROS 通信探针，检查消息新鲜度。</span><small>Docker/ROS · 未连接真机</small>{mode === 'software_test' && <span className="radio-mark" aria-hidden="true">✓</span>}</button>
      <button className="mode-card unavailable" type="button" disabled><span className="card-icon">⌁</span><span className="tag neutral-tag">尚未实施</span><strong>真实机器人只读部署</strong><span>等待准确型号、固件、适配器及工件验证。</span><small>real_readonly · 本轮不可执行</small></button>
    </div>
    {mode === 'mock' ? <div className="scenario-box"><div><strong>选择演示场景</strong><p>故障注入仅用于验证错误提示和恢复流程。</p></div><label><span className="visually-hidden">演示场景</span><select aria-label="演示场景" value={scenario} disabled={locked} onChange={(event) => onScenario(event.target.value as DemoScenario)}><option value="success">标准演示 · 完成软件流程</option><option value="verify_failure">故障注入 · 验证步骤失败</option></select></label></div>
      : <><div className="scenario-box"><div><strong>选择软件测试场景</strong><p>仅启动本项目通信探针，不验证 D1 驱动、传感器或导航。</p></div><label><span className="visually-hidden">软件测试场景</span><select aria-label="软件测试场景" value={probeScenario} disabled={locked} onChange={(event) => onProbeScenario(event.target.value as ProbeScenario)}><option value="success">标准测试 · ROS 消息通信</option><option value="no_publisher">故障注入 · 无发布者</option></select></label></div><div className="notice warning">Docker daemon 操作权属于高权限信任边界；本次只允许本项目已解析的固定软件操作。</div></>}
    {mode === 'mock' && scenario === 'verify_failure' && <div className="notice warning">故障注入测试 · 验证步骤失败</div>}
    {mode === 'software_test' && probeScenario === 'no_publisher' && <div className="notice warning">故障注入测试 · 无发布者</div>}
    {locked && <div className="notice neutral">当前作业仍在执行或软件服务仍在运行。请先在结果页取消作业或停止测试服务，再更改配置。</div>}
    <div className="page-actions"><span>{mode === 'mock' ? '演示不会修改电脑配置。' : '将创建本项目拥有的测试容器与内部网络。'}</span><button className="primary" type="button" onClick={next}>下一步：机器人配置 <span aria-hidden="true">→</span></button></div>
  </>;
}
