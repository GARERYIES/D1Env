export const checkedAt = '2026-10-06T08:00:00Z';
const runtime = { os_name: null, os_version: null, gpu_required: false, min_disk_bytes: 104857600 };
export const catalog: Catalog = {
  schema_version: 1,
  profiles: [
    {
      schema_version: 1, profile_id: 'demo', name: '软件演示 · MOCK', kind: 'mock',
      profile_revision: 'foundation-1', vendor: null, sdk_family: null, variant: null,
      architectures: ['x86_64', 'aarch64'], runtime_requirements: runtime,
      firmware_rules: null,
      capabilities: { demo: { declared_by_vendor: false, status: 'implemented', evidence_refs: [], reason: '仅演示软件任务，不连接机器人' } },
      sensor_contract: [], network_requirements: ['none'], artifact_requirements: [], evidence_refs: ['M2'], unverified_reason: null,
    },
    {
      schema_version: 1, profile_id: 'edu-zsl-1', name: 'D1 点足候选', kind: 'hardware',
      profile_revision: 'documented-2026-10-06', vendor: 'AgibotTech', sdk_family: 'edu_ultra_zsl_1', variant: 'ZSL-1',
      architectures: ['x86_64', 'aarch64'], runtime_requirements: { ...runtime, os_name: 'Linux', os_version: '22.04' }, firmware_rules: null,
      capabilities: { readonly: { declared_by_vendor: true, status: 'documented', evidence_refs: ['S15'], reason: '高层签名有文档，适配器尚未实现' }, navigation: { declared_by_vendor: false, status: 'not_implemented', evidence_refs: [], reason: '本轮未实现导航或运动' } },
      sensor_contract: [], network_requirements: ['documented_unverified'], artifact_requirements: [], evidence_refs: ['S15'], unverified_reason: '固件范围、工件、ABI 与遥测语义未验证；禁止真实部署',
    },
  ],
};
export const doctor: DoctorResponse = {
  facts: {
    target_id: 'local', os_name: 'Darwin', os_version: '26.0', architecture: 'aarch64',
    docker_available: false, docker_accessible: false, compose_available: false,
    disk_free_bytes: 20000000000, gpu_available: null, checked_at: checkedAt,
    docker_error: 'missing', interfaces: ['lo0'],
  },
  checks: [{ code: 'DOCKER_MISSING', status: 'WARN', reason: '未找到 Docker；MOCK 不需要 Docker', remediation: '本轮可继续演示', origin: 'local_probe', observed_at: checkedAt, evidence: { docker_available: false } }],
  telemetry: { status: 'UNKNOWN', battery_percent: null, pose: null, observed_at: null, origin: null },
};
export const plan: DeploymentPlan = {
  plan_id: 'a'.repeat(64), mode: 'mock', target_id: 'local', profile_id: 'demo',
  operations: [{ operation_id: 'verify', kind: 'mock_step', label: '演示验证', timeout_s: 5, reversible: true, required_evidence: ['mock'] }],
  required_evidence: ['mock'], verified_scope: 'mock', profile_revision: 'foundation-1',
  config_digest: 'b'.repeat(64), download_bytes: null, directories: ['项目内的 MOCK 作业目录'], services: ['MOCK 演示 worker'], permissions: ['仅写项目任务数据库与 MOCK 资源'], network: 'none',
  request: { mode: 'mock', profile_id: 'demo', target_id: 'local', task: 'demo', demo_scenario: 'success' },
};
export const job: JobSnapshot = {
  job_id: 'job-1', plan_id: plan.plan_id, target_id: 'local', mode: 'mock', state: 'SUCCEEDED',
  verified_scope: 'mock', current_operation_id: null, created_at: checkedAt, updated_at: checkedAt, error_code: null,
};
export const failedJob: JobSnapshot = { ...job, state: 'FAILED', error_code: 'MOCK_READINESS_FAILED' };
export const maliciousMessage = '<script>window.__d1env_injected=true</script>';
export const failureEvents: JobEvent[] = [{ job_id: job.job_id, seq: 1, timestamp: checkedAt, event_type: 'operation_failed', operation_id: 'verify_failure', mode: 'mock', origin: 'mock', message: maliciousMessage, evidence: { error_code: 'MOCK_READINESS_FAILED', remediation: '检查演示故障注入设置后重试', test_failure: true } }];
import type { Catalog, DeploymentPlan, DoctorResponse, JobEvent, JobSnapshot } from '../../src/types';
