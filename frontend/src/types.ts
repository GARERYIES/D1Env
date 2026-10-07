// API schema 1, aligned with src/d1env/models.py. Unknown observations stay null.
export type Mode = 'mock' | 'software_test' | 'real_readonly';
export type ExecutableMode = 'mock' | 'software_test';
export type VerifiedScope = 'mock' | 'software';
export type CheckStatus = 'PASS' | 'WARN' | 'FAIL' | 'UNKNOWN' | 'SKIPPED';
export type EvidenceOrigin = 'mock' | 'local_probe' | 'docker' | 'sdk' | 'operator';
export type CapabilityStatus = 'not_implemented' | 'documented' | 'implemented' | 'integration_verified' | 'hardware_verified';
export type JobState = 'PLANNED' | 'PREFLIGHT' | 'ACQUIRING' | 'CONFIGURING' | 'STARTING' | 'VERIFYING' | 'SUCCEEDED' | 'BLOCKED' | 'FAILED' | 'CANCELLED' | 'INTERRUPTED';
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type DemoScenario = 'success' | 'verify_failure';
export type ProbeScenario = 'success' | 'no_publisher';
export interface ArtifactRef { kind: 'mock' | 'registry' | 'local_build'; source: string | null; architecture: string | null; immutable_id: string | null }
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
  kind: 'mock' | 'software' | 'hardware';
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
  artifact_requirements: ArtifactRef[];
  evidence_refs: string[];
  unverified_reason: string | null;
}
export interface Catalog { schema_version: 1; profiles: Profile[] }
export interface DeploymentRequest { mode: Mode; profile_id: string; target_id: 'local'; task: 'demo' | 'diagnostics' | 'ros_probe'; demo_scenario?: DemoScenario; probe_scenario?: ProbeScenario }
export interface HostFacts {
  target_id: 'local'; os_name: string | null; os_version: string | null; architecture: string | null;
  docker_available: boolean | null; docker_accessible: boolean | null; compose_available: boolean | null;
  disk_free_bytes: number | null; gpu_available: boolean | null; checked_at: string;
  docker_error: 'missing' | 'daemon_stopped' | 'permission_denied' | 'timeout' | 'unknown' | null;
  interfaces: string[];
  docker_os?: string | null; docker_architecture?: string | null; docker_version?: string | null;
}
export interface CheckResult { code: string; status: CheckStatus; reason: string; remediation: string; origin: EvidenceOrigin; observed_at: string; evidence: Record<string, JsonValue> }
export interface Telemetry { status: CheckStatus; battery_percent: number | null; pose: number[] | null; observed_at: string | null; origin: EvidenceOrigin | null }
export interface DoctorResponse { facts: HostFacts; checks: CheckResult[]; telemetry: Telemetry }
export interface Blocker { code: string; message: string; remediation: string; field: string | null }
export interface Operation { operation_id: string; kind: 'mock_step' | 'docker_step'; label: string; timeout_s: number; reversible: boolean; required_evidence: string[]; artifact?: ArtifactRef | null; probe_scenario?: ProbeScenario }
export interface DeploymentPlan {
  plan_id: string; mode: Mode; target_id: 'local'; profile_id: string; operations: Operation[]; required_evidence: string[];
  verified_scope: VerifiedScope; profile_revision: string; config_digest: string; download_bytes: number | null;
  directories: string[]; services: string[]; permissions: string[]; network: 'none' | 'project_internal';
  request: DeploymentRequest;
}
export interface PlanResolution { plan: DeploymentPlan | null; blockers: Blocker[] }
export interface JobSnapshot { job_id: string; plan_id: string; target_id: 'local'; mode: Mode; state: JobState; verified_scope: VerifiedScope; current_operation_id: string | null; created_at: string; updated_at: string; error_code: string | null; current_software_ready?: boolean | null; current_health_evidence?: Record<string, JsonValue> }
export interface JobEvent { job_id: string; seq: number; timestamp: string; event_type: string; operation_id: string | null; mode: Mode; origin: 'mock' | 'docker'; message: string; evidence: Record<string, JsonValue> }
export interface DiagnosticReport { schema_version: 1; mode: Mode; verified_scope: VerifiedScope; job: Record<string, JsonValue>; checks: Record<string, JsonValue>[]; events: Record<string, JsonValue>[]; source_locks: Record<string, JsonValue>; unverified_items: string[]; redactions: string[] }
export interface ReportResponse { report: DiagnosticReport; markdown: string }
export interface SessionResponse { csrf_token: string; mode: Mode }
export interface TrustedRosBundle { schema_version: 1; filename: string; sha256: string; size_bytes: number; source: string; image_id: string; architecture: string }
export interface RosArtifactMetadata { trusted_bundle: TrustedRosBundle | null; blocked_reason: string | null }
export type RuntimeTaskState = 'RUNNING' | 'WAITING_USER' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'INTERRUPTED';
export type RuntimeStage = 'detect' | 'license' | 'download' | 'verify' | 'install' | 'native_setup' | 'start' | 'wait_ready' | 'import_image' | 'complete';
export type RuntimeUserAction = 'accept_license' | 'check_again';
export interface RuntimeTask {
  task_id: string; request_key: string; scope: 'runtime_environment'; state: RuntimeTaskState; stage: RuntimeStage;
  updated_at: string; environment_ready: boolean | null; user_action: RuntimeUserAction | null;
  evidence: Record<string, JsonValue>; events: Record<string, JsonValue>[];
  progress?: { downloaded_bytes: number; total_bytes: number } | null;
  message: string; remediation: string; error_code: string | null;
}
export interface RuntimeStatus {
  environment_ready: boolean | null; task: RuntimeTask | null;
  platform: { os: string | null; architecture: string | null; supported: boolean };
  installer: { version: string | null; sha256: string | null; size_bytes: number | null; license_url: string | null; blocked_reason?: string | null } | null;
  evidence: Record<string, JsonValue>; message: string; remediation: string; observed_at: string;
}
