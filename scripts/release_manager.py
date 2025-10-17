#!/usr/bin/env python3
"""
Create GitHub release with patched APKs
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from github import Github
from pipeline_logger import log_release_created

OUTPUT_DIR = Path("output")

def is_identical_to_previous_release(repo, current_successful):
    """
    Check if the current successful patches are identical to the previous release.
    Returns True if identical (should skip release), False if different (should create release).
    """
    try:
        # Get the latest release
        releases = repo.get_releases()
        if releases.totalCount == 0:
            print("🆕 No previous releases found - proceeding with first release")
            return False
        
        latest_release = releases[0]
        print(f"🔍 Comparing with previous release: {latest_release.tag_name}")
        
        # Get assets from previous release
        previous_assets = {asset.name for asset in latest_release.get_assets()}
        
        # Get current successful APK files
        current_assets = set()
        for item in current_successful:
            output_apk_path = item.get('output_apk', '')
            if output_apk_path:
                # Extract just the filename from the path
                apk_filename = os.path.basename(output_apk_path)
                current_assets.add(apk_filename)
        
        # Debug: show what we're comparing
        print(f"🔍 Previous assets: {sorted(previous_assets)}")
        print(f"🔍 Current assets: {sorted(current_assets)}")
        
        print(f"📋 Previous release had {len(previous_assets)} assets")
        print(f"📋 Current successful patches: {len(current_assets)} assets")
        
        # Compare the sets
        if current_assets == previous_assets:
            print("✅ Asset lists are identical")
            return True
        else:
            print("📝 Asset differences detected:")
            if current_assets - previous_assets:
                print(f"   New assets: {', '.join(current_assets - previous_assets)}")
            if previous_assets - current_assets:
                print(f"   Removed assets: {', '.join(previous_assets - current_assets)}")
            return False
            
    except Exception as e:
        print(f"⚠️  Error comparing with previous release: {e}")
        print("🔄 Proceeding with release creation to be safe")
        return False

def create_release():
    """Create GitHub release with patched APKs"""
    
    # Get GitHub token
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("✗ GITHUB_TOKEN not found in environment")
        sys.exit(1)
    
    # Get repository info
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    if not repo_name:
        print("✗ GITHUB_REPOSITORY not found in environment")
        sys.exit(1)
    
    # Load patch results
    results_file = OUTPUT_DIR / "patch_results.json"
    if not results_file.exists():
        print("✗ Patch results not found")
        sys.exit(1)
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    if not results['successful']:
        print("✗ No successfully patched APKs to release")
        sys.exit(1)
    
    # Connect to GitHub
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    # Check if this release would be identical to the previous one
    if is_identical_to_previous_release(repo, results['successful']):
        print("⏭️  Skipping release - identical to previous release")
        print("🔍 Same apps with same versions were successfully patched")
        print("💡 No new content to release")
        
        # Log the skip reason
        from pipeline_logger import log_pipeline_skip
        trigger = os.environ.get('GITHUB_EVENT_NAME', 'manual')
        skip_info = {
            "successful_patches": len(results.get('successful', [])),
            "failed_patches": len(results.get('failed', [])),
            "previous_release_match": True
        }
        log_pipeline_skip(trigger, "identical_release", skip_info)
        
        sys.exit(0)
    
    # Create release tag and title
    date_str = datetime.now().strftime('%Y-%m-%d')
    tag_name = f"patched-{date_str}"
    release_title = f"Patched Apps - {datetime.now().strftime('%B %d, %Y')}"
    
    # Check if release already exists
    try:
        existing_release = repo.get_release(tag_name)
        print(f"Release {tag_name} already exists. Deleting and recreating...")
        existing_release.delete_release()
    except:
        pass  # Release doesn't exist, continue
    
    # Build release notes
    release_notes = f"""# ReVanced Patched Apps
    
## 📊 Summary
- **Successfully Patched:** {len(results['successful'])} apps
- **Failed:** {len(results['failed'])} apps
- **Build Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

