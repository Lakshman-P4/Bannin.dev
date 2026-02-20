"""Friendly process name mapping and grouping logic.

Maps raw executable names (chrome.exe, python.exe, svchost.exe) to
human-readable names and categories. Provides grouping rules so 15
chrome.exe instances become one "Google Chrome" row, while dev
runtimes (python, node) stay split with cmdline descriptions.
"""

# Each entry: friendly_name, category, split (if True, keep instances separate with cmdline)
# Split = True for dev runtimes where users care about individual instances
PROCESS_MAP = {
    # --- Browsers ---
    "chrome.exe": ("Google Chrome", "Browser", False),
    "chrome": ("Google Chrome", "Browser", False),
    "msedge.exe": ("Microsoft Edge", "Browser", False),
    "msedge": ("Microsoft Edge", "Browser", False),
    "firefox.exe": ("Mozilla Firefox", "Browser", False),
    "firefox": ("Mozilla Firefox", "Browser", False),
    "safari": ("Safari", "Browser", False),
    "opera.exe": ("Opera", "Browser", False),
    "opera": ("Opera", "Browser", False),
    "brave.exe": ("Brave Browser", "Browser", False),
    "brave": ("Brave Browser", "Browser", False),
    "vivaldi.exe": ("Vivaldi", "Browser", False),
    "vivaldi": ("Vivaldi", "Browser", False),
    "arc": ("Arc Browser", "Browser", False),

    # --- Development ---
    "code.exe": ("VS Code", "Development", False),
    "code": ("VS Code", "Development", False),
    "code - insiders.exe": ("VS Code Insiders", "Development", False),
    "cursor.exe": ("Cursor", "Development", False),
    "cursor": ("Cursor", "Development", False),
    "windsurf.exe": ("Windsurf", "Development", False),
    "windsurf": ("Windsurf", "Development", False),
    "idea64.exe": ("IntelliJ IDEA", "Development", False),
    "idea": ("IntelliJ IDEA", "Development", False),
    "pycharm64.exe": ("PyCharm", "Development", False),
    "pycharm": ("PyCharm", "Development", False),
    "webstorm64.exe": ("WebStorm", "Development", False),
    "webstorm": ("WebStorm", "Development", False),
    "sublime_text.exe": ("Sublime Text", "Development", False),
    "sublime_text": ("Sublime Text", "Development", False),
    "atom.exe": ("Atom", "Development", False),
    "atom": ("Atom", "Development", False),
    "notepad++.exe": ("Notepad++", "Development", False),
    "github desktop.exe": ("GitHub Desktop", "Development", False),
    "gitkraken.exe": ("GitKraken", "Development", False),
    "warp": ("Warp Terminal", "Development", False),
    "iterm2": ("iTerm2", "Development", False),
    "windowsterminal.exe": ("Windows Terminal", "Development", False),
    "terminal": ("Terminal", "Development", False),
    "hyper.exe": ("Hyper Terminal", "Development", False),

    # --- Dev runtimes (split = True — keep instances separate) ---
    "python.exe": ("Python", "Development", True),
    "python": ("Python", "Development", True),
    "python3": ("Python", "Development", True),
    "python3.exe": ("Python", "Development", True),
    "pythonw.exe": ("Python", "Development", True),
    "node.exe": ("Node.js", "Development", True),
    "node": ("Node.js", "Development", True),
    "java.exe": ("Java", "Development", True),
    "java": ("Java", "Development", True),
    "javaw.exe": ("Java", "Development", True),
    "cargo.exe": ("Rust (Cargo)", "Development", True),
    "cargo": ("Rust (Cargo)", "Development", True),
    "rustc.exe": ("Rust Compiler", "Development", True),
    "rustc": ("Rust Compiler", "Development", True),
    "go.exe": ("Go", "Development", True),
    "go": ("Go", "Development", True),
    "ruby.exe": ("Ruby", "Development", True),
    "ruby": ("Ruby", "Development", True),
    "perl.exe": ("Perl", "Development", True),
    "perl": ("Perl", "Development", True),
    "php.exe": ("PHP", "Development", True),
    "php": ("PHP", "Development", True),
    "dotnet.exe": (".NET", "Development", True),
    "dotnet": (".NET", "Development", True),
    "deno.exe": ("Deno", "Development", True),
    "deno": ("Deno", "Development", True),
    "bun.exe": ("Bun", "Development", True),
    "bun": ("Bun", "Development", True),
    "npm.exe": ("npm", "Development", True),
    "npm": ("npm", "Development", True),
    "npx.exe": ("npx", "Development", True),
    "npx": ("npx", "Development", True),

    # --- Git ---
    "git.exe": ("Git", "Development", False),
    "git": ("Git", "Development", False),

    # --- Communication ---
    "slack.exe": ("Slack", "Communication", False),
    "slack": ("Slack", "Communication", False),
    "discord.exe": ("Discord", "Communication", False),
    "discord": ("Discord", "Communication", False),
    "teams.exe": ("Microsoft Teams", "Communication", False),
    "teams": ("Microsoft Teams", "Communication", False),
    "zoom.exe": ("Zoom", "Communication", False),
    "zoom.us": ("Zoom", "Communication", False),
    "telegram.exe": ("Telegram", "Communication", False),
    "telegram": ("Telegram", "Communication", False),
    "whatsapp.exe": ("WhatsApp", "Communication", False),
    "signal.exe": ("Signal", "Communication", False),
    "signal": ("Signal", "Communication", False),

    # --- Productivity ---
    "winword.exe": ("Microsoft Word", "Productivity", False),
    "excel.exe": ("Microsoft Excel", "Productivity", False),
    "powerpnt.exe": ("Microsoft PowerPoint", "Productivity", False),
    "outlook.exe": ("Microsoft Outlook", "Productivity", False),
    "onenote.exe": ("Microsoft OneNote", "Productivity", False),
    "notion.exe": ("Notion", "Productivity", False),
    "notion": ("Notion", "Productivity", False),
    "obsidian.exe": ("Obsidian", "Productivity", False),
    "obsidian": ("Obsidian", "Productivity", False),

    # --- Media ---
    "spotify.exe": ("Spotify", "Media", False),
    "spotify": ("Spotify", "Media", False),
    "vlc.exe": ("VLC Media Player", "Media", False),
    "vlc": ("VLC Media Player", "Media", False),
    "itunes.exe": ("iTunes", "Media", False),
    "music": ("Apple Music", "Media", False),

    # --- Creative ---
    "photoshop.exe": ("Adobe Photoshop", "Creative", False),
    "illustrator.exe": ("Adobe Illustrator", "Creative", False),
    "premiere pro.exe": ("Adobe Premiere Pro", "Creative", False),
    "afterfx.exe": ("Adobe After Effects", "Creative", False),
    "figma.exe": ("Figma", "Creative", False),
    "figma": ("Figma", "Creative", False),
    "blender.exe": ("Blender", "Creative", False),
    "blender": ("Blender", "Creative", False),

    # --- Gaming ---
    "steam.exe": ("Steam", "Gaming", False),
    "steam": ("Steam", "Gaming", False),
    "epicgameslauncher.exe": ("Epic Games", "Gaming", False),

    # --- Docker / Containers ---
    "docker.exe": ("Docker", "Development", False),
    "docker": ("Docker", "Development", False),
    "dockerd.exe": ("Docker Engine", "Development", False),
    "dockerd": ("Docker Engine", "Development", False),
    "com.docker.backend": ("Docker Desktop", "Development", False),

    # --- Security ---
    "msmpeng.exe": ("Windows Defender", "Security", False),
    "nissrv.exe": ("Windows Defender Network", "Security", False),
    "mpcmdrun.exe": ("Windows Defender Scan", "Security", False),
    "securityhealthservice.exe": ("Windows Security", "Security", False),

    # --- Windows System (visible) ---
    "explorer.exe": ("Windows Explorer", "System", False),
    "taskmgr.exe": ("Task Manager", "System", False),
    "searchhost.exe": ("Windows Search", "System", False),
    "startmenuexperiencehost.exe": ("Start Menu", "System", False),
    "shellexperiencehost.exe": ("Windows Shell", "System", False),
    "runtimebroker.exe": ("Windows Runtime", "System", False),
    "dwm.exe": ("Desktop Window Manager", "System", False),
    "widgets.exe": ("Windows Widgets", "System", False),
    "systemsettings.exe": ("Windows Settings", "System", False),

    # --- macOS System (visible) ---
    "finder": ("Finder", "System", False),
    "dock": ("Dock", "System", False),
    "systemuiserver": ("System UI", "System", False),
    "spotlight": ("Spotlight", "System", False),
    "windowserver": ("WindowServer", "System", False),
    "launchd": ("macOS Services", "System", False),

    # --- Cloud / Sync ---
    "onedrive.exe": ("OneDrive", "Productivity", False),
    "onedrive": ("OneDrive", "Productivity", False),
    "googledrivesync.exe": ("Google Drive", "Productivity", False),
    "dropbox.exe": ("Dropbox", "Productivity", False),
    "dropbox": ("Dropbox", "Productivity", False),
    "icloud.exe": ("iCloud", "Productivity", False),

    # --- AI Tools ---
    "claude.exe": ("Claude Desktop", "AI", False),
    "claude": ("Claude Desktop", "AI", False),
    "chatgpt.exe": ("ChatGPT", "AI", False),
    "chatgpt": ("ChatGPT", "AI", False),
    "copilot.exe": ("Copilot", "AI", False),

    # --- Edge WebView (grouped) ---
    "msedgewebview2.exe": ("Edge WebView", "System", False),

    # --- Bannin ---
    "bannin": ("Bannin Agent", "Monitoring", False),
}

