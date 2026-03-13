# -*- coding: utf-8 -*-
import csv
import json
from datetime import datetime
from pathlib import Path

def generate_reports(results, start_time, end_time, activity_id=None, activity=None):
    """
    สร้างรายงานทั้ง HTML และ CSV (สำหรับ Excel)
    เงื่อนไข: หากไม่มีรูปถ่าย (screenshot) ให้ถือว่า Fail เสมอ
    activity_id: ถ้ามี จะสร้าง subfolder reports/{activity_id}/
    activity: Activity object — ใช้ดึง report_columns สำหรับคอลัมน์เฉพาะกิจกรรม
    """
    # กรองสถานะใหม่: ถ้าไม่มีรูปถือว่า Fail
    for r in results:
        if r["status"] and not r.get("screenshot"):
            r["status"] = False
            if "Success" in r["message"] or not r["message"]:
                r["message"] = "Fail (No screenshot captured)"
            else:
                r["message"] = f"{r['message']} (No screenshot)"

    report_dir = Path("reports")
    if activity_id:
        report_dir = report_dir / activity_id
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = report_dir / f"report_{timestamp}.html"
    csv_file = report_dir / f"summary_{timestamp}.csv" # CSV สามารถเปิดใน Excel ได้ทันที
    
    summary = {
        "total": len(results),
        "success": len([r for r in results if r["status"]]),
        "fail": len([r for r in results if not r["status"]]),
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": str(end_time - start_time).split(".")[0]
    }

    extra_cols = getattr(activity, 'report_columns', []) if activity else []
    _generate_html(results, summary, html_file, activity_id=activity_id, extra_cols=extra_cols)
    _generate_csv(results, csv_file, extra_cols=extra_cols)

    # Copy เป็นผลลัพธ์ล่าสุด (ใน subfolder ของ activity)
    import shutil
    latest_html = report_dir / "latest_report.html"
    latest_csv = report_dir / "latest_summary.csv"
    shutil.copy2(html_file, latest_html)
    shutil.copy2(csv_file, latest_csv)

    # Copy ไปที่ reports/ root ด้วย (สำหรับ backward compat / UI View Report)
    root_dir = Path("reports")
    root_dir.mkdir(exist_ok=True)
    shutil.copy2(html_file, root_dir / "latest_report.html")
    shutil.copy2(csv_file, root_dir / "latest_summary.csv")

    print(f"\n[Reporter] สร้างรายงานเรียบร้อยแล้ว:")
    print(f" - HTML: {html_file.absolute()}")
    print(f" - CSV:  {csv_file.absolute()}")

def _generate_csv(results, file_path, extra_cols=None):
    extra_cols = extra_cols or []
    keys = ["Account ID", "Status", "Reason/Message"]
    keys += [c["label"] for c in extra_cols]
    keys += ["Time", "Screenshot Path"]
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        for r in results:
            row = [
                r["id"],
                "SUCCESS" if r["status"] else "FAILED",
                r["message"],
            ]
            for c in extra_cols:
                row.append(r.get("extra", {}).get(c["key"], "-"))
            row += [
                r["time"],
                r["screenshot"] if r["screenshot"] else "MISSING PHOTO"
            ]
            writer.writerow(row)

