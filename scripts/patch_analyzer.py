#!/usr/bin/env python3
"""
Analyze ReVanced patches to determine supported app versions
"""

import json
import subprocess
import re
from pathlib import Path

REVANCED_DIR = Path("revanced")
CONFIG_FILE = Path("config/apps.json")

def get_patch_info():
    """Get information about available patches using ReVanced CLI"""
    try:
        # Find the CLI jar file
        cli_jar = None
        for jar_file in REVANCED_DIR.glob("revanced-cli-*.jar"):
            cli_jar = jar_file
            break
        
        if not cli_jar:
            raise FileNotFoundError("ReVanced CLI jar not found")
        
        # Find the patches file
        patches_file = None
        for rvp_file in REVANCED_DIR.glob("patches-*.rvp"):
            patches_file = rvp_file
            break
        
        if not patches_file:
            raise FileNotFoundError("ReVanced patches file not found")
        
        print(f"🔍 Analyzing patches using CLI: {cli_jar.name}")
        print(f"📦 Patches file: {patches_file.name}")
        
        # Run ReVanced CLI to list patches with version info
        cmd = [
            "java", "-jar", str(cli_jar),
            "list-patches",
            "--with-versions",
            "--with-packages", 
            str(patches_file)
        ]
        
        print(f"🚀 Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REVANCED_DIR.parent)
        
        if result.returncode != 0:
            print(f"❌ CLI command failed with return code {result.returncode}")
            print(f"Error output: {result.stderr}")
            return None
        
        return result.stdout
        
    except Exception as e:
        print(f"❌ Error getting patch info: {e}")
        return None

def parse_patch_output(cli_output):
    """Parse ReVanced CLI output to extract patch information"""
    # Extract package-version mappings and detect packages that support "any" version
    package_versions = {}
    packages_with_patches = set()  # Track all packages that have patches
    
    if not cli_output:
        return package_versions
    
    lines = cli_output.split('\n')
    current_package = None
    looking_for_versions = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Look for package names
        if line.startswith('Package name:'):
            package_name = line.replace('Package name:', '').strip()
            current_package = package_name
            packages_with_patches.add(package_name)  # This package has patches
            if current_package not in package_versions:
                package_versions[current_package] = set()
            looking_for_versions = True
            continue
        
        # Look for version numbers under "Compatible versions:"
        elif line.startswith('Compatible versions:'):
            looking_for_versions = True
            continue  # Just a header, versions come next
        elif current_package and looking_for_versions and re.match(r'^\d+\.\d+\.\d+', line):
            # This is a version number
            version = line.strip()
            package_versions[current_package].add(version)
            continue
        elif current_package and line.startswith('Index:'):
            # New patch entry - stop looking for versions for current package
            looking_for_versions = False
            # If we found a package but no versions, it means "any version" is supported
            if current_package in packages_with_patches and len(package_versions[current_package]) == 0:
                package_versions[current_package].add("any")  # Special marker for "any version"
            current_package = None
    
    # Handle the last package if we reached end of file
    if current_package and current_package in packages_with_patches and len(package_versions[current_package]) == 0:
        package_versions[current_package].add("any")  # Special marker for "any version"
    
    # Convert sets to sorted lists (latest first), except for "any" version packages
    for package in package_versions:
        if package_versions[package] == {"any"} or package_versions[package] == ["any"]:
            package_versions[package] = ["any"]  # Keep "any" as is
        else:
            versions = list(package_versions[package])
            # Sort versions properly (latest first)
            try:
                versions.sort(key=lambda x: [int(i) for i in x.split('.')], reverse=True)
            except:
                versions.sort(reverse=True)
            package_versions[package] = versions
    
    return package_versions

def get_supported_versions_for_package(package_name, package_versions):
    """Get supported versions for a specific package"""
    return package_versions.get(package_name, [])

def analyze_config_apps():
    """Analyze the apps in config against available patches"""
    # Load config
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    # Get patch information
    print("🔍 Getting ReVanced patch information...")
    cli_output = get_patch_info()
    
    if not cli_output:
        print("❌ Could not get patch information")
        return None
    
    # Parse patches
    package_versions = parse_patch_output(cli_output)
    
    print(f"📦 Found patches for {len(package_versions)} packages")
    
    # Analyze each app in config
    app_analysis = {}
    
    for app in config['apps']:
        package_name = app['package_name']
        app_name = app['name']
        
        print(f"\n📱 Analyzing {app_name} ({package_name})...")
        
        supported_versions = get_supported_versions_for_package(package_name, package_versions)
        
        if supported_versions:
            # Handle "any" version case (supports all versions)
            if supported_versions == ["any"]:
                app_analysis[package_name] = {
                    'name': app_name,
                    'supported_versions': ["any"],
                    'recommended_version': "latest",  # Use "latest" for any-version apps
                    'download_url': app['download_url'],
                    'supports_any_version': True
                }
                
                print(f"  ✅ Supported by ReVanced patches")
                print(f"  📋 Supports ANY version (no version restrictions)")
                print(f"  🎯 Recommended approach: Download latest available")
            else:
                # Specific versions supported
                app_analysis[package_name] = {
                    'name': app_name,
                    'supported_versions': supported_versions,
                    'recommended_version': supported_versions[0],  # Latest supported version
                    'download_url': app['download_url']
                }
                
                print(f"  ✅ Supported by ReVanced patches")
                print(f"  📋 Available versions: {', '.join(supported_versions[:5])}{'...' if len(supported_versions) > 5 else ''}")
                print(f"  🎯 Recommended version: {supported_versions[0]}")
        else:
            app_analysis[package_name] = {
                'name': app_name,
                'supported_versions': [],
                'recommended_version': None,
                'download_url': app['download_url'],
                'status': 'not_supported'
            }
            print(f"  ❌ No ReVanced patches found for this app")
    
    return app_analysis

def main():
    print("🔍 ReVanced Patch Analysis")
    print("="*50)
    
    analysis = analyze_config_apps()
    
    if analysis:
        # Save analysis results
        output_file = Path("downloads/patch_analysis.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n💾 Analysis saved to: {output_file}")
        
        # Summary
        supported_apps = [app for app in analysis.values() if app.get('recommended_version')]
        unsupported_apps = [app for app in analysis.values() if not app.get('recommended_version')]
        
        print(f"\n📊 Summary:")
        print(f"  Supported apps: {len(supported_apps)}")
        print(f"  Unsupported apps: {len(unsupported_apps)}")
        
        if supported_apps:
            print(f"\n✅ Supported apps:")
            for app in supported_apps:
                print(f"  - {app['name']}: v{app['recommended_version']}")
        
        if unsupported_apps:
            print(f"\n❌ Unsupported apps:")
            for app in unsupported_apps:
                print(f"  - {app['name']}")
    else:
        print("❌ Analysis failed")

if __name__ == "__main__":
    main()