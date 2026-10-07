import type { DoctorResponse, ExecutableMode, JobSnapshot } from '../types';

function UnknownTelemetry() {
  return <div className="telemetry-grid">
    <div><span>电量</span><strong data-testid="battery-value">未知 <small>null</small></strong></div>
    <div><span>姿态</span><strong data-testid="pose-value">未知 <small>null</small></strong></div>
  </div>;
}

export function EvidencePanel({ mode, doctor, job }: { mode: ExecutableMode; doctor: DoctorResponse | null; job: JobSnapshot | null }) {
  return <aside className="evidence-panel" aria-label="状态与证据">
    <div className="aside-heading"><span className="eyebrow">STATUS & EVIDENCE</span><h2>每一步，都有依据</h2></div>
    <div className="scope-card"><span className={`tag ${mode === 'mock' ? 'mock-tag' : 'software-tag'}`}>{mode === 'mock' ? 'MOCK' : '软件测试'}</span><p>{job ? '当前作业范围' : '计划验证范围'}</p><strong data-testid="verified-scope">{job?.verified_scope ?? (mode === 'mock' ? 'mock' : 'software / 待验证')}</strong><small>{mode === 'mock' ? '软件演示结果不代表 Docker 或真机验证。' : '仅检查 Docker/ROS 软件服务，不代表 D1 驱动、数据或运动已验证。'}</small></div>
    <section className="evidence-section">
      <div className="section-row"><h3>真机遥测</h3><span className="tag unknown-tag" data-testid="telemetry-state">UNKNOWN</span></div>
      <UnknownTelemetry />
      <p className="muted">未连接机器人。缺失观测保持 null，不判断为正常。</p>
      <button type="button" className="motion-disabled" disabled>运动控制未启用</button>
    </section>
    <section className="evidence-section">
      <div className="section-row"><h3>电脑检测</h3><span className="tag neutral-tag">{doctor ? '真实只读' : '待检测'}</span></div>
      <p className="muted">{doctor ? '来源：local_probe · 后端本机观测' : '执行电脑信息将由后端获取。浏览器不会自报检测结果。'}</p>
      {doctor && <ul className="evidence-checks">{doctor.checks.map((check) => <li key={check.code}><span className={`tiny-status status-${check.status.toLowerCase()}`}>{check.status}</span><span>{check.reason}</span></li>)}</ul>}
    </section>
    <div className="boundary-note"><span aria-hidden="true">↳</span><p>{mode === 'mock' ? 'MOCK 软件演示' : '真实 CPU ROS 软件测试'}<br /><small>{mode === 'mock' ? '无 SDK、无容器操作、无运动指令' : '未接 SDK、未接真机、无运动指令'}</small></p></div>
  </aside>;
}