def _build_history_html(activity_id):
    """สร้าง HTML section สำหรับ history trend (ถ้ามีข้อมูล)"""
    try:
        from utils.run_history import load_recent_runs, get_frequent_failures
    except ImportError:
        return ""

    runs = load_recent_runs(activity_id, limit=7)
    if not runs:
        return ""

    # Trend bars
    trend_bars = ""
    for run in reversed(runs):  # เก่าสุดทางซ้าย
        rate = run.get("success_rate", 0)
        date = run.get("start_time", "")[:10]
        total = run.get("total", 0)
        success = run.get("success", 0)
        fail = run.get("fail", 0)
        bar_color = "#22c55e" if rate >= 95 else "#f59e0b" if rate >= 80 else "#ef4444"
        trend_bars += f"""
        <div style="flex: 1; text-align: center; min-width: 80px;">
            <div style="height: 80px; display: flex; align-items: flex-end; justify-content: center; margin-bottom: 6px;">
                <div style="width: 32px; height: {max(4, rate * 0.8):.0f}px; background: {bar_color}; border-radius: 4px 4px 0 0;" title="{rate}%"></div>
            </div>
            <div style="font-size: 1.1em; font-weight: 800; color: {bar_color};">{rate:.0f}%</div>
            <div style="font-size: 0.7em; color: #64748b;">{date[5:]}</div>
            <div style="font-size: 0.65em; color: #475569;">{success}/{total}</div>
        </div>"""

    # Frequent failures
    freq_fails = get_frequent_failures(activity_id, runs=7, min_fails=2)
    fail_html = ""
    if freq_fails:
        fail_items = ""
        for f in freq_fails[:10]:
            fail_items += f'<span style="background: rgba(239,68,68,0.15); color: #ef4444; padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; border: 1px solid rgba(239,68,68,0.3);">{f["id"]} ({f["fail_count"]}/{f["total_runs"]})</span>\n'
        fail_html = f"""
        <div style="background: var(--card-bg); border-radius: 12px; padding: 20px; margin-bottom: 30px;">
            <h3 style="color: #ef4444; margin: 0 0 12px 0; font-size: 0.95em;">Frequent Failures (last {len(runs)} runs)</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                {fail_items}
            </div>
        </div>"""

    return f"""
    <div style="background: var(--card-bg); border-radius: 12px; padding: 20px; margin-bottom: 30px;">
        <h3 style="color: var(--accent); margin: 0 0 15px 0; font-size: 0.95em;">Success Rate — Last {len(runs)} Runs</h3>
        <div style="display: flex; gap: 4px; align-items: flex-end;">
            {trend_bars}
        </div>
    </div>
    {fail_html}"""


