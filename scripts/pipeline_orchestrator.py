#!/usr/bin/env python3
"""
Pipeline orchestrator with comprehensive logging
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from pipeline_logger import log_pipeline_run, print_pipeline_summary

def determine_trigger():
    """Determine what triggered the pipeline"""
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        return 'schedule'
    elif os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        return 'manual'
    elif os.environ.get('GITHUB_EVENT_NAME') == 'push':
        return 'config_change'
    else:
        return 'unknown'

def load_results_file(filepath: str):
    """Load results from JSON file if it exists"""
    path = Path(filepath)
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def log_pipeline_completion():
    """Log the completion of entire pipeline"""
    
    # Determine trigger
    trigger = determine_trigger()
    
    # Load all result files
    download_results = load_results_file("downloads/download_results.json")
    patch_results = load_results_file("output/patch_results.json")
    release_info = load_results_file("output/release_info.json")
    
    # Determine overall status
    status = "success"
    if not download_results or not patch_results:
        status = "failed"
    elif not patch_results.get('successful'):
        status = "failed"
    elif patch_results.get('failed'):
        status = "partial"
    
    # Mock issues created (would be populated by issue_manager.py)
    issues_created = {"created": [], "updated": []}
    
    # Log the complete pipeline run
    pipeline_data = log_pipeline_run(
        trigger=trigger,
        download_results=download_results,
        patch_results=patch_results,
        release_info=release_info,
        issues_created=issues_created,
        status=status
    )
    
    # Print summary
    print("\n" + "="*60)
    print("🚀 PIPELINE COMPLETION SUMMARY")
    print("="*60)
    print(f"Trigger: {trigger}")
    print(f"Status: {status.upper()}")
    print(f"Run ID: {pipeline_data['run_id']}")
    print(f"Timestamp: {pipeline_data['timestamp']}")
    
    if pipeline_data.get('summary'):
        s = pipeline_data['summary']
        print(f"\nResults:")
        print(f"  Apps Attempted: {s['apps_attempted']}")
        print(f"  Downloads: {s['downloads_successful']} ✓, {s['downloads_failed']} ✗")
        print(f"  Patches: {s['patches_successful']} ✓, {s['patches_failed']} ✗")
        print(f"  Release Created: {'Yes' if s['release_created'] else 'No'}")
        print(f"  Issues Created: {s['issues_created']}")
    
    return pipeline_data

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "summary":
            print_pipeline_summary()
        elif sys.argv[1] == "log":
            log_pipeline_completion()
        else:
            print("Usage: python pipeline_orchestrator.py [summary|log]")
    else:
        print("Usage: python pipeline_orchestrator.py [summary|log]")