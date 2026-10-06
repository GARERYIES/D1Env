import type { Profile } from '../types';

const capabilityNames: Record<string, string> = { demo: '软件演示', readonly: '只读遥测', mapping: '建图', navigation: '导航与运动' };

function RobotMark({ variant }: { variant: string | null }) {
  return <svg aria-hidden="true" viewBox="0 0 150 88" className="robot-mark"><path d="M43 30h66l10 17-11 11H49L35 44z" fill="currentColor" opacity=".18" /><path d="M43 30h66l10 17-11 11H49L35 44zM52 57l-11 12 7 14M101 58l14 12-9 13M53 32l-12-9M102 32l14-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinejoin="round" /><circle cx="108" cy="43" r="3" fill="currentColor" />{variant?.includes('1w') && <><circle cx="48" cy="79" r="7" fill="none" stroke="currentColor" strokeWidth="3" /><circle cx="108" cy="79" r="7" fill="none" stroke="currentColor" strokeWidth="3" /></>}</svg>;
}

export function RobotPage({ profiles, selectedId, onSelect, next }: { profiles: Profile[]; selectedId: string; onSelect: (id: string) => void; next: () => void }) {
  return <>
    <div className="page-heading"><span className="eyebrow">02 / 配置</span><h1>选择有据可查的配置。</h1><p>演示配置与真实型号分开。菜单中出现的型号，不表示已经完成适配。</p></div>
    <div className="profile-grid">{profiles.map((profile) => <article key={profile.profile_id} className={`profile-card ${selectedId === profile.profile_id ? 'selected' : ''} ${profile.kind === 'hardware' ? 'hardware-profile' : ''}`}>
      <div className="profile-title"><RobotMark variant={profile.variant} /><span className={`tag ${profile.kind === 'mock' ? 'mock-tag' : 'neutral-tag'}`}>{profile.kind === 'mock' ? 'MOCK' : '真实型号候选'}</span></div>
      <h2>{profile.name}</h2>
      <ul className="capability-list">{Object.entries(profile.capabilities).map(([name, capability]) => <li key={name}><div><strong>{capabilityNames[name] ?? name}</strong><span className="capability-status">{capability.status}</span></div><p>{capability.reason}</p>{capability.evidence_refs.length > 0 && <small>来源：{capability.evidence_refs.join('、')}</small>}</li>)}</ul>
      {profile.unverified_reason && <p className="unverified-reason">{profile.unverified_reason}</p>}
      <button type="button" className="profile-select" disabled={profile.kind !== 'mock'} aria-label={`选择 ${profile.name}`} aria-pressed={selectedId === profile.profile_id} onClick={() => onSelect(profile.profile_id)}>{profile.kind === 'mock' ? selectedId === profile.profile_id ? '已选择演示配置' : '选择演示配置' : '尚未实施 · 不可执行'}</button>
      <details><summary>配置与来源详情</summary><dl><dt>配置 ID</dt><dd>{profile.profile_id}</dd><dt>SDK 家族</dt><dd>{profile.sdk_family ?? '未知 / 不使用 SDK'}</dd><dt>固件范围</dt><dd>{profile.firmware_rules?.join('、') ?? '未知'}</dd><dt>来源引用</dt><dd>{profile.evidence_refs.join('、') || '无'}</dd></dl></details>
    </article>)}</div>
    <div className="page-actions"><span>真实配置的能力将逐项验证后开放。</span><button className="primary" type="button" onClick={next}>下一步：执行电脑 <span aria-hidden="true">→</span></button></div>
  </>;
}
