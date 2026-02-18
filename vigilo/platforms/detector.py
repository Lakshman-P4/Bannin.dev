import os
import importlib


def detect_platform() -> str:
    """Detect which platform the agent is running on.

    Returns one of: 'colab', 'kaggle', 'local'
    """
    if _is_colab():
        return "colab"
    if _is_kaggle():
        return "kaggle"
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
    # Colab runs on a VM with /content as the working directory
    if os.path.isdir("/content") and os.path.isdir("/root/.config"):
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
