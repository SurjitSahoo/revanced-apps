#!/usr/bin/env python3
"""
Check if there are new versions to release based on patch analysis and previous releases
"""

import json
import sys
import os
import requests
from pathlib import Path
from datetime import datetime, timedelta

PATCH_ANALYSIS_FILE = Path("downloads/patch_analysis.json")

def load_patch_analysis():
    """Load the current patch analysis"""
    if not PATCH_ANALYSIS_FILE.exists():
        print("❌ Patch analysis file not found")
        return None
    
    with open(PATCH_ANALYSIS_FILE, 'r') as f:
        return json.load(f)

def load_release_history_from_github():
    """Load the release history from GitHub API"""
    try:
        # Get repository info from environment or use default
        repo_name = os.environ.get('GITHUB_REPOSITORY', 'SurjitSahoo/revanced-apps')
        
        # Try to get GitHub token for higher rate limits, but work without it
        github_token = os.environ.get('GITHUB_TOKEN')
        headers = {}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        # Fetch releases from GitHub API
        url = f"https://api.github.com/repos/{repo_name}/releases"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            releases = response.json()
            print(f"📋 Found {len(releases)} GitHub releases")
            return releases
        else:
            print(f"⚠️  Failed to fetch releases from GitHub API: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"⚠️  Error fetching release history from GitHub: {e}")
        return []

def get_latest_released_versions():
    """Get the latest released versions for each app from GitHub releases"""
    releases = load_release_history_from_github()
    if not releases:
        return {}
    
    # Get the most recent release
    latest_release = max(releases, key=lambda x: x['published_at'])
    
    print(f"📋 Latest release: {latest_release['tag_name']} ({latest_release['published_at']})")
    
    # Extract app versions from the release assets
    released_versions = {}
    for asset in latest_release.get('assets', []):
        filename = asset['name']
        
        # Extract package name and version from filename 
        # (e.g., com.google.android.youtube-v20.14.43-universal-patched.apk)
        import re
        package_match = re.search(r'^([^-]+)', filename)
        version_match = re.search(r'-v?(\d+\.\d+\.\d+(?:\.\d+)?)', filename)
        
        if package_match and version_match:
            package = package_match.group(1)
            version = version_match.group(1)
            
            if package not in released_versions:
                released_versions[package] = set()
            released_versions[package].add(version)
    
    return released_versions

def check_for_new_versions():
    """Check if there are new versions that need to be released"""
    patch_analysis = load_patch_analysis()
    if not patch_analysis:
        return False, "No patch analysis available"
    
    released_versions = get_latest_released_versions()
    releases = load_release_history_from_github()
    
    new_versions_found = []
    
    # Get the timestamp of the latest release for time-based checks
    latest_release_time = None
    if releases:
        latest_release = max(releases, key=lambda x: x['published_at'])
        latest_release_time = datetime.fromisoformat(latest_release['published_at'].replace('Z', '+00:00'))
    
    for package, app_info in patch_analysis.items():
        app_name = app_info['name']
        recommended_version = app_info.get('recommended_version')
        
        if not recommended_version or app_info.get('status') == 'not_supported':
            continue
        
        # Special handling for apps that support "any" version
        if app_info.get('supports_any_version') or recommended_version in ['any', 'latest']:
            # For "any" version apps, check if we've released recently (within last 7 days)
            if latest_release_time:
                # Make datetime timezone-aware for comparison
                now = datetime.now(latest_release_time.tzinfo)
                days_since_release = (now - latest_release_time).days
                
                # Check if this app was in the latest release
                app_in_latest_release = False
                if releases:
                    latest_release = max(releases, key=lambda x: x['published_at'])
                    for asset in latest_release.get('assets', []):
                        if package in asset['name']:
                            app_in_latest_release = True
                            break
                
                # If app wasn't in latest release or it's been more than 7 days, consider for release
                if not app_in_latest_release:
                    new_versions_found.append({
                        'package': package,
                        'app_name': app_name,
                        'version': 'latest',
                        'reason': f'App supporting any version was not in latest release'
                    })
                elif days_since_release >= 7:
                    new_versions_found.append({
                        'package': package,
                        'app_name': app_name,
                        'version': 'latest',
                        'reason': f'App supporting any version - last release was {days_since_release} days ago'
                    })
            else:
                # No release history, so we should release
                new_versions_found.append({
                    'package': package,
                    'app_name': app_name,
                    'version': 'latest',
                    'reason': 'No previous release found for app supporting any version'
                })
            continue
        
        # For apps with specific version requirements
        package_released_versions = released_versions.get(package, set())
        
        if recommended_version not in package_released_versions:
            new_versions_found.append({
                'package': package,
                'app_name': app_name,
                'version': recommended_version,
                'reason': f'New version {recommended_version} not in released versions: {list(package_released_versions)}'
            })
    
    return len(new_versions_found) > 0, new_versions_found

def main():
    """Main function to check if new release is needed"""
    print("🔍 Checking if new release is needed...")
    print("="*50)
    
    needs_release, details = check_for_new_versions()
    
    if needs_release:
        print("✅ New versions detected - release needed!")
        print("\n📋 New versions to release:")
        for item in details:
            print(f"  - {item['app_name']} ({item['package']}): v{item['version']}")
            print(f"    Reason: {item['reason']}")
        
        # Set GitHub Actions output
        import os
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"needs_release=true\n")
                f.write(f"new_versions_count={len(details)}\n")
        else:
            print("GITHUB_OUTPUT environment variable not found")
            print(f"needs_release=true")
            print(f"new_versions_count={len(details)}")
        
        # Save details for potential use in later steps
        output_file = Path("logs/pending_release.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump({
                'needs_release': True,
                'timestamp': datetime.now().isoformat(),
                'new_versions': details
            }, f, indent=2)
        
        sys.exit(0)  # Success - proceed with release
    else:
        print("✅ No new versions detected - skipping release")
        print("All currently supported versions have already been released.")
        
        # Set GitHub Actions output
        import os
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"needs_release=false\n")
                f.write(f"new_versions_count=0\n")
        else:
            print("GITHUB_OUTPUT environment variable not found")
            print(f"needs_release=false")
            print(f"new_versions_count=0")
        
        # Save details
        output_file = Path("logs/pending_release.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump({
                'needs_release': False,
                'timestamp': datetime.now().isoformat(),
                'reason': 'No new versions to release'
            }, f, indent=2)
        
        sys.exit(0)  # Success - but skip release

if __name__ == "__main__":
    main()