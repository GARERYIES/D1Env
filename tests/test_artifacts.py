import pytest
from pydantic import ValidationError

from d1env.models import ArtifactRef, DeploymentRequest


@pytest.mark.parametrize("identifier", ["latest", "sha256:" + "0"*64, "sha256:placeholder"])
def test_unlocked_real_artifact_identifiers_rejected(identifier):
    with pytest.raises(ValidationError):
        ArtifactRef(kind="registry",source="registry.example/test",architecture="x86_64",immutable_id=identifier)


def test_remote_target_and_string_booleans_rejected():
    with pytest.raises(ValidationError):
        DeploymentRequest(target_id="ssh://remote")
