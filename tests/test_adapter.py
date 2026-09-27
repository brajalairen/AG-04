"""The shipped LoRA adapter and its evidence: intact, portable, loadable from anywhere. No model is loaded here."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from satquery.settings import DEFAULT_ADAPTER, REPO_ROOT
from satquery.specialists.falcon import import_peft, resolve_adapter

ADAPTER = REPO_ROOT / DEFAULT_ADAPTER
ADAPTATION = REPO_ROOT / "experiments" / "adaptation"
RECORDED_SHA256 = "b7b1388f6c60918877c587e28707c994b64a0798a9ccf9f5c4d9fb0a31336100"


def test_the_shipped_adapter_weights_are_the_evaluated_ones():
    """The checksum recorded when the adapter was evaluated; any other weights would void the reported results."""
    digest = hashlib.sha256((ADAPTER / "adapter_model.safetensors").read_bytes()).hexdigest()
    assert digest == RECORDED_SHA256


def test_the_adapter_config_is_portable_and_matches_the_recorded_run():
    config = json.loads((ADAPTER / "adapter_config.json").read_text(encoding="utf-8"))
    assert config["base_model_name_or_path"] == "mehmetbayik/Falcon-Single-Instruction-Large"
    assert (config["peft_type"], config["r"], config["lora_alpha"], config["lora_dropout"]) == ("LORA", 8, 16, 0.05)
    recorded = json.loads((ADAPTER / "train_config.json").read_text(encoding="utf-8"))
    assert recorded["trainable_params"] == 1_572_864 and recorded["target_module_count"] == 96
    for text in (json.dumps(config), (ADAPTER / "README.md").read_text(encoding="utf-8")):
        assert ":\\" not in text and "Users" not in text  # no machine-specific path


def test_a_relative_adapter_path_resolves_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(resolve_adapter(DEFAULT_ADAPTER)) == ADAPTER


def test_hub_ids_and_absolute_paths_pass_through_unchanged(tmp_path):
    assert resolve_adapter("someone/some-adapter") == "someone/some-adapter"
    assert resolve_adapter(str(tmp_path)) == str(tmp_path)


def test_a_missing_peft_install_gives_an_instruction_not_a_traceback(monkeypatch):
    monkeypatch.setitem(sys.modules, "peft", None)  # makes `import peft` fail
    with pytest.raises(RuntimeError, match="adaptation extra"):
        import_peft()


def test_the_recorded_full_evaluation_is_the_headline_result():
    before = json.loads((ADAPTATION / "results" / "eval_before.json").read_text(encoding="utf-8"))
    after = json.loads((ADAPTATION / "results" / "eval_after.json").read_text(encoding="utf-8"))
    assert before["rows"] == after["rows"] == 1794 and before["split"] == after["split"] == "test"
    assert (before["exact_match"], after["exact_match"]) == (0.4972, 0.6633)
    assert before["adapter"] is None and after["adapter"]


def test_the_shipped_test_split_is_complete_and_balanced():
    split = ADAPTATION / "test_split"
    rows = [json.loads(line) for line in (split / "test.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1794 and {r["split"] for r in rows} == {"test"}
    assert sum(r["answer"] == "yes" for r in rows) == 897  # exactly 50%
    assert all((split / r["image_path"]).is_file() for r in rows)
    assert (split / "LICENSE-CDLA-Permissive-1.0.txt").is_file()
