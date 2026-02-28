"""Simulated epoch training with checkpoint saving.

Saves a checkpoint file after each completed epoch. If you kill this
mid-training, all completed epoch results are already on disk.

Usage:
    python train_epochs.py
"""

from __future__ import annotations

import json
import os
import random
import time

import bannin

CHECKPOINT_DIR = "checkpoints"
NUM_EPOCHS = 10
STEPS_PER_EPOCH = 20


def save_checkpoint(epoch: int, metrics: dict) -> str:
    """Save training state to a JSON checkpoint file."""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = os.path.join(CHECKPOINT_DIR, f"checkpoint_epoch_{epoch}.json")
    payload = {
        "epoch": epoch,
        "metrics": metrics,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def train_one_epoch(epoch: int) -> dict:
    """Simulate one epoch of training. Takes ~20 seconds."""
    for step in range(1, STEPS_PER_EPOCH + 1):
        total_steps = epoch * STEPS_PER_EPOCH + step
        overall_total = NUM_EPOCHS * STEPS_PER_EPOCH
        bannin.progress(
            "Fine-tuning DistilBERT",
            current=total_steps,
            total=overall_total,
        )
        time.sleep(1)

    # Simulated metrics that improve each epoch
    loss = 2.5 * (0.7 ** epoch) + random.uniform(-0.05, 0.05)
    accuracy = min(0.95, 0.4 + epoch * 0.08 + random.uniform(-0.02, 0.02))
    return {"loss": round(loss, 4), "accuracy": round(accuracy, 4)}


def main() -> None:
    print(f"Training DistilBERT for {NUM_EPOCHS} epochs ({STEPS_PER_EPOCH} steps each)")
    print(f"Checkpoints save to ./{CHECKPOINT_DIR}/\n")

    for epoch in range(NUM_EPOCHS):
        print(f"Epoch {epoch + 1}/{NUM_EPOCHS} starting...")
        metrics = train_one_epoch(epoch)
        path = save_checkpoint(epoch + 1, metrics)
        print(f"  Epoch {epoch + 1} done -- loss={metrics['loss']}, acc={metrics['accuracy']}")
        print(f"  Checkpoint saved: {path}\n")

    print("Training complete!")


if __name__ == "__main__":
    main()
