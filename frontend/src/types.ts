// API schema 1, aligned with src/d1env/models.py. Unknown observations stay null.
export type Mode = 'mock' | 'real_readonly';
export type CheckStatus = 'PASS' | 'WARN' | 'FAIL' | 'UNKNOWN' | 'SKIPPED';
export type EvidenceOrigin = 'mock' | 'local_probe' | 'docker' | 'sdk' | 'operator';
export type CapabilityStatus = 'not_implemented' | 'documented' | 'implemented' | 'integration_verified' | 'hardware_verified';
export type JobState = 'PLANNED' | 'PREFLIGHT' | 'ACQUIRING' | 'CONFIGURING' | 'STARTING' | 'VERIFYING' | 'SUCCEEDED' | 'BLOCKED' | 'FAILED' | 'CANCELLED' | 'INTERRUPTED';
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type DemoScenario = 'success' | 'verify_failure';
export interface Capability {
  declared_by_vendor: boolean;
  status: CapabilityStatus;
  evidence_refs: string[];
  reason: string;
}
export interface Profile {
  schema_version: 1;
  profile_id: string;
  name: string;
  kind: 'mock' | 'hardware';
  profile_revision: string;
  vendor: string | null;
  sdk_family: 'edu_ultra_zsl_1' | 'edu_ultra_zsl_1w' | 'maxpro_legacy' | null;
  variant: string | null;
  architectures: ('x86_64' | 'aarch64')[];
  runtime_requirements: { os_name: string | null; os_version: string | null; gpu_required: boolean; min_disk_bytes: number };
  firmware_rules: string[] | null;
  capabilities: Record<string, Capability>;
  sensor_contract: string[];
  network_requirements: ('none' | 'documented_unverified')[];
  artifact_requirements: { kind: 'mock' | 'registry' | 'local_build'; source: string | null; architecture: string | null; immutable_id: string | null }[];
  evidence_refs: string[];
  unverified_reason: string | null;
}
export interface Catalog { schema_version: 1; profiles: Profile[] }
export interface DeploymentRequest { mode: Mode; profile_id: string; target_id: 'local'; task: 'demo' | 'diagnostics'; demo_scenario?: DemoScenario }
export interface HostFacts {
  target_id: 'local'; os_name: string | null; os_version: string | null; architecture: string | null;
  docker_available: boolean | null; docker_accessible: boolean | null; compose_available: boolean | null;
  disk_free_bytes: number | null; gpu_available: boolean | null; checked_at: string;
  docker_error: 'missing' | 'daemon_stopped' | 'permission_denied' | 'timeout' | 'unknown' | null;
  interfaces: string[];
}
export interface CheckResult { code: string; status: CheckStatus; reason: string; remediation: string; origin: EvidenceOrigin; observed_at: string; evidence: Record<string, JsonValue> }
export interface Telemetry { status: CheckStatus; battery_percent: number | null; pose: number[] | null; observed_at: string | null; origin: EvidenceOrigin | null }
export interface DoctorResponse { facts: HostFacts; checks: CheckResult[]; telemetry: Telemetry }
export interface Blocker { code: string; message: string; remediation: string; field: string | null }
export interface Operation { operation_id: string; kind: 'mock_step'; label: string; timeout_s: number; reversible: boolean; required_evidence: string[] }
export interface DeploymentPlan {
  plan_id: string; mode: Mode; target_id: 'local'; profile_id: string; operations: Operation[]; required_evidence: string[];
  verified_scope: 'mock'; profile_revision: string; config_digest: string; download_bytes: number | null;
  directories: string[]; services: string[]; permissions: string[]; network: 'none';
  request: DeploymentRequest;
}
export interface PlanResolution { plan: DeploymentPlan | null; blockers: Blocker[] }
export interface JobSnapshot { job_id: string; plan_id: string; target_id: 'local'; mode: Mode; state: JobState; verified_scope: 'mock'; current_operation_id: string | null; created_at: string; updated_at: string; error_code: string | null }
export interface JobEvent { job_id: string; seq: number; timestamp: string; event_type: string; operation_id: string | null; mode: Mode; origin: 'mock'; message: string; evidence: Record<string, JsonValue> }
export interface DiagnosticReport { schema_version: 1; mode: Mode; verified_scope: 'mock'; job: Record<string, JsonValue>; checks: Record<string, JsonValue>[]; events: Record<string, JsonValue>[]; source_locks: Record<string, JsonValue>; unverified_items: string[]; redactions: string[] }
export interface ReportResponse { report: DiagnosticReport; markdown: string }
export interface SessionResponse { csrf_token: string; mode: Mode }
