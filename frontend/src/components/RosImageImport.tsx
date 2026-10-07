import { useState } from 'react';
import type { RosArtifactMetadata } from '../types';

export function RosImageImport({ metadata, pending, imported, locked, onImport }: { metadata: RosArtifactMetadata | null; pending: boolean; imported: boolean; locked: boolean; onImport: (file: File) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const bundle = metadata?.trusted_bundle;
  const incorrectSize = !!file && !!bundle && file.size !== bundle.size_bytes;
  return <section className="ros-import-card">
    <div className="section-row"><h2>随包软件镜像</h2><span className="tag software-tag">仅 Docker / ROS 软件</span></div>
    <p>选择发行包内的镜像文件，导入后再运行软件测试。镜像身份、完整性与架构由本地服务核验。</p>
    {bundle ? <dl className="import-facts"><div><dt>发行文件</dt><dd>{bundle.filename}</dd></div><div><dt>工件来源 / 架构</dt><dd>{bundle.source} / {bundle.architecture}</dd></div><div><dt>文件大小</dt><dd>{bundle.size_bytes.toLocaleString('zh-CN')} 字节</dd></div><div><dt>准确镜像身份</dt><dd className="mono">{bundle.image_id}</dd></div><div><dt>发行文件 SHA-256</dt><dd className="mono">{bundle.sha256}</dd></div></dl> : <div className="notice warning">{metadata?.blocked_reason ?? '正在读取可信发行工件；未取得元数据前不能导入。'}</div>}
    <label className="import-file-label">随包 ROS 镜像文件<input type="file" accept=".bundle,.tar,.gz" disabled={!bundle || pending || locked} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
    {incorrectSize && <p className="import-size-error">文件大小与发行记录不符。请选择完整的随包镜像，当前文件不会上传。</p>}
    <button className="secondary" type="button" disabled={!bundle || !file || incorrectSize || pending || locked} onClick={() => { if (file) onImport(file); }}>{pending ? '正在导入并核验镜像…' : '导入随发行包提供的 ROS 软件镜像'}</button>
    {imported && <div className="notice neutral">软件镜像已导入；还需启动测试并检查 ROS 通信。</div>}
    <p className="muted">导入使用 Docker 的高权限操作权，可能需要几分钟。请保持工作台开启；导入完成不会记为真机连接或通信检查通过。</p>
  </section>;
}
