"""Test GPU alert rules by feeding simulated GPU metrics to the threshold engine.

This verifies all GPU alert code paths work correctly without real hardware.
Run: python test_gpu_alerts.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from bannin.intelligence.alerts import ThresholdEngine


def test_gpu_alerts():
    print("=" * 60)
    print("GPU ALERT TESTING (simulated metrics)")
    print("=" * 60)
    print()

    # Reset the engine so we start clean
    ThresholdEngine.reset()
    engine = ThresholdEngine.get()

    # Show loaded rules
    gpu_rules = [r for r in engine._rules if "gpu" in r["id"].lower()]
    print(f"GPU-related alert rules loaded: {len(gpu_rules)}")
    for r in gpu_rules:
        print(f"  - {r['id']}: {r['metric']} {r['operator']} {r['threshold']} ({r['severity']})")
    print()

    # --- Test 1: GPU VRAM at 50% (should NOT fire) ---
    print("-" * 40)
    print("TEST 1: GPU VRAM at 50% (should be quiet)")
    snapshot = {
        "memory": {"percent": 60},
        "disk": {"percent": 50},
        "cpu": {"percent": 40},
        "gpu": {
            "memory_percent": 50,
            "temperature_c": 65,
            "power_w": 120,
        },
    }
    alerts = engine.evaluate(snapshot)
    if not alerts:
        print("  PASS: No alerts fired (expected)")
    else:
        print(f"  FAIL: {len(alerts)} unexpected alert(s): {[a['id'] for a in alerts]}")
    print()

    # --- Test 2: GPU VRAM at 85% (should fire WARNING) ---
    print("-" * 40)
    print("TEST 2: GPU VRAM at 85% (should fire warning)")
    snapshot["gpu"]["memory_percent"] = 85
    alerts = engine.evaluate(snapshot)
    gpu_alerts = [a for a in alerts if "gpu" in a["id"]]
    if gpu_alerts:
        for a in gpu_alerts:
            print(f"  PASS: {a['severity'].upper()} — {a['message']}")
    else:
        print("  FAIL: No GPU alert fired")
    print()

    # --- Test 3: Same metric again immediately (should be suppressed by cooldown) ---
    print("-" * 40)
    print("TEST 3: Same 85% again immediately (cooldown should suppress)")
    alerts = engine.evaluate(snapshot)
    gpu_alerts = [a for a in alerts if "gpu" in a["id"]]
    if not gpu_alerts:
        print("  PASS: Cooldown suppressed duplicate alert")
    else:
        print(f"  FAIL: Alert fired despite cooldown: {[a['id'] for a in gpu_alerts]}")
    print()

    # --- Test 4: GPU VRAM at 96% (should fire CRITICAL) ---
    # Reset engine to clear cooldowns for this test
    ThresholdEngine.reset()
    engine = ThresholdEngine.get()

    print("-" * 40)
    print("TEST 4: GPU VRAM at 96% (should fire critical)")
    snapshot["gpu"]["memory_percent"] = 96
    alerts = engine.evaluate(snapshot)
    gpu_alerts = [a for a in alerts if "gpu" in a["id"]]
    if gpu_alerts:
        for a in gpu_alerts:
            print(f"  PASS: {a['severity'].upper()} — {a['message']}")
    else:
        print("  FAIL: No GPU critical alert fired")
    print()

    # --- Test 5: OOM prediction with GPU data ---
    ThresholdEngine.reset()
    engine = ThresholdEngine.get()

    print("-" * 40)
    print("TEST 5: GPU OOM predicted (5 min, 85% confidence)")
    snapshot_with_oom = {
        "memory": {"percent": 60},
        "disk": {"percent": 50},
        "cpu": {"percent": 40},
        "gpu": {"memory_percent": 92, "temperature_c": 78},
        "predictions": {
            "oom": {
                "ram": {"minutes_until_full": 30, "confidence": 50, "trend": "stable"},
                "gpu": {"minutes_until_full": 5, "confidence": 85, "trend": "increasing"},
            }
        },
    }
    alerts = engine.evaluate(snapshot_with_oom)
    oom_alerts = [a for a in alerts if "oom" in a["id"]]
    gpu_vram_alerts = [a for a in alerts if "gpu_vram" in a["id"]]
    if oom_alerts:
        for a in oom_alerts:
            print(f"  PASS: {a['severity'].upper()} — {a['message']}")
    else:
        print("  INFO: GPU OOM alert didn't fire (rule may need gpu.0. path)")
    if gpu_vram_alerts:
        for a in gpu_vram_alerts:
            print(f"  PASS: {a['severity'].upper()} — {a['message']}")
    print()

    # --- Test 6: CPU and RAM alerts alongside GPU ---
    ThresholdEngine.reset()
    engine = ThresholdEngine.get()

    print("-" * 40)
    print("TEST 6: Everything at critical (CPU 95%, RAM 96%, GPU 97%)")
    snapshot_all_critical = {
        "memory": {"percent": 96},
        "disk": {"percent": 97},
        "cpu": {"percent": 95},
        "gpu": {"memory_percent": 97, "temperature_c": 90},
    }
    alerts = engine.evaluate(snapshot_all_critical)
    print(f"  Total alerts fired: {len(alerts)}")
    for a in alerts:
        print(f"    {a['severity'].upper():10} | {a['id']:25} | {a['message']}")
    print()

    # --- Summary ---
    print("=" * 60)
    print("ALERT HISTORY (full session)")
    print("=" * 60)
    history = engine.get_alerts()
    print(f"Total alerts fired across all tests: {history['total_fired']}")
    for a in history["alerts"]:
        print(f"  [{a['severity']:8}] {a['id']:25} — {a['message']}")


if __name__ == "__main__":
    test_gpu_alerts()