def _generate_html(results, summary, file_path, activity_id=None, extra_cols=None):
    extra_cols = extra_cols or []
    col_colors = ["#f472b6", "#22c55e", "#3b82f6", "#94a3b8", "#f59e0b", "#a78bfa"]

    history_html = _build_history_html(activity_id) if activity_id else ""

    rows_html = ""
    for r in results:
        status_class = "success" if r["status"] else "fail"
        status_text = "SUCCESS" if r["status"] else "FAILED"

        if r["screenshot"]:
            ss_link = f'<a href="file:///{r["screenshot"]}" target="_blank" class="ss-link">View Photo</a>'
        else:
            ss_link = '<span class="no-ss">❌ NO PHOTO</span>'

        extra_tds = ""
        for i, c in enumerate(extra_cols):
            val = r.get("extra", {}).get(c["key"], "-")
            icon = c.get("icon", "")
            color = col_colors[i % len(col_colors)]
            extra_tds += f'<td style="text-align: center; font-weight: bold; color: {color};">{icon} {val}</td>\n'

        rows_html += f"""
        <tr class="{status_class}">
            <td>{r['id']}</td>
            <td><span class="status-pill">{status_text}</span></td>
            <td>{r['message']}</td>
            {extra_tds}
            <td>{r['time']}</td>
            <td>{ss_link}</td>
        </tr>
        """

    # สร้าง header columns แบบ dynamic
    extra_th = ""
    for i, c in enumerate(extra_cols):
        col_idx = 3 + i
        icon = c.get("icon", "")
        extra_th += f'<th onclick="sortTable({col_idx})" style="text-align: center;">{icon} {c["label"]}</th>\n'
    time_col_idx = 3 + len(extra_cols)
    ss_col_idx = time_col_idx + 1

    html_template = f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>EXE Activity Report{f" — {activity_id}" if activity_id else ""}</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text: #f8fafc;
                --success: #22c55e;
                --fail: #ef4444;
                --accent: #3b82f6;
                --warning: #f59e0b;
            }}
            body {{ font-family: 'Inter', 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 40px; line-height: 1.6; }}
            .container {{ max-width: 1100px; margin: 0 auto; }}
            h1 {{ text-align: center; color: var(--accent); margin-bottom: 30px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }}

            .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
            .summary-card {{ background: var(--card-bg); padding: 20px; border-radius: 12px; text-align: center; border-bottom: 4px solid var(--accent); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
            .summary-card.success {{ border-color: var(--success); }}
            .summary-card.fail {{ border-color: var(--fail); }}
            .summary-card .value {{ font-size: 2.2em; font-weight: 800; display: block; margin: 5px 0; }}
            .summary-card .label {{ color: #94a3b8; font-size: 0.85em; text-transform: uppercase; font-weight: 600; }}

            .table-container {{ background: var(--card-bg); border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #334155; padding: 18px 15px; text-align: left; color: #cbd5e1; font-size: 0.9em; text-transform: uppercase; cursor: pointer; position: relative; transition: background 0.2s; }}
            th:hover {{ background: #475569; }}
            th::after {{ content: '↕'; position: absolute; right: 10px; opacity: 0.3; }}
            td {{ padding: 15px; border-bottom: 1px solid #334155; font-size: 0.95em; }}

            .status-pill {{ padding: 5px 12px; border-radius: 20px; font-size: 0.75em; font-weight: 800; display: inline-block; min-width: 80px; text-align: center; }}
            tr.success td {{ color: #e2e8f0; }}
            tr.success .status-pill {{ background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.3); }}
            tr.fail td {{ color: #fecaca; }}
            tr.fail .status-pill {{ background: rgba(239, 68, 68, 0.15); color: var(--fail); border: 1px solid rgba(239, 68, 68, 0.3); }}

            .ss-link {{ color: var(--accent); text-decoration: none; font-weight: 700; border: 1px solid var(--accent); padding: 4px 10px; border-radius: 6px; font-size: 0.85em; transition: all 0.2s; }}
            .ss-link:hover {{ background: var(--accent); color: white; }}
            .no-ss {{ color: var(--warning); font-weight: bold; font-size: 0.85em; }}

            .footer {{ margin-top: 50px; text-align: center; color: #64748b; font-size: 0.85em; }}
            .fail-notif {{ color: var(--fail); font-weight: bold; font-size: 0.8em; display: block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Activity Report{f" — {activity_id}" if activity_id else ""}</h1>

            <div class="summary-grid">
                <div class="summary-card">
                    <span class="label">Total Accounts</span>
                    <span class="value">{summary['total']}</span>
                </div>
                <div class="summary-card success">
                    <span class="label">Success</span>
                    <span class="value">{summary['success']}</span>
                </div>
                <div class="summary-card fail">
                    <span class="label">Failed / No Photo</span>
                    <span class="value">{summary['fail']}</span>
                </div>
                <div class="summary-card">
                    <span class="label">Duration</span>
                    <span class="value">{summary['duration']}</span>
                </div>
            </div>

            {history_html}

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th onclick="sortTable(0)">Account ID</th>
                            <th onclick="sortTable(1)">Status</th>
                            <th onclick="sortTable(2)">Remark / Error Reason</th>
                            {extra_th}
                            <th onclick="sortTable({time_col_idx})">Time</th>
                            <th onclick="sortTable({ss_col_idx})">Proof Screenshot</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>

            <div class="footer">
                Report generated at {summary['end_time']} | Project GE Login Automation
            </div>
        </div>
        <script>
        function sortTable(n) {{
            var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
            table = document.querySelector("table");
            switching = true;
            dir = "asc";
            while (switching) {{
                switching = false;
                rows = table.rows;
                for (i = 1; i < (rows.length - 1); i++) {{
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("TD")[n];
                    y = rows[i + 1].getElementsByTagName("TD")[n];
                    
                    var xVal = x.innerText.toLowerCase();
                    var yVal = y.innerText.toLowerCase();
                    
                    if (dir == "asc") {{
                        if (xVal > yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }} else if (dir == "desc") {{
                        if (xVal < yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }}
                }}
                if (shouldSwitch) {{
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    switchcount ++;
                }} else {{
                    if (switchcount == 0 && dir == "asc") {{
                        dir = "desc";
                        switching = true;
                    }}
                }}
            }}
        }}
        </script>
    </body>
    </html>
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_template)
