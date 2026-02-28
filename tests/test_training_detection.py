"""Tests for training process detection via command-line inspection."""

from __future__ import annotations

import time

import pytest

from bannin.intelligence.training import TrainingDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_detector():
    """Reset TrainingDetector singleton before each test."""
    TrainingDetector.reset()
    yield
    TrainingDetector.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(pid: int, name: str, cmdline: list[str],
               cpu: float = 5.0, mem: float = 1.0) -> dict:
    return {
        "pid": pid,
        "name": name,
        "cpu_percent": cpu,
        "memory_percent": mem,
        "status": "running",
        "cmdline": cmdline,
    }


# ---------------------------------------------------------------------------
# Keyword / script detection
# ---------------------------------------------------------------------------

class TestKeywordDetection:
    """Verify which processes are detected as training and which are not."""

    @pytest.mark.parametrize("cmdline,should_detect", [
        # Detected: train.py script
        (["python", "train.py", "--epochs", "10"], True),
        # Detected: train_model.py (matches train_\w+)
        (["python", "scripts/train_model.py"], True),
        # Detected: finetune script
        (["python", "-u", "finetune_llm.py"], True),
        # Detected: HuggingFace run_clm
        (["python", "run_clm.py", "--model_name_or_path", "gpt2"], True),
        # Detected: --do_train flag
        (["python", "run.py", "--do_train", "--output_dir", "out"], True),
        # Detected: -m transformers framework
        (["python", "-m", "transformers", "train"], True),
        # Detected: -m accelerate launch
        (["python", "-m", "accelerate", "launch", "run.py"], True),
        # Detected: pytorch_lightning module
        (["python", "-m", "pytorch_lightning", "fit"], True),
        # Not detected: regular server
        (["python", "server.py", "--port", "8000"], False),
        # Not detected: pip install (transformers is an arg, not a module)
        (["python", "-m", "pip", "install", "transformers"], False),
        # Not detected: pytest
        (["python", "-m", "pytest", "tests/", "-v"], False),
        # Not detected: jupyter
        (["python", "-m", "jupyter", "notebook"], False),
        # Not detected: empty cmdline
        ([], False),
    ], ids=[
        "train.py",
        "train_model.py",
        "finetune_llm.py",
        "run_clm.py",
        "do_train_flag",
        "transformers_module",
        "accelerate_launch",
        "pytorch_lightning",
        "server.py",
        "pip_install",
        "pytest",
        "jupyter",
        "empty_cmdline",
    ])
    def test_detection(self, cmdline: list[str], should_detect: bool) -> None:
        det = TrainingDetector.get()
        proc = _make_proc(pid=1000, name="python.exe", cmdline=cmdline)
        det.update_from_scan([proc])
        tasks = det.get_detected_tasks()
        if should_detect:
            assert len(tasks) == 1, f"Expected detection for {cmdline}"
            assert tasks[0]["status"] == "running"
        else:
            assert len(tasks) == 0, f"False positive for {cmdline}"

    def test_non_python_ignored(self) -> None:
        """Non-python processes are never flagged, even with training keywords."""
        det = TrainingDetector.get()
        proc = _make_proc(pid=2000, name="node.exe",
                          cmdline=["node", "train.js", "--epochs", "10"])
        det.update_from_scan([proc])
        assert det.get_detected_tasks() == []


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------

class TestTaskLifecycle:

    def test_register_and_update(self) -> None:
        det = TrainingDetector.get()
        proc = _make_proc(pid=3000, name="python", cmdline=["python", "train.py"])
        det.update_from_scan([proc])
        tasks = det.get_detected_tasks()
        assert len(tasks) == 1
        assert tasks[0]["pid"] == 3000
        assert tasks[0]["status"] == "running"
        assert "train.py" in tasks[0]["name"]

        # Second scan updates metrics
        proc["cpu_percent"] = 95.0
        det.update_from_scan([proc])
        tasks = det.get_detected_tasks()
        assert tasks[0]["cpu_percent"] == 95.0

    def test_process_disappears_marks_finished(self) -> None:
        det = TrainingDetector.get()
        proc = _make_proc(pid=3001, name="python", cmdline=["python", "train.py"])
        det.update_from_scan([proc])
        assert det.get_detected_tasks()[0]["status"] == "running"

        # Process gone
        det.update_from_scan([])
        tasks = det.get_detected_tasks()
        assert len(tasks) == 1
        assert tasks[0]["status"] == "finished"

    def test_finished_evicted_after_ttl(self) -> None:
        det = TrainingDetector.get()
        det._finished_ttl = 0  # immediate eviction
        proc = _make_proc(pid=3002, name="python", cmdline=["python", "train.py"])
        det.update_from_scan([proc])
        det.update_from_scan([])  # marks finished
        # One more scan triggers TTL check
        time.sleep(0.01)
        det.update_from_scan([])
        assert det.get_detected_tasks() == []

    def test_max_tracked_bound(self) -> None:
        det = TrainingDetector.get()
        det._max_tracked = 5
        # Add 10 processes
        procs = [
            _make_proc(pid=4000 + i, name="python",
                       cmdline=["python", f"train_{i}.py"])
            for i in range(10)
        ]
        det.update_from_scan(procs)
        tasks = det.get_detected_tasks()
        assert len(tasks) <= 5

    def test_no_internal_fields_in_output(self) -> None:
        det = TrainingDetector.get()
        proc = _make_proc(pid=5000, name="python", cmdline=["python", "train.py"])
        det.update_from_scan([proc])
        tasks = det.get_detected_tasks()
        for task in tasks:
            for key in task:
                assert not key.startswith("_"), f"Internal field leaked: {key}"


# ---------------------------------------------------------------------------
# Integration with ProgressTracker.get_tasks()
# ---------------------------------------------------------------------------

class TestIntegrationWithProgressTracker:

    def test_get_tasks_includes_detected(self) -> None:
        """ProgressTracker.get_tasks() must include detected_tasks key."""
        det = TrainingDetector.get()
        proc = _make_proc(pid=6000, name="python", cmdline=["python", "train.py"])
        det.update_from_scan([proc])

        from bannin.intelligence.progress import ProgressTracker
        result = ProgressTracker.get().get_tasks()
        assert "detected_tasks" in result
        assert isinstance(result["detected_tasks"], list)
        assert len(result["detected_tasks"]) == 1
        assert result["detected_tasks"][0]["pid"] == 6000

    def test_get_tasks_empty_when_no_training(self) -> None:
        """detected_tasks is an empty list when nothing is detected."""
        from bannin.intelligence.progress import ProgressTracker
        result = ProgressTracker.get().get_tasks()
        assert "detected_tasks" in result
        assert result["detected_tasks"] == []
