"""Friendly process name mapping and grouping logic.

Maps raw executable names (chrome.exe, python.exe, svchost.exe) to
human-readable names and categories. Provides grouping rules so 15
chrome.exe instances become one "Google Chrome" row, while dev
runtimes (python, node) stay split with cmdline descriptions.
"""

from __future__ import annotations

# Each entry: friendly_name, category, split (if True, keep instances separate with cmdline)
PROCESS_MAP: dict[str, tuple[str, str, bool]] = {
    # --- Browsers ---
    "chrome.exe": ("Google Chrome", "Browser", False),
    "chrome": ("Google Chrome", "Browser", False),
    "msedge.exe": ("Microsoft Edge", "Browser", False),
    "msedge": ("Microsoft Edge", "Browser", False),
    "firefox.exe": ("Mozilla Firefox", "Browser", False),
    "firefox": ("Mozilla Firefox", "Browser", False),
    "safari": ("Safari", "Browser", False),
    "brave.exe": ("Brave Browser", "Browser", False),
    "brave": ("Brave Browser", "Browser", False),
    "arc": ("Arc Browser", "Browser", False),

    # --- Development (editors, terminals) ---
    "code.exe": ("VS Code", "Development", False),
    "code": ("VS Code", "Development", False),
    "cursor.exe": ("Cursor", "Development", False),
    "cursor": ("Cursor", "Development", False),
    "windsurf.exe": ("Windsurf", "Development", False),
    "windsurf": ("Windsurf", "Development", False),
    "idea64.exe": ("IntelliJ IDEA", "Development", False),
    "pycharm64.exe": ("PyCharm", "Development", False),
    "sublime_text.exe": ("Sublime Text", "Development", False),
    "windowsterminal.exe": ("Windows Terminal", "Development", False),
    "terminal": ("Terminal", "Development", False),
    "warp": ("Warp Terminal", "Development", False),
    "iterm2": ("iTerm2", "Development", False),

    # --- Dev runtimes (split = True) ---
    "python.exe": ("Python", "Development", True),
    "python": ("Python", "Development", True),
    "python3": ("Python", "Development", True),
    "python3.exe": ("Python", "Development", True),
    "pythonw.exe": ("Python", "Development", True),
    "node.exe": ("Node.js", "Development", True),
    "node": ("Node.js", "Development", True),
    "java.exe": ("Java", "Development", True),
    "java": ("Java", "Development", True),
    "cargo.exe": ("Rust (Cargo)", "Development", True),
    "cargo": ("Rust (Cargo)", "Development", True),
    "go.exe": ("Go", "Development", True),
    "go": ("Go", "Development", True),
    "deno.exe": ("Deno", "Development", True),
    "deno": ("Deno", "Development", True),
    "bun.exe": ("Bun", "Development", True),
    "bun": ("Bun", "Development", True),

    # --- Git / Docker ---
    "git.exe": ("Git", "Development", False),
    "git": ("Git", "Development", False),
    "docker.exe": ("Docker", "Development", False),
    "docker": ("Docker", "Development", False),
    "dockerd.exe": ("Docker Engine", "Development", False),
    "dockerd": ("Docker Engine", "Development", False),

    # --- Communication ---
    "slack.exe": ("Slack", "Communication", False),
    "slack": ("Slack", "Communication", False),
    "discord.exe": ("Discord", "Communication", False),
    "discord": ("Discord", "Communication", False),
    "teams.exe": ("Microsoft Teams", "Communication", False),
    "teams": ("Microsoft Teams", "Communication", False),
    "zoom.exe": ("Zoom", "Communication", False),
    "zoom.us": ("Zoom", "Communication", False),

    # --- Productivity ---
    "winword.exe": ("Microsoft Word", "Productivity", False),
    "excel.exe": ("Microsoft Excel", "Productivity", False),
    "outlook.exe": ("Microsoft Outlook", "Productivity", False),
    "notion.exe": ("Notion", "Productivity", False),
    "notion": ("Notion", "Productivity", False),
    "obsidian.exe": ("Obsidian", "Productivity", False),
    "obsidian": ("Obsidian", "Productivity", False),
    "onedrive.exe": ("OneDrive", "Productivity", False),
    "onedrive": ("OneDrive", "Productivity", False),
    "dropbox.exe": ("Dropbox", "Productivity", False),
    "dropbox": ("Dropbox", "Productivity", False),

    # --- Media ---
    "spotify.exe": ("Spotify", "Media", False),
    "spotify": ("Spotify", "Media", False),

    # --- Security ---
    "msmpeng.exe": ("Windows Defender", "Security", False),

    # --- System (visible) ---
    "explorer.exe": ("Windows Explorer", "System", False),
    "taskmgr.exe": ("Task Manager", "System", False),
    "dwm.exe": ("Desktop Window Manager", "System", False),
    "searchhost.exe": ("Windows Search", "System", False),
    "memcompression": ("Memory Compression", "System", False),
    "msedgewebview2.exe": ("Edge WebView", "System", False),
    "finder": ("Finder", "System", False),
    "windowserver": ("WindowServer", "System", False),

    # --- AI Tools ---
    "claude.exe": ("Claude Desktop", "AI", False),
    "claude": ("Claude Desktop", "AI", False),
    "ollama.exe": ("Ollama", "AI", False),
    "ollama": ("Ollama", "AI", False),
    "ollama_llama_server.exe": ("Ollama Server", "AI", False),
    "ollama_llama_server": ("Ollama Server", "AI", False),
    "lmstudio.exe": ("LM Studio", "AI", False),
    "lmstudio": ("LM Studio", "AI", False),

    # --- Bannin ---
    "bannin": ("Bannin Agent", "Monitoring", False),
}

