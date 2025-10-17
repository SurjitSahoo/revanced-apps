#!/usr/bin/env python3
"""
Pipeline status logger for tracking releases and patches
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

LOGS_DIR = Path("logs")
PIPELINE_LOG = LOGS_DIR / "pipeline_history.json"
RELEASES_LOG = LOGS_DIR / "release_history.json"

def ensure_logs_dir():
    """Ensure logs directory exists"""
    LOGS_DIR.mkdir(exist_ok=True)

def load_pipeline_history() -> list:
    """Load pipeline history"""
    if PIPELINE_LOG.exists():
        with open(PIPELINE_LOG, 'r') as f:
            return json.load(f)
    return []

def load_release_history() -> list:
    """Load release history"""
    if RELEASES_LOG.exists():
        with open(RELEASES_LOG, 'r') as f:
            return json.load(f)
    return []

def log_pipeline_run(
    trigger: str,
    download_results: Optional[Dict] = None,
    patch_results: Optional[Dict] = None,
    release_info: Optional[Dict] = None,
    issues_created: Optional[Dict] = None,
    status: str = "success"
):
    """Log a complete pipeline run"""
    ensure_logs_dir()
    
    # Get pipeline metadata
    pipeline_data = {
        "timestamp": datetime.now().isoformat(),
        "run_id": os.environ.get('GITHUB_RUN_ID', 'local'),
        "run_number": os.environ.get('GITHUB_RUN_NUMBER', '0'),
        "workflow": os.environ.get('GITHUB_WORKFLOW', 'Manual'),
        "trigger": trigger,  # 'schedule', 'manual', 'config_change'
        "commit_sha": os.environ.get('GITHUB_SHA', 'unknown'),
        "actor": os.environ.get('GITHUB_ACTOR', 'local'),
        "status": status,  # 'success', 'partial', 'failed'
        "results": {
            "downloads": download_results,
            "patches": patch_results,
            "release": release_info,
            "issues": issues_created
        }
    }
    
    # Add summary statistics
    if download_results and patch_results:
        pipeline_data["summary"] = {
            "apps_attempted": len(download_results.get('successful', [])) + len(download_results.get('failed', [])),
            "downloads_successful": len(download_results.get('successful', [])),
            "downloads_failed": len(download_results.get('failed', [])),
            "patches_successful": len(patch_results.get('successful', [])),
            "patches_failed": len(patch_results.get('failed', [])),
            "release_created": bool(release_info),
            "issues_created": len(issues_created.get('created', [])) if issues_created else 0
        }
    
    # Load existing history and append
    history = load_pipeline_history()
    history.append(pipeline_data)
    
    # Keep only last 50 runs to prevent file getting too large
    if len(history) > 50:
        history = history[-50:]
    
    # Save updated history
    with open(PIPELINE_LOG, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"✓ Pipeline run logged: {pipeline_data['timestamp']}")
    return pipeline_data

def log_release_created(release_info: Dict, patch_results: Dict):
    """Log a successful release"""
    ensure_logs_dir()
    
    release_data = {
        "timestamp": datetime.now().isoformat(),
        "tag": release_info.get('tag'),
        "url": release_info.get('url'),
        "run_id": os.environ.get('GITHUB_RUN_ID', 'local'),
        "apps_released": [],
        "total_size_mb": 0,
        "architecture_variants": {}
    }
    
    # Analyze released apps
    for item in patch_results.get('successful', []):
        app_name = item['app']['name']
        apk_path = Path(item['output_apk'])
        
        if apk_path.exists():
            size_mb = apk_path.stat().st_size / (1024*1024)
            
            # Extract architecture from filename
            arch = "universal"
            if "-armeabi-v7a-" in apk_path.name:
                arch = "armeabi-v7a"
            elif "-arm64-v8a-" in apk_path.name:
                arch = "arm64-v8a"
            elif "-x86_64-" in apk_path.name:
                arch = "x86_64"
            
            release_data["apps_released"].append({
                "name": app_name,
                "package": item['app']['package_name'],
                "architecture": arch,
                "size_mb": round(size_mb, 1),
                "filename": apk_path.name
            })
            
            release_data["total_size_mb"] += size_mb
            
            # Count architecture variants
            if app_name not in release_data["architecture_variants"]:
                release_data["architecture_variants"][app_name] = []
            release_data["architecture_variants"][app_name].append(arch)
    
    release_data["total_size_mb"] = round(release_data["total_size_mb"], 1)
    
    # Load existing release history and append
    history = load_release_history()
    history.append(release_data)
    
    # Keep only last 30 releases
    if len(history) > 30:
        history = history[-30:]
    
    # Save updated history
    with open(RELEASES_LOG, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"✓ Release logged: {release_data['tag']} ({release_data['total_size_mb']} MB)")
    return release_data

def log_pipeline_skip(trigger: str, reason: str, pending_info: Optional[Dict] = None):
    """Log when pipeline is skipped"""
    ensure_logs_dir()
    
    # Get pipeline metadata
    pipeline_data = {
        "timestamp": datetime.now().isoformat(),
        "run_id": os.environ.get('GITHUB_RUN_ID', 'local'),
        "run_number": os.environ.get('GITHUB_RUN_NUMBER', '0'),
        "workflow": os.environ.get('GITHUB_WORKFLOW', 'Manual'),
        "trigger": trigger,  # 'schedule', 'manual', 'config_change'
        "commit_sha": os.environ.get('GITHUB_SHA', 'unknown'),
        "actor": os.environ.get('GITHUB_ACTOR', 'local'),
        "status": "skipped",
        "reason": reason,
        "results": {
            "pending_info": pending_info
        }
    }
    
    # Load existing history and append
    history = load_pipeline_history()
    history.append(pipeline_data)
    
    # Keep only last 50 runs to prevent file getting too large
    if len(history) > 50:
        history = history[-50:]
    
    # Save updated history
    with open(PIPELINE_LOG, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"✓ Pipeline skip logged: {pipeline_data['timestamp']}")
    return pipeline_data

def get_pipeline_stats():
    """Get pipeline statistics"""
    history = load_pipeline_history()
    if not history:
        return {
            "total_runs": 0, 
            "successful_runs": 0,
            "success_rate": 0,
            "recent_success_rate": 0,
            "last_run": None,
            "last_successful_release": None
        }
    
    total = len(history)
    successful = len([r for r in history if r.get('status') == 'success'])
    
    # Recent activity (last 10 runs)
    recent = history[-10:] if len(history) >= 10 else history
    recent_success = len([r for r in recent if r.get('status') == 'success'])
    
    return {
        "total_runs": total,
        "successful_runs": successful,
        "success_rate": round((successful / total) * 100, 1) if total > 0 else 0,
        "recent_success_rate": round((recent_success / len(recent)) * 100, 1) if recent else 0,
        "last_run": history[-1]['timestamp'] if history else None,
        "last_successful_release": next(
            (r['timestamp'] for r in reversed(history) if r.get('results', {}).get('release')), 
            None
        )
    }

def print_pipeline_summary():
    """Print pipeline summary"""
    stats = get_pipeline_stats()
    release_history = load_release_history()
    
    print("\n" + "="*60)
    print("📊 PIPELINE STATUS SUMMARY")
    print("="*60)
    print(f"Total Runs: {stats['total_runs']}")
    print(f"Success Rate: {stats['success_rate']}%")
    print(f"Recent Success Rate: {stats['recent_success_rate']}%")
    print(f"Last Run: {stats['last_run'] or 'Never'}")
    print(f"Last Release: {stats['last_successful_release'] or 'Never'}")
    print(f"Total Releases: {len(release_history)}")
    
    if release_history:
        latest_release = release_history[-1]
        print(f"Latest Release: {latest_release['tag']} ({latest_release['total_size_mb']} MB)")
        print(f"Apps in Latest: {len(latest_release['apps_released'])}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print_pipeline_summary()
    else:
        print("Usage: python pipeline_logger.py [summary]")
        print("This script is meant to be imported and used by other pipeline scripts")