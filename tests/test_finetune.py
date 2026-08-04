"""Tests for the LoRA / QLoRA fine-tuning infrastructure."""
from __future__ import annotations

import pytest

from algo_agents.connectors.base import ConnectorState
from algo_agents.finetune import (
    LoRAConfig,
    LoRAFineTuner,
    QLoRAConfig,
    TrainingConfig,
    count_parameters,
    demo_sentiment_examples,
    finetune_status,
    lora_supported,
    qlora_supported,
)

_TINY_MODEL = "hf-internal-testing/tiny-random-BertForSequenceClassification"


def test_lora_config_defaults_and_parsing():
    cfg = LoRAConfig()
    assert cfg.r == 8 and cfg.alpha == 16
    assert cfg.target_modules == ["query", "value"]
    from_settings = LoRAConfig.from_settings()
    assert isinstance(from_settings.target_modules, list)
    assert from_settings.target_modules  # non-empty from the "query,value" default


def test_qlora_config_validates_bits():
    assert QLoRAConfig().bits == 4
    assert QLoRAConfig(bits=8).bits == 8
    with pytest.raises(ValueError):
        QLoRAConfig(bits=5)


def test_qlora_config_embeds_lora():
    q = QLoRAConfig()
    assert isinstance(q.lora, LoRAConfig)


def test_training_config_from_settings():
    tc = TrainingConfig.from_settings()
    assert tc.num_labels == 3
    assert tc.base_model


def test_finetune_status_reports_components():
    report = {s.name: s for s in finetune_status()}
    for expected in ("peft", "transformers", "accelerate", "datasets", "lora", "qlora"):
        assert expected in report
    # peft is a declared dependency; when installed it must be READY.
    if lora_supported():
        assert report["lora"].state is ConnectorState.READY


def test_qlora_not_running_without_gpu():
    # These tests run on CPU-only CI; QLoRA must degrade, not silently "work".
    if not qlora_supported():
        report = {s.name: s for s in finetune_status()}
        assert report["qlora"].state is ConnectorState.NOT_RUNNING


def test_tuner_mode_selection():
    assert LoRAFineTuner().mode == "lora"
    assert LoRAFineTuner(qlora=QLoRAConfig()).mode == "qlora"
    # In QLoRA mode the adapter config comes from the QLoRAConfig.
    q = QLoRAConfig(lora=LoRAConfig(r=4))
    assert LoRAFineTuner(qlora=q).lora.r == 4


def test_build_quantization_config_none_for_lora():
    assert LoRAFineTuner(lora=LoRAConfig()).build_quantization_config() is None


def test_qlora_raises_clearly_without_cuda():
    tuner = LoRAFineTuner(qlora=QLoRAConfig())
    if not qlora_supported():
        with pytest.raises(RuntimeError):
            tuner.build_quantization_config()


def test_lora_reduces_trainable_params():
    pytest.importorskip("peft")
    pytest.importorskip("transformers")
    tuner = LoRAFineTuner(training=TrainingConfig(base_model=_TINY_MODEL, num_labels=3))
    model = tuner.load_model()
    trainable, total = count_parameters(model)
    assert 0 < trainable < total  # LoRA freezes the base, trains a small fraction


def test_lora_train_end_to_end(tmp_path):
    pytest.importorskip("peft")
    pytest.importorskip("transformers")
    tuner = LoRAFineTuner(
        training=TrainingConfig(
            base_model=_TINY_MODEL,
            output_dir=str(tmp_path),
            num_labels=3,
            epochs=1.0,
            batch_size=8,
        ),
        lora=LoRAConfig(),
    )
    metrics = tuner.train(demo_sentiment_examples(), output_dir=str(tmp_path))
    assert metrics["mode"] == "lora"
    assert metrics["trainable_params"] < metrics["all_params"]
    assert (tmp_path / "adapter").exists()
    from pathlib import Path

    # peft persists the adapter weights + config.
    assert any(Path(metrics["adapter_dir"]).glob("adapter_*"))