# Category-level descriptions used when no specific process description exists.
_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "Browser": "Web browser. Each tab and extension runs as a separate process for stability.",
    "Development": "Development tool. May spawn child processes for language servers, terminals, or build tasks.",
    "Communication": "Communication app. Electron-based apps use multiple processes for UI and notifications.",
    "Productivity": "Productivity application.",
    "Media": "Media application.",
    "System": "Operating system component.",
    "Security": "Security or antivirus service. May spike CPU during scans.",
    "AI": "AI tool or local model server. May use significant GPU/VRAM.",
    "Monitoring": "Monitoring agent collecting system metrics.",
}

# Processes to hide from the dashboard -- low-level system noise
HIDDEN_PROCESSES: set[str] = {
    # Windows
    "svchost.exe", "csrss.exe", "smss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "fontdrvhost.exe", "winlogon.exe", "sihost.exe",
    "ctfmon.exe", "conhost.exe", "dllhost.exe", "spoolsv.exe",
    "wudfhost.exe", "wmiprvse.exe", "dashost.exe", "sppextcomobj.exe",
    "smartscreen.exe", "searchindexer.exe", "searchprotocolhost.exe",
    "searchfilterhost.exe", "audiodg.exe", "usocoreworker.exe",
    "musnotificationux.exe", "compactoverlay.exe", "textinputhost.exe",
    "applicationframehost.exe", "lockapp.exe", "securityhealthsystray.exe",
    "sgrmbroker.exe", "registry", "system", "system idle process",
    "memory compression", "taskhostw.exe", "backgroundtaskhost.exe",
    "rdpclip.exe", "upfc.exe", "msiexec.exe", "wlanext.exe",
    "phoneexperiencehost.exe", "gamebarpresencewriter.exe",
    "runtimebroker.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "widgets.exe", "nissrv.exe",
    "mpcmdrun.exe", "securityhealthservice.exe",
    # macOS
    "kernel_task", "mds", "mds_stores", "mdworker", "mdworker_shared",
    "logd", "configd", "cfprefsd", "distnoted", "trustd",
    "opendirectoryd", "coreaudiod", "airportd", "watchdogd",
    "powerd", "thermald", "diskarbitrationd", "fseventsd",
    "coreservicesd", "notifyd", "usbd", "bluetoothd",
    "securityd", "loginwindow", "launchd", "dock", "systemuiserver",
    "spotlight",
    # Linux
    "kthreadd", "ksoftirqd", "kworker", "rcu_sched", "migration",
    "watchdog", "systemd-journald", "systemd-logind", "systemd-udevd",
    "dbus-daemon", "agetty", "crond", "atd",
}


def get_friendly_name(process_name: str) -> tuple[str, str]:
    """Return (friendly_name, category) for a process name.

    Falls back to the original name with 'Other' category if not mapped.
    """
    key = process_name.lower().strip()
    entry = PROCESS_MAP.get(key)
    if entry:
        return entry[0], entry[1]
    clean = key.removesuffix(".exe").replace("_", " ").replace("-", " ").title()
    return clean, "Other"


def _build_name_to_category() -> dict[str, str]:
    """Precompute reverse lookup: friendly_name -> category."""
    result: dict[str, str] = {}
    for _key, (_name, _cat, _split) in PROCESS_MAP.items():
        if _name not in result:
            result[_name] = _cat
    return result


_NAME_TO_CATEGORY: dict[str, str] = _build_name_to_category()


def get_description(friendly_name: str) -> str:
    """Return a human-readable description for a process, or empty string if unknown."""
    category = _NAME_TO_CATEGORY.get(friendly_name)
    if category:
        return _CATEGORY_DESCRIPTIONS.get(category, "")
    return ""


def is_hidden(process_name: str) -> bool:
    """Return True if this process should be hidden from the dashboard."""
    return process_name.lower().strip() in HIDDEN_PROCESSES


def should_split(process_name: str) -> bool:
    """Return True if instances of this process should be kept separate (dev runtimes)."""
    key = process_name.lower().strip()
    entry = PROCESS_MAP.get(key)
    if entry:
        return entry[2]
    return False


def get_cmdline_label(cmdline: list[str] | None, process_name: str) -> str:
    """Extract a meaningful label from a process's command line.

    For python -m module: returns the module name (e.g., "bannin.cli")
    For python script.py: returns the script name (e.g., "train.py")
    For others: returns the first non-flag argument's filename
    """
    if not cmdline or len(cmdline) < 2:
        return ""

    # Filter None entries that psutil may return for certain processes
    clean_cmdline = [a for a in cmdline if a is not None]
    if len(clean_cmdline) < 2:
        return ""

    # Handle "python -m module_name" pattern first
    try:
        m_idx = clean_cmdline.index("-m")
        if m_idx + 1 < len(clean_cmdline):
            return clean_cmdline[m_idx + 1]
    except ValueError:
        pass

    # Return the first non-flag argument's filename
    for arg in clean_cmdline[1:]:
        if arg.startswith("-"):
            continue
        parts = arg.replace("\\", "/").split("/")
        filename = parts[-1]
        if filename:
            return filename

    return ""
