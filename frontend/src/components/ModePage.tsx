import type { DemoScenario } from '../types';

export function ModePage({ scenario, onScenario, next }: { scenario: DemoScenario; onScenario: (scenario: DemoScenario) => void; next: () => void }) {
  return <>
    <div className="page-heading"><span className="eyebrow">01 / 开始</span><h1>先从一次清楚的演示开始。</h1><p>跟随五步向导，了解检查、预览与运行结果。当前版本不会连接机器人。</p></div>
    <div className="mode-grid">
      <button className="mode-card selected" type="button" aria-pressed="true"><span className="card-icon">◇</span><span className="tag mock-tag">默认 · MOCK</span><strong>软件演示体验</strong><span>真实检测这台电脑，用演示任务走完软件流程。</span><small>不需要机器人、Docker 或厂商 SDK</small><span className="radio-mark" aria-hidden="true">✓</span></button>
      <button className="mode-card unavailable" type="button" disabled><span className="card-icon">⌁</span><span className="tag neutral-tag">尚未实施</span><strong>真实机器人只读部署</strong><span>等待准确型号、固件、适配器及工件验证。</span><small>real_readonly · 本轮不可执行</small></button>
    </div>
    <div className="scenario-box"><div><strong>选择演示场景</strong><p>故障注入仅用于验证错误提示和恢复流程。</p></div><label><span className="visually-hidden">演示场景</span><select aria-label="演示场景" value={scenario} onChange={(event) => onScenario(event.target.value as DemoScenario)}><option value="success">标准演示 · 完成软件流程</option><option value="verify_failure">故障注入 · 验证步骤失败</option></select></label></div>
    {scenario === 'verify_failure' && <div className="notice warning">故障注入测试 · 验证步骤失败</div>}
    <div className="page-actions"><span>预计只需几步，无需修改电脑配置。</span><button className="primary" type="button" onClick={next}>下一步：机器人配置 <span aria-hidden="true">→</span></button></div>
  </>;
}