# Processes to hide from the dashboard — low-level system noise
HIDDEN_PROCESSES = {
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
    # macOS
    "kernel_task", "mds", "mds_stores", "mdworker", "mdworker_shared",
    "logd", "configd", "cfprefsd", "distnoted", "trustd",
    "opendirectoryd", "coreaudiod", "airportd", "watchdogd",
    "powerd", "thermald", "diskarbitrationd", "fseventsd",
    "coreservicesd", "notifyd", "usbd", "bluetoothd",
    "securityd", "loginwindow",
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
    # Clean up: strip .exe, capitalize
    clean = key.removesuffix(".exe").replace("_", " ").replace("-", " ").title()
    return clean, "Other"


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

    For python: shows the script name (e.g., "train.py")
    For node: shows the script name (e.g., "server.js")
    For others: shows the first meaningful argument
    """
    if not cmdline or len(cmdline) < 2:
        return ""

    name_lower = process_name.lower().strip()

    # Find the first argument that looks like a script/file
    for arg in cmdline[1:]:
        # Skip flags and options
        if arg.startswith("-"):
            continue
        # Skip module mode indicator
        if arg == "-m":
            continue
        # For "python -m module" pattern
        if cmdline[1] == "-m" and arg == cmdline[2] if len(cmdline) > 2 else False:
            return arg
        # Found a script or file argument
        # Extract just the filename from a path
        parts = arg.replace("\\", "/").split("/")
        filename = parts[-1]
        if filename:
            return filename

    # Check for -m module pattern
    try:
        m_idx = cmdline.index("-m")
        if m_idx + 1 < len(cmdline):
            return cmdline[m_idx + 1]
    except ValueError:
        pass

    return ""
