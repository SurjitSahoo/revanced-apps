#!/usr/bin/env python3
"""
Setup script to download latest ReVanced tools
"""

import os
import requests
import json
from pathlib import Path

REVANCED_DIR = Path("revanced")
REVANCED_DIR.mkdir(exist_ok=True)

def get_latest_release(repo):
    """Get latest release info from GitHub repo"""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def download_file(url, filename):
    """Download file with progress"""
    print(f"Downloading {filename}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(REVANCED_DIR / filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✓ Downloaded {filename}")

def download_revanced_tools():
    """Download ReVanced CLI, Patches, and Integrations"""
    
    tools = {
        "revanced-cli": "ReVanced/revanced-cli",
        "revanced-patches": "ReVanced/revanced-patches",
        "revanced-integrations": "ReVanced/revanced-integrations"
    }
    
    for tool_name, repo in tools.items():
        try:
            print(f"\nFetching latest {tool_name}...")
            release = get_latest_release(repo)
            
            # Find the appropriate file in assets
            for asset in release['assets']:
                asset_name = asset['name']
                # Download .jar for CLI, .apk for integrations, .rvp for patches
                if (asset_name.endswith('.jar') or 
                    asset_name.endswith('.apk') or 
                    asset_name.endswith('.rvp')):
                    # Skip signature files
                    if asset_name.endswith('.asc'):
                        continue
                        
                    download_file(asset['browser_download_url'], asset_name)
                    
                    # Save version info
                    version_file = REVANCED_DIR / f"{tool_name}-version.txt"
                    with open(version_file, 'w') as f:
                        f.write(release['tag_name'])
                    break
            
        except Exception as e:
            print(f"✗ Error downloading {tool_name}: {e}")
            raise

def main():
    print("Setting up ReVanced tools...")
    download_revanced_tools()
    
    # List downloaded files
    print("\nDownloaded files:")
    for file in REVANCED_DIR.glob("*"):
        if file.is_file() and not file.name.endswith('.txt'):
            print(f"  - {file.name}")
    
    print("\n✓ ReVanced tools setup complete!")

if __name__ == "__main__":
    main()