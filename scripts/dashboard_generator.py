#!/usr/bin/env python3
"""
Simple HTML dashboard generator for pipeline status
"""

import json
from pathlib import Path
from datetime import datetime
from pipeline_logger import load_pipeline_history, load_release_history, get_pipeline_stats

def generate_dashboard():
    """Generate HTML dashboard"""
    
    stats = get_pipeline_stats()
    pipeline_history = load_pipeline_history()
    release_history = load_release_history()
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>ReVanced Pipeline Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2d3748; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #2d3748; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .section h2 {{ margin-top: 0; color: #2d3748; }}
        .run-item {{ border-bottom: 1px solid #eee; padding: 10px 0; }}
        .run-item:last-child {{ border-bottom: none; }}
        .status {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
        .status.success {{ background: #c6f6d5; color: #22543d; }}
        .status.partial {{ background: #fef5e7; color: #744210; }}
        .status.failed {{ background: #fed7d7; color: #742a2a; }}
        .app-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .app-tag {{ background: #e2e8f0; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #eee; }}
        th {{ background: #f7fafc; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ReVanced Pipeline Dashboard</h1>
            <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{stats['total_runs']}</div>
                <div class="stat-label">Total Runs</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['success_rate']}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['recent_success_rate']}%</div>
                <div class="stat-label">Recent Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(release_history)}</div>
                <div class="stat-label">Total Releases</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Recent Pipeline Runs</h2>
"""
    
    # Recent runs (last 10)
    recent_runs = pipeline_history[-10:] if len(pipeline_history) >= 10 else pipeline_history
    recent_runs.reverse()  # Most recent first
    
    for run in recent_runs:
        timestamp = datetime.fromisoformat(run['timestamp']).strftime('%Y-%m-%d %H:%M')
        status_class = run['status']
        
        summary = run.get('summary', {})
        
        html += f"""
            <div class="run-item">
                <div style="display: flex; justify-content: between; align-items: center;">
                    <div style="flex: 1;">
                        <strong>Run #{run['run_number']}</strong> - {timestamp}
                        <span class="status {status_class}">{run['status'].upper()}</span>
                    </div>
                    <div style="text-align: right; font-size: 0.9em; color: #666;">
                        Trigger: {run['trigger']} | Actor: {run['actor']}
                    </div>
                </div>
"""
        
        if summary:
            html += f"""
                <div style="margin-top: 8px; font-size: 0.9em;">
                    Downloads: {summary.get('downloads_successful', 0)} ✓, {summary.get('downloads_failed', 0)} ✗ | 
                    Patches: {summary.get('patches_successful', 0)} ✓, {summary.get('patches_failed', 0)} ✗ | 
                    Release: {'Yes' if summary.get('release_created') else 'No'}
                </div>
"""
        
        html += "</div>"
    
    html += """
        </div>
        
        <div class="section">
            <h2>🎁 Recent Releases</h2>
            <table>
                <tr>
                    <th>Tag</th>
                    <th>Date</th>
                    <th>Apps</th>
                    <th>Size</th>
                    <th>Architectures</th>
                </tr>
"""
    
    # Recent releases (last 5)
    recent_releases = release_history[-5:] if len(release_history) >= 5 else release_history
    recent_releases.reverse()  # Most recent first
    
    for release in recent_releases:
        timestamp = datetime.fromisoformat(release['timestamp']).strftime('%Y-%m-%d')
        
        # Count unique apps
        unique_apps = list(set(app['name'] for app in release['apps_released']))
        app_count = len(unique_apps)
        
        # Architecture summary
        arch_summary = []
        for app_name, architectures in release['architecture_variants'].items():
            arch_summary.append(f"{app_name} ({', '.join(architectures)})")
        
        html += f"""
                <tr>
                    <td><a href="{release.get('url', '#')}" target="_blank">{release['tag']}</a></td>
                    <td>{timestamp}</td>
                    <td>{app_count}</td>
                    <td>{release['total_size_mb']} MB</td>
                    <td>{"<br>".join(arch_summary)}</td>
                </tr>
"""
    
    html += """
            </table>
        </div>
    </div>
</body>
</html>"""
    
    # Save dashboard
    dashboard_path = Path("logs/dashboard.html")
    with open(dashboard_path, 'w') as f:
        f.write(html)
    
    print(f"✓ Dashboard generated: {dashboard_path}")
    return dashboard_path

if __name__ == "__main__":
    generate_dashboard()