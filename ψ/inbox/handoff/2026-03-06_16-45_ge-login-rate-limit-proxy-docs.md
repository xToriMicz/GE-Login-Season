# Handoff: GE Login — Rate Limiting, Proxy Support, Docs Overhaul

**Date**: 2026-03-06 16:45
**Context**: ~60%

## What We Did

### 1. Committed Previous Session's Work (report overhaul)
- 8 files: report_columns, run_history, error detection, staggered workers, preview status bar
- Commit: `046d6d3`

### 2. Rate Limiter + IP Block Detection
- `_RateLimiter` class — global throttle shared across all parallel workers
- Adaptive interval: 4s base + 2s per extra worker (proxy mode: 2s)
- `_is_ip_blocked()` — detects 403/429/Cloudflare blocks
- Auto backoff: 120s cooldown for ALL workers when block detected
- `get_retry_delay()` updated: rate-limit errors → 120s delay
- Commit: `e7725d4`

### 3. Proxy Support
- `--proxy-file` CLI argument + `_load_proxies()` / `_parse_proxy()`
- Formats: `host:port`, `user:pass@host:port`, `socks5://host:port`
- Round-robin assignment to parallel workers
- Sequential mode uses first proxy
- UI: proxy file picker in Options > Performance
- Settings persistence for proxy_file
- `proxies.txt.example` created
- Commit: `a4289fb`

### 4. Free Thai Proxy Investigation
- Tested 37 free Thai proxies from multiple APIs — only 1 alive (3.3s latency)
- Free proxy TH = essentially dead/unreliable
- `test_proxies.py` created — auto-fetch from APIs + test
- User decision: restart router for new IP instead of paying for proxy

### 5. IPRoyal Research
- User signed up for IPRoyal ($7.35/1GB residential)
- Decided not to pay for now — rate limiter + router restart is enough

### 6. Docs + Install Overhaul
- README.md: complete rewrite for GitHub sharing with friends
- INSTALL.bat: added `cd /d`, Chrome detection, ASCII output, Python version display
- requirements.txt: removed pyinstaller
- Commit: `73ca95b`

### 7. Git Preferences Established
- GE Login: auto commit + push without asking
- All other projects: ask before commit/push
- Saved to MEMORY.md

## Pending
- [ ] GE Login untracked: `.claude/`, `.progress.json`, `fix1.PNG`, `proxies.txt`
- [ ] `proxies.txt` has 1 working proxy (may be dead by next session) — essentially placeholder
- [ ] xxtori-oracle has accumulated untracked vault files + settings changes

## Next Session
- [ ] Test bot run with parallel 2 + rate limiter — verify no IP block
- [ ] Monitor report quality (HTML trend chart, frequent failures)
- [ ] Consider new activity if GE adds events (check ge.exe.in.th news)
- [ ] Clean up xxtori-oracle vault files (handoffs, learnings, retrospectives)

## Key Files (GE Login)
- `login.py` — rate limiter, proxy support, IP block detection
- `core/retry.py` — smart delays including 120s for rate-limit
- `utils/run_history.py` — JSON history per run
- `utils/reporter.py` — dynamic columns, trend chart
- `test_proxies.py` — proxy testing tool
- `README.md` — rewritten for GitHub
- `INSTALL.bat` — improved installer
