import json
from pathlib import Path

from d1env import models


def test_published_contract_schemas_match_current_runtime_models():
    path = Path(__file__).resolve().parents[1] / "schemas/contracts.schema.json"
    published = json.loads(path.read_text())
    expected = {name: getattr(models, name).model_json_schema() for name in published}
    assert published == expected