## ✅ Successfully Patched Apps

"""
    
    def parse_apk_details(apk_path):
        # Example: output/com.google.android.youtube-v20.14.43-universal-patched.apk
        import re, os
        fname = os.path.basename(apk_path)
        # Remove '-patched.apk' or similar suffix
        fname = re.sub(r'-patched(\.keystore)?\.apk$', '', fname)
        # Remove output/ prefix if present
        fname = fname.replace('output/', '')
        # Split by '-'
        parts = fname.split('-')
        # Find app name
        app_name = None
        version = None
        variant = None
        if len(parts) >= 3:
            # com.google.android.youtube-v20.14.43-universal
            pkg = parts[0]
            version = parts[1]
            variant = parts[2]
        else:
            pkg = parts[0]
            version = None
            variant = None
        # Map package to app name if possible
        app_map = {
            'com.google.android.youtube': 'YouTube',
            'com.google.android.apps.youtube.music': 'YouTube Music',
            'com.google.android.apps.photos': 'Google Photos',
            'com.twitter.android': 'Twitter',
            'com.reddit.frontpage': 'Reddit',
        }
        app_name = app_map.get(pkg, pkg)
        return app_name, version, variant, fname

    for item in results['successful']:
        app_name, version, variant, fname = parse_apk_details(item['output_apk'])
        details = f"{app_name}"
        if version:
            details += f" {version}"
        if variant:
            details += f" - {variant}"
        release_notes += f"- {details}\n"

    if results['failed']:
        release_notes += f"\n## ❌ Failed to Patch\n\n"
        for item in results['failed']:
            app_name, version, variant, fname = parse_apk_details(item.get('output_apk', item.get('input_apk', '')))
            details = f"{app_name}"
            if version:
                details += f" {version}"
            if variant:
                details += f" - {variant}"
            release_notes += f"- {details} - See issues for details\n"
    
    release_notes += f"""
## 📥 Installation

1. Download the APK for your desired app
2. Enable "Install from Unknown Sources" on your Android device
3. Install the downloaded APK
4. Download and install [GMSCore (micro G)](https://github.com/microg/GmsCore/releases/) if you want to login with google account
5. Enjoy your patched app!

## ⚠️ Important Notes

- These are modified versions of the original apps
- Use at your own risk
- Some features may not work as expected
- These patches are provided by the ReVanced project

## 🔗 Links

- [ReVanced Project](https://github.com/ReVanced)
- [Report Issues](https://github.com/{repo_name}/issues)

---
*Automated build by GitHub Actions*
"""
    
    print(f"Creating release: {tag_name}")
    
    try:
        # Create the release
        release = repo.create_git_release(
            tag=tag_name,
            name=release_title,
            message=release_notes,
            draft=False,
            prerelease=False
        )
        
        print(f"✓ Created release: {release.html_url}")
        
        # Upload APKs
        print("\nUploading APKs...")
        for item in results['successful']:
            apk_path = Path(item['output_apk'])
            if apk_path.exists():
                print(f"  Uploading {apk_path.name}...")
                with open(apk_path, 'rb') as f:
                    release.upload_asset(
                        path=str(apk_path),
                        label=apk_path.name,  # Use full filename as asset title
                        content_type="application/vnd.android.package-archive"
                    )
                print(f"  ✓ Uploaded {apk_path.name}")
            else:
                print(f"  ✗ APK not found: {apk_path}")
        
        print(f"\n✓ Release created successfully!")
        print(f"  URL: {release.html_url}")
        
        # Save release info
        release_info = {
            'tag': tag_name,
            'url': release.html_url,
            'created_at': datetime.now().isoformat()
        }
        
        with open(OUTPUT_DIR / "release_info.json", 'w') as f:
            json.dump(release_info, f, indent=2)
        
        # Log the release
        log_release_created(release_info, results)
        
        sys.exit(0)  # Explicit success exit
        
    except Exception as e:
        print(f"✗ Error creating release: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_release()