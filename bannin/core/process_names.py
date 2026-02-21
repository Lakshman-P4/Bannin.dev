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
    "memory compression": ("Memory Compression", "System", False),
    "memcompression": ("Memory Compression", "System", False),
    "syntpenh.exe": ("Synaptics Touchpad", "System", False),
    "syntpenh": ("Synaptics Touchpad", "System", False),

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
    "ollama.exe": ("Ollama", "AI", False),
    "ollama": ("Ollama", "AI", False),
    "ollama_llama_server.exe": ("Ollama Server", "AI", False),
    "ollama_llama_server": ("Ollama Server", "AI", False),
    "llama-server.exe": ("Llama Server", "AI", False),
    "llama-server": ("Llama Server", "AI", False),
    "lmstudio.exe": ("LM Studio", "AI", False),
    "lmstudio": ("LM Studio", "AI", False),

    # --- Edge WebView (grouped) ---
    "msedgewebview2.exe": ("Edge WebView", "System", False),

    # --- Bannin ---
    "bannin": ("Bannin Agent", "Monitoring", False),
}

# Descriptions shown on hover in the dashboard. Explains what the process is
# and why it may have many instances. Keyed by friendly_name.
PROCESS_DESCRIPTIONS = {
    # Browsers
    "Google Chrome": "Web browser by Google. Each tab, extension, and internal service runs as a separate process for stability and security — one tab crashing won't take down the rest.",
    "Microsoft Edge": "Windows default browser built on Chromium. Like Chrome, each tab and extension runs in its own process for isolation.",
    "Mozilla Firefox": "Privacy-focused browser. Uses multiple processes to separate tabs and plugins, though fewer than Chromium-based browsers.",
    "Safari": "Apple's built-in browser. Uses separate processes per tab for security sandboxing.",
    "Opera": "Chromium-based browser with built-in VPN and ad blocker. Multi-process architecture like Chrome.",
    "Brave Browser": "Privacy-first Chromium browser. Multi-process architecture — each tab is isolated.",
    "Vivaldi": "Highly customizable Chromium-based browser. Multi-process like Chrome.",
    "Arc Browser": "Modern browser with workspace organisation. Chromium multi-process architecture.",

    # Development
    "VS Code": "Microsoft's code editor. Runs extension host processes, language servers, and terminal shells as separate processes.",
    "VS Code Insiders": "Pre-release version of VS Code with early features. Same multi-process architecture.",
    "Cursor": "AI-powered code editor built on VS Code. Runs language servers, AI features, and terminals as separate processes.",
    "Windsurf": "AI code editor by Codeium. Based on VS Code architecture with additional AI processes.",
    "IntelliJ IDEA": "JetBrains Java IDE. Heavy on RAM due to code indexing and analysis.",
    "PyCharm": "JetBrains Python IDE. Uses significant RAM for code intelligence and type checking.",
    "WebStorm": "JetBrains JavaScript IDE with deep framework support.",
    "Sublime Text": "Lightweight, fast text editor. Minimal resource usage compared to Electron-based editors.",
    "Notepad++": "Fast, lightweight Windows text editor. Very low resource footprint.",
    "GitHub Desktop": "Git GUI client for managing repositories and pull requests.",
    "GitKraken": "Visual Git client with built-in merge conflict editor.",
    "Warp Terminal": "Modern terminal with AI command suggestions. Rust-based for performance.",
    "iTerm2": "macOS terminal replacement with split panes and search.",
    "Windows Terminal": "Modern Windows terminal supporting PowerShell, CMD, WSL, and custom shells.",
    "Hyper Terminal": "Electron-based terminal. Higher memory use than native terminals.",
    "Git": "Version control system. Brief process spikes during fetch, push, merge, or rebase operations.",
    "Docker": "Container runtime. Each running container appears as a subprocess.",
    "Docker Engine": "Background daemon managing all Docker containers and images.",
    "Docker Desktop": "Desktop app managing Docker Engine, with GUI and Kubernetes support.",

    # Dev runtimes
    "Python": "Python interpreter. Multiple instances usually mean several scripts, servers, or tools running simultaneously.",
    "Node.js": "JavaScript runtime. Multiple instances often come from dev servers, build tools, or microservices running in parallel.",
    "Java": "Java Virtual Machine. Each Java application runs in its own JVM instance.",
    ".NET": ".NET runtime. Each .NET application runs as a separate process.",
    "Rust (Cargo)": "Rust package manager and build system. High CPU during compilation.",
    "Rust Compiler": "The Rust compiler (rustc). CPU-intensive during builds.",
    "Go": "Go language runtime or build tool.",
    "Ruby": "Ruby interpreter. Multiple instances from different services or tools.",
    "Perl": "Perl interpreter.",
    "PHP": "PHP interpreter or development server.",
    "Deno": "Secure JavaScript/TypeScript runtime. Alternative to Node.js.",
    "Bun": "Fast JavaScript runtime, bundler, and package manager.",
    "npm": "Node.js package manager. Running during install or script execution.",
    "npx": "npm package runner for executing CLI tools without global install.",

    # Communication
    "Slack": "Team messaging app. Uses Electron — multiple processes for UI, notifications, and calls.",
    "Discord": "Voice and text chat. Electron-based with separate processes for voice, UI, and updates.",
    "Microsoft Teams": "Microsoft collaboration platform. Multiple processes for chat, calls, and background sync.",
    "Zoom": "Video conferencing app.",
    "Telegram": "Messaging app. Lightweight compared to Electron-based alternatives.",
    "WhatsApp": "Messaging app for Windows.",
    "Signal": "Encrypted messaging app.",

    # Productivity
    "Microsoft Word": "Document editor from Office suite.",
    "Microsoft Excel": "Spreadsheet editor. Can be CPU-heavy with large workbooks or formulas.",
    "Microsoft PowerPoint": "Presentation editor from Office suite.",
    "Microsoft Outlook": "Email and calendar client. Background processes for mail sync and indexing.",
    "Microsoft OneNote": "Note-taking app with cloud sync.",
    "Notion": "All-in-one workspace for notes, wikis, and project management. Electron-based.",
    "Obsidian": "Markdown-based knowledge management. Electron app with plugin system.",
    "OneDrive": "Microsoft cloud sync. Background process keeping files synchronised with the cloud.",
    "Google Drive": "Google cloud storage sync daemon.",
    "Dropbox": "Cloud file synchronisation service.",
    "iCloud": "Apple cloud sync for Windows.",

    # Media
    "Spotify": "Music streaming app. Background process for playback even when minimised.",
    "VLC Media Player": "Open-source media player supporting virtually all formats.",
    "iTunes": "Apple media player and iOS device manager.",
    "Apple Music": "Apple's music streaming service.",

    # Creative
    "Adobe Photoshop": "Professional image editing. GPU-accelerated — RAM scales with canvas size.",
    "Adobe Illustrator": "Vector graphics editor.",
    "Adobe Premiere Pro": "Professional video editing. Heavy CPU/GPU during rendering.",
    "Adobe After Effects": "Motion graphics and visual effects. Extremely RAM and GPU intensive during previews.",
    "Figma": "Collaborative design tool. Electron-based with GPU rendering.",
    "Blender": "Open-source 3D modelling, animation, and rendering. GPU-intensive during renders.",

    # Gaming
    "Steam": "Game distribution platform. Background processes for game updates and social features.",
    "Epic Games": "Epic Games Store launcher. Runs background update checks.",

    # System
    "Windows Explorer": "Windows file manager and desktop shell. Core OS process.",
    "Task Manager": "Windows system monitor for viewing processes and performance.",
    "Windows Search": "Background indexing service for instant file and app search.",
    "Start Menu": "Windows Start Menu renderer.",
    "Windows Shell": "Windows shell experience including taskbar notifications.",
    "Windows Runtime": "Broker for Windows Store apps. Multiple instances manage different app permissions.",
    "Desktop Window Manager": "Composites all windows on screen. Essential for transparency, animations, and multi-monitor.",
    "Windows Widgets": "Windows widgets panel (news, weather, stocks).",
    "Windows Settings": "Windows Settings app.",
    "Memory Compression": "Windows feature that compresses inactive memory pages to free up RAM without writing to disk.",
    "Synaptics Touchpad": "Touchpad driver and gesture support.",
    "Finder": "macOS file manager and desktop.",
    "Dock": "macOS application dock.",
    "System UI": "macOS menu bar and system indicators.",
    "Spotlight": "macOS search and indexing.",
    "WindowServer": "macOS window compositor. Handles all screen rendering.",
    "macOS Services": "Core macOS service manager (launchd).",

    # Security
    "Windows Defender": "Built-in Windows antivirus. Background scanning may spike CPU periodically.",
    "Windows Defender Network": "Network inspection service for Windows Defender.",
    "Windows Defender Scan": "Active scan process. CPU-intensive during full or quick scans.",
    "Windows Security": "Windows Security health monitoring service.",

    # AI
    "Claude Desktop": "Anthropic's Claude AI desktop app. Multiple processes handle the UI, MCP servers, and background services — each connected tool or conversation may spawn additional processes.",
    "ChatGPT": "OpenAI's ChatGPT desktop app.",
    "Copilot": "Microsoft Copilot AI assistant.",
    "Ollama": "Local LLM server. Runs models like Llama, Mistral, and others on your machine with GPU acceleration.",
    "Ollama Server": "Ollama inference process handling model loading and generation. Uses GPU VRAM proportional to model size.",
    "Llama Server": "llama.cpp inference server for local LLM hosting.",
    "LM Studio": "Desktop app for running local LLMs. Downloads, manages, and serves models with a chat UI.",

    # Edge WebView
    "Edge WebView": "Embedded browser engine used by other apps (Spotify, Teams, widgets, etc.) to render web content. Many apps share this runtime, so high instance counts are normal.",

    # Bannin
    "Bannin Agent": "This monitoring agent. Collects system metrics and serves them via API and dashboard.",
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


def get_description(friendly_name: str) -> str:
    """Return a human-readable description for a process, or empty string if unknown."""
    return PROCESS_DESCRIPTIONS.get(friendly_name, "")


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
