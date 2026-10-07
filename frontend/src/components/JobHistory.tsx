import type { JobSnapshot } from '../types';

export function JobHistory({ jobs, pending, close, restore }: { jobs: JobSnapshot[]; pending: boolean; close: () => void; restore: (id: string) => void }) {
  return <section className="job-history" aria-label="历史软件作业">
    <div className="section-row"><h2>历史软件作业</h2><button type="button" className="secondary" disabled={pending} onClick={close}>收起历史作业</button></div>
    <p>这里显示历史记录。恢复会读取原始计划与当前观测，再从结果页清理该作业拥有的遗留服务；不会自动停止其他作业。</p>
    {pending && <p role="status">正在读取作业记录…</p>}
    {!pending && jobs.length === 0 && <p>尚无软件作业记录。</p>}
    {jobs.map((item) => <article key={item.job_id}><div><strong className="mono">{item.job_id}</strong><span>历史记录 · {item.state} · software</span><small>{item.updated_at}</small></div><button className="secondary" type="button" disabled={pending} aria-label={`恢复软件作业 ${item.job_id}`} onClick={() => restore(item.job_id)}>查看与恢复</button></article>)}
  </section>;
}
