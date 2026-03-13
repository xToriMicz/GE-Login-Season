# GE Login Season Server v2.1.0

Automated daily login bot for **Granado Espada Season Server** (EXE Portal).
Login -> Activity page -> Claim rewards -> Screenshot -> Logout — per account.

> Season Server 10: 10 Mar - 9 Jun 2026

## Quick Start (Windows)

```
1. Install Python 3.10+  (tick "Add Python to PATH")
2. Install Google Chrome   (if not already installed)
3. Double-click INSTALL.bat
4. Double-click START.bat
```

That's it. The UI will open.

## Update

กดปุ่ม **Update** ใน UI ได้เลย — โปรแกรมจะดาวน์โหลดเวอร์ชันล่าสุดจาก GitHub แล้ว restart อัตโนมัติ

ไฟล์ส่วนตัว (account .txt, cookies, screenshots) จะไม่ถูกเขียนทับ

หรือ update ด้วย command line:
```bash
git pull origin main
```

## Requirements

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Google Chrome** — [Download](https://www.google.com/chrome/) (or use `--browser msedge`)
- **Windows 10/11**

### Manual Install (Developer)

```bash
pip install -r requirements.txt
playwright install chromium
python -m ui
```

## Account File

Create a text file (UTF-8), one account per line: `exe_id,password`
Lines starting with `#` or blank lines are skipped.

Example `IDGE.txt`:
```
steinz01,MyPassword123
zaitallos,MyPassword456
# this is a comment
spinnyboy2,MyPassword789
```

> **Security**: Never commit or share files containing passwords. All `.txt` files are in `.gitignore`.

## Usage

### UI Mode (Recommended)

Double-click `START.bat` or run:
```bash
python -m ui
```

Features in the UI:
- Select activity, account file, browser
- Parallel workers (1-5 browsers)
- Auto-retry on failure
- Real-time preview while bot runs
- Proxy support
- Auto Daily scheduler (run every day at set time)
- Discord webhook notifications
- Auto Retry Failed (re-run failed IDs after delay)
- Bad credentials detection (skip retry, report separately)
- One-click Update button (git pull + restart)
- View report / screenshot folder
- Maintenance (clean old files)

### Command Line

```bash
# Basic — run all accounts with default settings
python login.py

# Specify account file
python login.py --file IDGE.txt

# Headless mode (no browser window)
python login.py --file IDGE.txt --headless

# Parallel 2 workers
python login.py --file IDGE.txt --parallel 2

# Run specific range of accounts
python login.py --file IDGE.txt --start-index 10 --stop-index 25

# Use proxy
python login.py --file IDGE.txt --proxy-file proxies.txt

# List available activities
python login.py --list-activities
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--file PATH` | Account file (default: `IDGE.txt`) |
| `--activity ID` | Activity ID (default: `ge-season-daily-login`). Use `--list-activities` to see all |
| `--parallel N` | Number of parallel browser workers, 1-5 (default: 1) |
| `--proxy-file PATH` | Proxy list file (format: `host:port` or `user:pass@host:port` per line) |
| `--browser TYPE` | Browser: `chrome`, `msedge`, `chromium` (default: `chrome`) |
| `--headless` | Run browser without visible window |
| `--max-retries N` | Retry failed accounts 0-3 times (default: 1) |
| `--start-index N` | Start from account #N in the file |
| `--stop-index N` | Stop at account #N (0 = run all) |
| `--no-screenshots` | Don't save proof screenshots |
| `--no-agent` | Disable anti-detection mode (faster but riskier) |
| `--human-type` | Type like a human (slower, more natural) |
| `--keep-browser-settings` | Keep sandbox browser profile between runs |
| `--keep-open` | Don't close browser after finishing (for debugging) |
| `--preview-mode` | Save live preview screenshots for UI |

## Proxy Support

Create a `proxies.txt` file with one proxy per line:
```
# HTTP proxy
203.150.100.1:8080
user:pass@proxy.example.com:3128

# SOCKS5 proxy
socks5://103.42.57.1:1080
```

In parallel mode, proxies are assigned round-robin to workers.
See `proxies.txt.example` for more details.

## Reports

After each run, the bot generates:
- **HTML Report** — visual summary with success/fail per account, trend chart, frequent failures
- **CSV Report** — for Excel
- **Run History** — JSON per run in `reports/{activity_id}/history/`

Reports are saved to `reports/{activity_id}/` and a copy at `reports/latest_report.html`.

## Project Structure

```
GE-Login-Season/
  login.py              # CLI entry point
  ui/                   # Tkinter UI (runs login.py as subprocess)
  activities/           # Activity modules (one file per activity)
    base.py             # Activity dataclass
    ge_daily_login.py   # Season Server daily login claim logic
    daily_login_detection.py  # Slot state detection (items-ready/items-successed)
  core/                 # Core logic
    config.py           # Constants
    delays.py           # Timing/timeout values
    login_flow.py       # Login -> activity -> logout flow
    retry.py            # Retry logic + smart delay
  utils/                # Utilities
    accounts.py         # Load account files
    reporter.py         # HTML/CSV report generator
    run_history.py      # JSON run history
    console.py          # Terminal status display
    agent.py            # Anti-detection (user-agent, stealth)
    navigation.py       # Page navigation helpers
    screenshots.py      # Screenshot helpers
    notify.py           # Discord webhook notifications
    preview.py          # Live preview for UI
  INSTALL.bat           # One-click installer
  START.bat             # One-click launcher
  requirements.txt      # Python dependencies
```

## Adding New Activities

1. Create `activities/ge_<name>.py`
2. Define `activity = Activity(id="...", name="...", url="...", wait_seconds=..., run_after_goto=...)`
3. The file is auto-discovered (any `ge_*.py` in `activities/`)
4. Run with `--activity <id>`

## Anti-Detection

The bot uses stealth mode by default:
- Real Chrome browser with automation flags disabled
- Auto-detect screen size (fits any monitor), Thai locale, Bangkok timezone
- Random delays between actions
- Cookie preservation for Cloudflare

Disable with `--no-agent` if you want faster runs (not recommended).

## Cloudflare

If "Verify you are human" appears, click it manually in the browser window.
The bot waits up to 90 seconds before timing out.

## Server Protection

Built-in rate limiting prevents IP bans:
- **Rate limiter** — global throttle across all parallel workers
- **IP block detection** — auto-detects 403/429/Cloudflare blocks
- **Auto backoff** — 120s cooldown when block detected
- **Staggered workers** — parallel browsers start with random delays

If you still get blocked, restart your router to get a new IP.

## Changelog

### v2.1.0 (2026-03-13)
- **Season Server support** — adapted for GE New Season Server daily login
- **Auto-update fix** — correct repo URL, branch name, ZIP user support, error handling
- **Detection** — uses `items-ready` / `items-successed` CSS classes (Season Server style)

### v2.0.0 (2026-03-06)
- **Parallel workers** — run 2-5 browsers simultaneously (`--parallel N`)
- **Rate limiter** — global throttle prevents IP bans across workers
- **IP block detection** — auto-detects 403/429/Cloudflare + 120s backoff
- **Proxy support** — Thai IP rotation (`--proxy-file proxies.txt`)
- **Report overhaul** — dynamic columns, success rate trend chart, frequent failures
- **Run history** — JSON per run for analytics
- **Auto Daily scheduler** — set time, run every day automatically
- **Discord webhook notifications** — get notified when run completes
- **One-click Update button** — git pull from GitHub + auto-restart
