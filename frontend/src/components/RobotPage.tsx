import type { ExecutableMode, Profile } from '../types';

const capabilityNames: Record<string, string> = { demo: '软件演示', ros_probe: 'ROS 软件通信探针', readonly: '只读遥测', mapping: '建图', navigation: '导航与运动' };

function RobotMark({ variant }: { variant: string | null }) {
  return <svg aria-hidden="true" viewBox="0 0 150 88" className="robot-mark"><path d="M43 30h66l10 17-11 11H49L35 44z" fill="currentColor" opacity=".18" /><path d="M43 30h66l10 17-11 11H49L35 44zM52 57l-11 12 7 14M101 58l14 12-9 13M53 32l-12-9M102 32l14-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinejoin="round" /><circle cx="108" cy="43" r="3" fill="currentColor" />{variant?.includes('1w') && <><circle cx="48" cy="79" r="7" fill="none" stroke="currentColor" strokeWidth="3" /><circle cx="108" cy="79" r="7" fill="none" stroke="currentColor" strokeWidth="3" /></>}</svg>;
}

export function RobotPage({ mode, locked, profiles, selectedId, onSelect, next }: { mode: ExecutableMode; locked: boolean; profiles: Profile[]; selectedId: string; onSelect: (id: string) => void; next: () => void }) {
  const expectedKind = mode === 'software_test' ? 'software' : 'mock';
  const selected = profiles.some((profile) => profile.profile_id === selectedId && profile.kind === expectedKind);
  return <>
    <div className="page-heading"><span className="eyebrow">02 / 配置</span><h1>选择有据可查的配置。</h1><p>当前{mode === 'mock' ? '演示仅使用 MOCK 配置' : '真实软件测试仅使用软件配置'}。菜单中出现的 D1 型号，不表示已经完成适配。</p></div>
    {!selected && <div className="notice warning">{mode === 'software_test' ? '尚无可执行的软件配置；请等待可信工件及软件配置加入，不能降级为 MOCK。' : '尚无可执行的演示配置。'}</div>}
    <div className="profile-grid">{profiles.map((profile) => <article key={profile.profile_id} className={`profile-card ${selectedId === profile.profile_id ? 'selected' : ''} ${profile.kind === 'hardware' ? 'hardware-profile' : ''}`}>
      <div className="profile-title">{profile.kind === 'software' ? <span className="software-profile-icon" aria-hidden="true">▣</span> : <RobotMark variant={profile.variant} />}<span className={`tag ${profile.kind === 'mock' ? 'mock-tag' : profile.kind === 'software' ? 'software-tag' : 'neutral-tag'}`}>{profile.kind === 'mock' ? 'MOCK' : profile.kind === 'software' ? '软件测试 · 未接真机' : '真实型号候选'}</span></div>
      <h2>{profile.name}</h2>
      <ul className="capability-list">{Object.entries(profile.capabilities).map(([name, capability]) => <li key={name}><div><strong>{capabilityNames[name] ?? name}</strong><span className="capability-status">{capability.status}</span></div><p>{capability.reason}</p>{capability.evidence_refs.length > 0 && <small>来源：{capability.evidence_refs.join('、')}</small>}</li>)}</ul>
      {profile.unverified_reason && <p className="unverified-reason">{profile.unverified_reason}</p>}
      <button type="button" className="profile-select" disabled={locked || profile.kind !== expectedKind} aria-label={`选择 ${profile.name}`} aria-pressed={selectedId === profile.profile_id} onClick={() => onSelect(profile.profile_id)}>{profile.kind === expectedKind ? selectedId === profile.profile_id ? '已选择当前配置' : '选择当前配置' : profile.kind === 'hardware' ? '尚未实施 · 不可执行' : '与当前模式不匹配'}</button>
      <details><summary>配置与来源详情</summary><dl><dt>配置 ID</dt><dd>{profile.profile_id}</dd><dt>SDK 家族</dt><dd>{profile.sdk_family ?? '未知 / 不使用 SDK'}</dd><dt>固件范围</dt><dd>{profile.firmware_rules?.join('、') ?? '未知'}</dd><dt>来源引用</dt><dd>{profile.evidence_refs.join('、') || '无'}</dd></dl></details>
    </article>)}</div>
    <div className="page-actions"><span>真实 D1 配置的能力将逐项验证后开放。</span><button className="primary" type="button" disabled={!selected} onClick={next}>下一步：执行电脑 <span aria-hidden="true">→</span></button></div>
  </>;
}
