"""Browser lifecycle management for xianyu-reply using CDP remote connection.

Chrome runs as an independent process with --remote-debugging-port.
CLI commands connect via CDP, so the browser survives across multiple commands.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Config
BASE_DIR = Path.home() / ".xianyu-reply"
PROFILE_DIR = BASE_DIR / "chrome-profile"
STATE_FILE = BASE_DIR / "browser-state.json"
CDP_PORT = 9222


def _ensure_dirs():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_playwright():
    """Install playwright and browser if not present."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing playwright...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "playwright>=1.40", "playwright-stealth>=1.0"],
            stdout=subprocess.DEVNULL,
        )

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        print("Installing Playwright browser (chromium)...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
        )


def _save_state(pid, port):
    """Save browser process state to disk."""
    STATE_FILE.write_text(json.dumps({"pid": pid, "port": port}))


def _load_state():
    """Load browser process state. Returns (pid, port) or (None, None)."""
    if not STATE_FILE.exists():
        return None, None
    try:
        data = json.loads(STATE_FILE.read_text())
        return data["pid"], data["port"]
    except (json.JSONDecodeError, KeyError):
        STATE_FILE.unlink(missing_ok=True)
        return None, None


def _is_process_alive(pid):
    """Check if a process with given pid is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _find_chrome():
    """Find Chrome executable path."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    # Try 'which'
    try:
        result = subprocess.run(["which", "google-chrome"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def _launch_chrome(headless=False, port=CDP_PORT):
    """Launch Chrome as an independent process with remote debugging enabled."""
    _ensure_dirs()

    # Clean stale locks
    for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = PROFILE_DIR / lock
        if p.exists():
            p.unlink(missing_ok=True)

    chrome_path = _find_chrome()
    if not chrome_path:
        raise RuntimeError("Chrome not found. Please install Google Chrome.")

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={PROFILE_DIR}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1440,900",
        "--lang=zh-CN",
    ]
    if headless:
        args.append("--headless=new")

    # Start Chrome as a detached process that survives Python exit
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _save_state(proc.pid, port)
    print(f"Chrome launched (pid={proc.pid}, port={port})", file=sys.stderr)
    return proc.pid


def _try_connect(port=CDP_PORT, timeout=10):
    """Try to connect to an existing Chrome via CDP. Returns (pw, browser, page) or raises."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=timeout * 1000)
    except Exception:
        pw.stop()
        raise

    # Get or create a page
    contexts = browser.contexts
    if contexts and contexts[0].pages:
        page = contexts[0].pages[0]
    else:
        ctx = browser.contexts[0] if contexts else browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            ignore_https_errors=True,
        )
        page = ctx.new_page()

    return pw, browser, page


# Track active CDP connection for the current process
_pw = None
_browser = None


def ensure_browser(headless=False):
    """Main entry point: connect to existing Chrome or launch a new one. Returns page."""
    global _pw, _browser

    pid, port = _load_state()

    # If we have state, check if Chrome is still alive
    if pid is not None and _is_process_alive(pid):
        try:
            _pw, _browser, page = _try_connect(port, timeout=5)
            return page
        except Exception:
            # Process alive but CDP not responding — kill and relaunch
            print("Chrome unresponsive, restarting...", file=sys.stderr)
            kill()

    # Clean up stale state
    if pid is not None and not _is_process_alive(pid):
        STATE_FILE.unlink(missing_ok=True)

    # Launch new Chrome
    _launch_chrome(headless=headless, port=CDP_PORT)

    # Wait for CDP to become available
    for i in range(15):
        time.sleep(1)
        try:
            _pw, _browser, page = _try_connect(CDP_PORT, timeout=3)
            return page
        except Exception:
            if i == 14:
                raise RuntimeError("Chrome launched but CDP connection failed after 15s")
            continue


def disconnect():
    """Disconnect CDP connection without killing Chrome."""
    global _pw, _browser
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _pw:
        try:
            _pw.stop()
        except Exception:
            pass
        _pw = None


def kill():
    """Kill the Chrome process and clean up state."""
    global _pw, _browser

    # Disconnect CDP first
    disconnect()

    pid, _ = _load_state()
    if pid is not None:
        if _is_process_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Chrome terminated (pid={pid})", file=sys.stderr)
            except OSError:
                pass
        STATE_FILE.unlink(missing_ok=True)


def get_page():
    """Get current page from active CDP connection, or None."""
    if _browser is None:
        return None
    try:
        contexts = _browser.contexts
        if contexts and contexts[0].pages:
            return contexts[0].pages[0]
    except Exception:
        pass
    return None
