"""Docker unit fixtures; actual daemon evidence is recorded separately."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from d1env.docker.client import INFO_FORMAT, DockerClient, DockerCommand
from d1env.docker.executor import DockerExecutor
from d1env.models import ArtifactRef, ExecutionContext, Operation

IMAGE_ID = "sha256:" + "1" * 64
JOB_ID = "a" * 32
PLAN_ID = "b" * 64
PUB_ID = "c" * 64
SUB_ID = "d" * 64
NETWORK_ID = "e" * 64


def artifact():
    return ArtifactRef(
        kind="local_build", source="d1env/ros-probe", architecture="aarch64", immutable_id=IMAGE_ID
    )


def context(tmp_path, cancelled=lambda: False):
    return ExecutionContext(
        job_id=JOB_ID,
        plan_id=PLAN_ID,
        target_id="local",
        mode="software_test",
        work_dir=tmp_path,
        is_cancelled=cancelled,
        emit=lambda event: None,
    )


def operation(step, *, scenario="success", image=None, timeout=1.0):
    return Operation(
        operation_id=step,
        kind="docker_step",
        label=f"软件测试 {step}",
        artifact=image or artifact(),
        probe_scenario=scenario,
        timeout_s=timeout,
    )


class FixtureDocker:
    def __init__(self):
        self.containers = {}
        self.networks = {}
        self.calls = []
        self.sample_changes = {}
        self.image_source = "d1env/ros-probe"
        self.fail_up = False
        self.fail_code = None

    def run(self, args, timeout_s=5.0, is_cancelled=lambda: False):
        self.calls.append(args)
        if is_cancelled():
            return DockerCommand(args, None, "", "", cancelled=True)
        if self.fail_code:
            return DockerCommand(args, 1, "", self.fail_code)
        if args[:2] == ("info", "--format"):
            return DockerCommand(
                args, 0, json.dumps({"Architecture": "aarch64", "OSType": "linux"}), ""
            )
        if args == ("compose", "version", "--short"):
            return DockerCommand(args, 0, "2.39.1", "")
        if args[:2] == ("image", "inspect"):
            return DockerCommand(
                args,
                0,
                json.dumps(
                    [
                        {
                            "Id": IMAGE_ID,
                            "Architecture": "arm64",
                            "Os": "linux",
                            "Config": {"Labels": {"io.d1env.source": self.image_source}},
                        }
                    ]
                ),
                "",
            )
        if args[:2] == ("container", "ls"):
            values = [
                item["Id"]
                for item in self.containers.values()
                if item["Config"]["Labels"].get("io.d1env.job") == JOB_ID
            ]
            return DockerCommand(args, 0, "\n".join(values), "")
        if args[:2] == ("network", "ls"):
            values = [
                item["Id"]
                for item in self.networks.values()
                if item["Labels"].get("io.d1env.job") == JOB_ID
            ]
            return DockerCommand(args, 0, "\n".join(values), "")
        if args[:2] in {("container", "inspect"), ("network", "inspect")}:
            values = self.containers if args[0] == "container" else self.networks
            item = next(
                (
                    item
                    for item in values.values()
                    if item["Id"] == args[2] or item["Name"].lstrip("/") == args[2]
                ),
                None,
            )
            return (
                DockerCommand(args, 0, json.dumps([item]), "")
                if item
                else DockerCommand(
                    args,
                    1,
                    "",
                    f"Error response from daemon: network {args[2]} not found"
                    if args[0] == "network"
                    else "Error: No such object",
                )
            )
        if args[0] == "compose" and "up" in args:
            config = json.loads(Path(args[args.index("--file") + 1]).read_text())
            for role, identity in [("pub", PUB_ID), ("sub", SUB_ID)]:
                service = config["services"][role]
                self.containers[identity] = {
                    "Id": identity,
                    "Name": "/" + service["container_name"],
                    "Image": IMAGE_ID,
                    "State": {"Running": True},
                    "Config": {"Labels": service["labels"]},
                }
            net = config["networks"]["probe"]
            self.networks[NETWORK_ID] = {
                "Id": NETWORK_ID,
                "Name": net["name"],
                "Labels": net["labels"],
                "Internal": True,
                "Driver": "bridge",
                "Containers": {PUB_ID: {}, SUB_ID: {}},
            }
            logging_options = config["services"]["pub"]["logging"]["options"]
            invalid_logging = (
                logging_options.get("max-file") == "1"
                and logging_options.get("compress", "true") != "false"
            )
            failed = self.fail_up or invalid_logging
            return DockerCommand(
                args,
                1 if failed else 0,
                "",
                "local log compression cannot use max-file=1"
                if invalid_logging
                else "fixture up failed"
                if self.fail_up
                else "",
            )
        if args[0] == "exec":
            now = time.time()
            status = {
                "run_id": JOB_ID,
                "publisher_id": JOB_ID,
                "sample_count": 3,
                "last_sequence": 3,
                "last_sent_at": now - 0.1,
                "last_received_at": now - 0.05,
            }
            status.update(self.sample_changes)
            return DockerCommand(args, 0, json.dumps(status), "")
        if args[:2] == ("container", "stop"):
            self.containers[args[-1]]["State"]["Running"] = False
            return DockerCommand(args, 0, args[-1], "")
        if args[:2] == ("container", "rm"):
            self.containers.pop(args[-1])
            for net in self.networks.values():
                net["Containers"].pop(args[-1], None)
            return DockerCommand(args, 0, args[-1], "")
        if args[:2] == ("network", "rm"):
            self.networks.pop(args[-1])
            return DockerCommand(args, 0, args[-1], "")
        raise AssertionError(f"unexpected Docker argv: {args}")


def deployed(tmp_path):
    client = FixtureDocker()
    executor = DockerExecutor(client=client, readiness_timeout_s=0.1)
    ctx = context(tmp_path)
    for step in ["preflight", "acquire", "configure", "start"]:
        result = executor.execute(operation(step), ctx)
        assert result.status == "succeeded", result
    return executor, client, ctx


def test_fixed_compose_enforces_permissions_network_and_pinned_image(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    config = json.loads((tmp_path / "compose.json").read_text())
    assert set(config["services"]) == {"pub", "sub"}
    for service in config["services"].values():
        assert service["image"] == IMAGE_ID
        assert service["user"] == "10001:10001"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["pids_limit"] <= 128
        assert service["cpus"] <= 1.0
        assert service["mem_limit"] == "256m"
        assert service["tmpfs"] and "volumes" not in service and "ports" not in service
        assert "network_mode" not in service and service["networks"] == ["probe"]
        assert service["labels"]["io.d1env.job"] == JOB_ID
        assert service["labels"]["io.d1env.plan"] == PLAN_ID
    assert config["networks"]["probe"]["internal"] is True
    assert config["networks"]["probe"]["driver"] == "bridge"
    result = executor.verify_running(ctx, artifact())
    assert result.status == "succeeded" and result.origin == "docker"
    assert result.evidence["software_ready"] is True
    assert result.evidence["sample_count"] >= 3
    assert set(executor.cleanup(ctx)) == {PUB_ID, SUB_ID, NETWORK_ID}
    assert executor.cleanup(ctx) == []
    assert not any(
        call[:2] in {("image", "rm"), ("system", "prune")} or "down" in call
        for call in client.calls
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_count": 0},
        {"sample_count": 2},
        {"sample_count": True},
        {"last_sequence": 2},
        {"last_sent_at": None},
        {"last_received_at": None},
        {"last_sent_at": time.time() - 30},
        {"last_received_at": time.time() - 30},
        {"last_sent_at": time.time() + 30},
        {"last_received_at": time.time() + 30},
        {"last_sent_at": "not a timestamp"},
        {"last_received_at": float("nan")},
        {"run_id": "f" * 32},
        {"publisher_id": "f" * 32},
    ],
)
def test_running_is_not_readiness_without_fresh_matching_received_samples(tmp_path, changes):
    executor, client, ctx = deployed(tmp_path)
    client.sample_changes = changes
    result = executor.verify_running(ctx, artifact())
    assert result.status == "failed"
    assert result.evidence["software_ready"] is False
    assert result.error_code in {"ROS_PROBE_NOT_READY", "ROS_PROBE_INVALID_STATUS"}
    executor.cleanup(ctx)


def test_exited_container_and_missing_owned_resource_fail_readiness(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    client.containers[SUB_ID]["State"]["Running"] = False
    assert executor.verify_running(ctx, artifact()).status == "failed"
    client.containers.pop(SUB_ID)
    assert executor.verify_running(ctx, artifact()).status == "failed"
    executor.cleanup(ctx)


def test_no_publisher_is_explicit_fault_injection_and_uses_idle_role(tmp_path):
    client = FixtureDocker()
    executor = DockerExecutor(client=client, readiness_timeout_s=0.05)
    ctx = context(tmp_path)
    executor.execute(operation("configure", scenario="no_publisher"), ctx)
    config = json.loads((tmp_path / "compose.json").read_text())
    assert config["services"]["pub"]["command"] == ["idle"]
    executor.execute(operation("start", scenario="no_publisher"), ctx)
    client.sample_changes = {
        "sample_count": 0,
        "last_sequence": None,
        "run_id": None,
        "publisher_id": None,
        "last_sent_at": None,
        "last_received_at": None,
    }
    result = executor.execute(operation("verify", scenario="no_publisher", timeout=0.05), ctx)
    assert result.status == "failed" and result.evidence["fault_injection"] is True
    executor.cleanup(ctx)


def test_same_named_external_container_cannot_be_claimed_or_deleted(tmp_path):
    client = FixtureDocker()
    client.containers[PUB_ID] = {
        "Id": PUB_ID,
        "Name": f"/d1env-{JOB_ID}-pub",
        "Image": IMAGE_ID,
        "State": {"Running": True},
        "Config": {"Labels": {"user": "external"}},
    }
    executor = DockerExecutor(client=client)
    ctx = context(tmp_path)
    executor.execute(operation("configure"), ctx)
    result = executor.execute(operation("start"), ctx)
    assert result.status == "failed" and result.error_code == "DOCKER_RESOURCE_CONFLICT"
    assert executor.cleanup(ctx) == []
    assert PUB_ID in client.containers
    assert not any(call[0] == "compose" and "up" in call for call in client.calls)


def test_cleanup_rechecks_exact_identity_labels_and_preserves_foreign_network_users(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    client.containers[PUB_ID]["Config"]["Labels"]["io.d1env.plan"] = "f" * 64
    client.networks[NETWORK_ID]["Containers"]["f" * 64] = {"Name": "user-service"}
    removed = executor.cleanup(ctx)
    assert removed == [SUB_ID]
    assert PUB_ID in client.containers and NETWORK_ID in client.networks
    inventory = executor.inventory(ctx)
    assert inventory["verified_scope"] == "software"
    assert any(item["owned"] is False for item in inventory["resources"])


def test_failed_compose_still_records_partial_resources_for_owned_cleanup(tmp_path):
    client = FixtureDocker()
    client.fail_up = True
    executor = DockerExecutor(client=client)
    ctx = context(tmp_path)
    executor.execute(operation("configure"), ctx)
    result = executor.execute(operation("start"), ctx)
    assert result.status == "failed"
    assert set(executor.cleanup(ctx)) == {PUB_ID, SUB_ID, NETWORK_ID}


@pytest.mark.parametrize(
    "bad",
    [
        {"source": "user/evil;touch /tmp/pwn"},
        {"kind": "mock"},
        {"immutable_id": "sha256:" + "0" * 64},
        {"immutable_id": "latest"},
    ],
)
def test_artifact_injection_is_rejected_without_docker_calls(tmp_path, bad):
    client = FixtureDocker()
    executor = DockerExecutor(client=client)
    result = executor.execute(
        operation("acquire").model_copy(update={"artifact": artifact().model_copy(update=bad)}),
        context(tmp_path),
    )
    assert result.status == "failed"
    assert client.calls == []


@pytest.mark.parametrize(
    "change",
    [{"job_id": "../../escape"}, {"plan_id": "../escape"}, {"mode": "mock"}, {"plan_id": None}],
)
def test_context_injection_or_missing_identity_is_rejected_before_docker(tmp_path, change):
    client = FixtureDocker()
    executor = DockerExecutor(client=client)
    result = executor.execute(operation("configure"), context(tmp_path).model_copy(update=change))
    assert result.status == "failed"
    assert client.calls == []


@pytest.mark.parametrize("filename", ["compose.json", "docker-resources.json"])
def test_symlink_files_cannot_escape_job_directory(tmp_path, filename):
    outside = tmp_path.parent / f"outside-{filename}"
    outside.write_text("user data")
    (tmp_path / filename).symlink_to(outside)
    client = FixtureDocker()
    result = DockerExecutor(client=client).execute(operation("configure"), context(tmp_path))
    assert result.status == "failed"
    assert outside.read_text() == "user data"
    assert client.calls == []


def test_modified_generated_compose_is_rejected_before_start(tmp_path):
    client = FixtureDocker()
    executor = DockerExecutor(client=client)
    ctx = context(tmp_path)
    executor.execute(operation("configure"), ctx)
    payload = json.loads((tmp_path / "compose.json").read_text())
    payload["services"]["pub"]["privileged"] = True
    (tmp_path / "compose.json").write_text(json.dumps(payload))
    result = executor.execute(operation("start"), ctx)
    assert result.status == "failed" and result.error_code == "DOCKER_CONFIG_INVALID"
    assert not any("up" in call for call in client.calls)


def test_cancel_and_daemon_failure_are_explicit_results(tmp_path):
    client = FixtureDocker()
    executor = DockerExecutor(client=client)
    result = executor.execute(operation("preflight"), context(tmp_path, cancelled=lambda: True))
    assert result.status == "cancelled" and result.origin == "docker"
    client.fail_code = "permission denied"
    failed = executor.execute(operation("preflight"), context(tmp_path))
    assert failed.status == "failed" and failed.error_code == "DOCKER_COMMAND_FAILED"
    assert "permission denied" in json.dumps(failed.evidence)


def make_fake_docker(tmp_path, monkeypatch, body):
    executable = tmp_path / "docker"
    executable.write_text(f"#!{sys.executable}\n" + body)
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    return executable


def test_actual_child_process_output_timeout_and_cancel_are_bounded(tmp_path, monkeypatch):
    make_fake_docker(
        tmp_path,
        monkeypatch,
        "import sys, time\nsys.stdout.write('x' * 100000)\nsys.stdout.flush()\ntime.sleep(3)\n",
    )
    client = DockerClient()
    result = client.run(("info", "--format", INFO_FORMAT), timeout_s=5.0)
    assert result.returncode == 0 and not result.timed_out
    assert len((result.stdout + result.stderr).encode()) <= 65536
    assert "TRUNCATED" in result.stdout
    timed = client.run(("info", "--format", INFO_FORMAT), timeout_s=0.05)
    assert timed.timed_out and timed.returncode is None
    result = client.run(("info", "--format", INFO_FORMAT), timeout_s=1.0, is_cancelled=lambda: True)
    assert result.cancelled and result.returncode is None


def test_client_rejects_arbitrary_shell_like_or_destructive_argv(tmp_path):
    client = DockerClient()
    for args in [
        ("system", "prune", "--force"),
        ("image", "rm", IMAGE_ID),
        ("run", "--privileged", IMAGE_ID),
        ("exec", SUB_ID, "sh", "-c", "id"),
        ("container", "rm", "same-name"),
        ("network", "rm", "same-name"),
    ]:
        with pytest.raises(ValueError):
            client.run(args)


def test_probe_payload_cannot_overwrite_readiness_or_fault_scope(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    client.sample_changes = {
        "sample_count": 0,
        "software_ready": True,
        "fault_injection": True,
        "freshness_threshold_s": 999999,
    }
    result = executor.verify_running(ctx, artifact())
    assert result.status == "failed"
    assert result.evidence["software_ready"] is False
    assert result.evidence["fault_injection"] is False
    assert result.evidence["freshness_threshold_s"] == 5
    executor.cleanup(ctx)


def test_daemon_environment_cannot_override_fixed_local_context(tmp_path, monkeypatch):
    make_fake_docker(
        tmp_path,
        monkeypatch,
        "import json, os, sys\nprint(json.dumps({'argv': sys.argv[1:], 'remote': os.environ.get('DOCKER_HOST'), 'compose': os.environ.get('COMPOSE_PROJECT_NAME')}))\n",
    )
    monkeypatch.setenv("DOCKER_HOST", "tcp://malicious.example:2375")
    monkeypatch.setenv("DOCKER_CONTEXT", "foreign")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "external-user-project")
    result = DockerClient().run(("info", "--format", INFO_FORMAT), timeout_s=5)
    payload = json.loads(result.stdout)
    assert payload["argv"][:2] == ["--context", "default"]
    assert payload["remote"] is None and payload["compose"] is None


def test_ambiguous_duplicate_status_keys_cannot_prove_readiness(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    original_run = client.run

    def return_ambiguous_status(args, timeout_s=5.0, is_cancelled=lambda: False):
        if args[0] == "exec":
            now = time.time() - 0.1
            contents = (
                '{"sample_count":0,"sample_count":3,"last_sequence":3,'
                f'"run_id":"{JOB_ID}","publisher_id":"{JOB_ID}",'
                f'"last_sent_at":{now},"last_received_at":{now}' + "}"
            )
            return DockerCommand(args, 0, contents, "")
        return original_run(args, timeout_s=timeout_s, is_cancelled=is_cancelled)

    client.run = return_ambiguous_status
    result = executor.verify_running(ctx, artifact())
    assert result.status == "failed" and result.error_code == "ROS_PROBE_INVALID_STATUS"
    assert result.evidence["software_ready"] is False
    executor.cleanup(ctx)


def test_inventory_explicitly_marks_owned_network_with_foreign_endpoint_as_preserved(tmp_path):
    executor, client, ctx = deployed(tmp_path)
    client.networks[NETWORK_ID]["Containers"]["f" * 64] = {"Name": "external-service"}
    assert executor.cleanup(ctx) == [PUB_ID, SUB_ID]
    inventory = executor.inventory(ctx)
    network = next(item for item in inventory["resources"] if item["kind"] == "network")
    assert network["owned"] is True and network["preserved"] is True
    assert network["preserved_reason"] == "foreign_or_unknown_network_endpoints"
    assert network in inventory["preserved_resources"] and network in inventory["remaining_owned"]


def test_labelled_no_publisher_fault_stays_visible_when_status_reader_times_out(tmp_path):
    client = FixtureDocker()
    executor = DockerExecutor(client=client)
    ctx = context(tmp_path)
    for step in ["configure", "start"]:
        assert executor.execute(operation(step, scenario="no_publisher"), ctx).status == "succeeded"
    original_run = client.run

    def timeout_reader(args, timeout_s=5.0, is_cancelled=lambda: False):
        if args[0] == "exec":
            return DockerCommand(args, None, "", "fixed reader timeout", timed_out=True)
        return original_run(args, timeout_s=timeout_s, is_cancelled=is_cancelled)

    client.run = timeout_reader
    result = executor.execute(operation("verify", scenario="no_publisher"), ctx)
    assert result.status == "failed" and result.error_code == "DOCKER_TIMEOUT"
    assert result.evidence["software_ready"] is False
    assert result.evidence["fault_injection"] is True
    assert result.evidence["timed_out"] is True
    executor.cleanup(ctx)


@pytest.mark.parametrize("source", [None, "external/not-the-trusted-probe"])
def test_actual_image_source_label_must_match_trusted_profile_before_acquisition(tmp_path, source):
    client = FixtureDocker()
    client.image_source = source
    executor = DockerExecutor(client=client)
    result = executor.execute(operation("acquire"), context(tmp_path))
    assert result.status == "failed" and result.error_code == "DOCKER_CONFIG_INVALID"
    assert result.evidence["software_ready"] is False
    assert not any(call[0] == "compose" and "up" in call for call in client.calls)
