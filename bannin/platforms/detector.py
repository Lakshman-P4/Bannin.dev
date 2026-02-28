from __future__ import annotations

import os
import importlib


def detect_platform() -> str:
    """Detect which platform the agent is running on.

    Returns one of: 'colab', 'kaggle', 'local'
    """
    # Check Kaggle first -- Kaggle VMs may also have google.colab installed,
    # which would cause a false positive if Colab is checked first.
    if _is_kaggle():
        return "kaggle"
    if _is_colab():
        return "colab"
    return "local"


def _is_colab() -> bool:
    # Colab sets specific env vars and has the google.colab module
    if os.environ.get("COLAB_RELEASE_TAG"):
        return True
    if os.environ.get("COLAB_GPU"):
        return True
    try:
        importlib.import_module("google.colab")
        return True
    except ImportError:
        pass
    # Colab runs on a VM with /content as the working directory.
    # Require a Colab-specific marker to avoid false positives on regular Linux.
    if os.path.isdir("/content") and (
        os.path.isdir("/root/.config/colab") or os.path.isfile("/etc/colab-env")
    ):
        return True
    return False


def _is_kaggle() -> bool:
    # Kaggle sets specific env vars
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        return True
    if os.environ.get("KAGGLE_DATA_PROXY_TOKEN"):
        return True
    # Kaggle has /kaggle directory structure
    if os.path.isdir("/kaggle/working"):
        return True
    return False
