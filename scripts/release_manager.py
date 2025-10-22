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
    
    This function now compares app versions rather than just asset names, so if the same
    app versions are successfully patched as in the previous release, it will skip creating
    a duplicate release even if some other apps failed.
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
        
        # Extract app versions from current successful patches
        current_app_versions = {}
        for item in current_successful:
            output_apk_path = item.get('output_apk', '')
            if output_apk_path:
                # Parse the filename to extract app, version, and architecture
                # e.g., "com.google.android.youtube-v20.14.43-universal-patched.apk"
                filename = os.path.basename(output_apk_path)
                if filename.endswith('-patched.apk'):
                    # Remove -patched.apk suffix
                    base_name = filename[:-12]  # Remove "-patched.apk"
                    
                    # Split into parts: package-version-architecture
                    # Find last occurrence of version pattern (vX.X.X)
                    import re
                    # More flexible regex to handle complex package names
                    version_match = re.search(r'-v([\d.]+)-([^-]+)$', base_name)
                    if version_match:
                        version = version_match.group(1)
                        architecture = version_match.group(2)
                        package = base_name[:version_match.start()]
                    else:
                        # Fallback: try to parse differently structured names
                        # Look for pattern: package-v8.10.52-armeabi-v7a
                        alt_match = re.search(r'-v([\d.]+)-(.+)$', base_name)
                        if alt_match:
                            version = alt_match.group(1)
                            # Handle multi-part architectures like armeabi-v7a
                            architecture = alt_match.group(2)
                            package = base_name[:alt_match.start()]
                        else:
                            continue  # Skip if we can't parse
                        
                        if package not in current_app_versions:
                            current_app_versions[package] = {}
                        if version not in current_app_versions[package]:
                            current_app_versions[package][version] = set()
                        current_app_versions[package][version].add(architecture)
        
        # Extract app versions from previous release assets
        previous_app_versions = {}
        for asset_name in previous_assets:
            if asset_name.endswith('.apk'):
                # Same parsing logic for previous assets
                import re
                # More flexible regex for parsing previous assets
                version_match = re.search(r'-v([\d.]+)-([^-]+)-patched\.apk$', asset_name)
                if version_match:
                    version = version_match.group(1)
                    architecture = version_match.group(2)
                    package = asset_name[:version_match.start()]
                else:
                    # Fallback: try alternative pattern for complex architectures
                    alt_match = re.search(r'-v([\d.]+)-(.+)-patched\.apk$', asset_name)
                    if alt_match:
                        version = alt_match.group(1)
                        architecture = alt_match.group(2)
                        package = asset_name[:alt_match.start()]
                    else:
                        continue  # Skip if we can't parse
                    
                    if package not in previous_app_versions:
                        previous_app_versions[package] = {}
                    if version not in previous_app_versions[package]:
                        previous_app_versions[package][version] = set()
                    previous_app_versions[package][version].add(architecture)
        
        # Debug: show what we're comparing
        print(f"� Current successful apps and versions:")
        for package, versions in current_app_versions.items():
            for version, archs in versions.items():
                print(f"   {package} v{version}: {', '.join(sorted(archs))}")
        
        print(f"🔍 Previous release apps and versions:")
        for package, versions in previous_app_versions.items():
            for version, archs in versions.items():
                print(f"   {package} v{version}: {', '.join(sorted(archs))}")
        
        # Check if current successful patches are a subset of previous release
        # This means all currently successful apps/versions were already released before
        current_is_subset_of_previous = True
        for package, versions in current_app_versions.items():
            if package not in previous_app_versions:
                current_is_subset_of_previous = False
                break
            for version, archs in versions.items():
                if version not in previous_app_versions[package]:
                    current_is_subset_of_previous = False
                    break
                # Check if all current architectures exist in previous release
                if not archs.issubset(previous_app_versions[package][version]):
                    current_is_subset_of_previous = False
                    break
            if not current_is_subset_of_previous:
                break
        
        if current_is_subset_of_previous and current_app_versions:
            print("✅ All current successful patches already exist in previous release")
            print("📝 Skipping release - no new content (successful apps are subset of previous release)")
            return True
        else:
            print("📝 App version differences detected:")
            
            # Show which apps/versions are new
            for package, versions in current_app_versions.items():
                if package not in previous_app_versions:
                    print(f"   New app: {package}")
                else:
                    for version, archs in versions.items():
                        if version not in previous_app_versions[package]:
                            print(f"   New version: {package} v{version}")
                        elif archs != previous_app_versions[package][version]:
                            print(f"   Different architectures: {package} v{version}")
            
            # Show which apps/versions were removed
            for package, versions in previous_app_versions.items():
                if package not in current_app_versions:
                    print(f"   Removed app: {package}")
                else:
                    for version, archs in versions.items():
                        if version not in current_app_versions[package]:
                            print(f"   Removed version: {package} v{version}")
            
            return False
            
    except Exception as e:
        print(f"⚠️  Error comparing with previous release: {e}")
        print("🔄 Proceeding with release creation to be safe")
        import traceback
        traceback.print_exc()
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