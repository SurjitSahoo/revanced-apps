#!/usr/bin/env python3
"""
Patch APKs using ReVanced CLI
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

REVANCED_DIR = Path("revanced")
DOWNLOADS_DIR = Path("downloads")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def find_revanced_files():
    """Find ReVanced CLI, patches, and integrations files"""
    files = {
        'cli': None,
        'patches': None,
        'integrations': None
    }
    
    for file in REVANCED_DIR.glob("*.jar"):
        name_lower = file.name.lower()
        if 'cli' in name_lower:
            files['cli'] = file
    
    # Look for patches file (.rvp extension)
    for file in REVANCED_DIR.glob("*.rvp"):
        name_lower = file.name.lower()
        if 'patches' in name_lower:
            files['patches'] = file
    
    for file in REVANCED_DIR.glob("*.apk"):
        name_lower = file.name.lower()
        if 'integrations' in name_lower:
            files['integrations'] = file
    
    # Verify all files found
    missing = [k for k, v in files.items() if v is None]
    if missing:
        raise FileNotFoundError(f"Missing ReVanced files: {', '.join(missing)}")
    
    return files

def _extract_architecture_from_filename(filename):
    """Extract architecture from APK filename"""
    filename_lower = filename.lower()
    
    # Common architecture patterns in APK filenames
    if 'armeabi-v7a' in filename_lower or 'armv7' in filename_lower:
        return 'armeabi-v7a'
    elif 'arm64-v8a' in filename_lower or 'arm64' in filename_lower or 'aarch64' in filename_lower:
        return 'arm64-v8a'
    elif 'x86_64' in filename_lower:
        return 'x86_64'
    elif 'x86' in filename_lower:
        return 'x86'
    elif 'universal' in filename_lower or 'noarch' in filename_lower:
        return 'universal'
    else:
        # Fallback: try to extract from version pattern like "v1.0-universal"
        import re
        match = re.search(r'-(armeabi-v7a|arm64-v8a|x86_64|x86|universal|noarch)', filename_lower)
        if match:
            arch = match.group(1)
            return 'armeabi-v7a' if arch in ['armv7', 'armeabi'] else arch
        return 'universal'  # Default fallback

def patch_apk(apk_path, app_info, revanced_files, max_retries=3):
    """
    Patch a single APK using ReVanced CLI with retry logic
    """
    app_name = app_info['name']
    package_name = app_info['package_name']
    
    print(f"\n{'='*60}")
    print(f"Patching: {app_name}")
    print(f"Package: {package_name}")
    print(f"{'='*60}")
    
    # Create unique output filename based on input APK name
    input_filename = apk_path.name
    # Replace .apk with -patched.apk but keep the rest of the original filename
    output_filename = input_filename.replace('.apk', '-patched.apk')
    output_path = OUTPUT_DIR / output_filename
    
    # Build ReVanced command
    cmd = [
        'java', '-jar', str(revanced_files['cli']),
        'patch',
        '-p', str(revanced_files['patches']),
        '-o', str(output_path),
        str(apk_path)
    ]
    
    # Add specific patches if configured
    if app_info.get('patches'):
        for patch in app_info['patches']:
            cmd.extend(['--enable', patch])
    
    # Add excluded patches if configured
    if app_info.get('exclude_patches'):
        for patch in app_info['exclude_patches']:
            cmd.extend(['--disable', patch])
    
    print(f"Command: {' '.join(cmd)}\n")
    
    # Retry logic for patching
    last_error = None
    log_file = OUTPUT_DIR / f"{package_name}-patch.log"
    
    for attempt in range(max_retries):
        try:
            print(f"📱 Patching attempt {attempt + 1}/{max_retries}...")
            
            # Clean up previous output file if it exists
            if output_path.exists():
                output_path.unlink()
            
            # Run the patching process
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            # Log output (append for multiple attempts)
            log_mode = 'w' if attempt == 0 else 'a'
            with open(log_file, log_mode) as f:
                if attempt > 0:
                    f.write(f"\n\n{'='*50}\nRETRY ATTEMPT {attempt + 1}/{max_retries}\n{'='*50}\n")
                f.write(f"Command: {' '.join(cmd)}\n\n")
                f.write("STDOUT:\n")
                f.write(result.stdout)
                f.write("\n\nSTDERR:\n")
                f.write(result.stderr)
                f.write(f"\n\nReturn code: {result.returncode}")
            
            if result.returncode == 0 and output_path.exists():
                print(f"✓ Successfully patched {app_name} (attempt {attempt + 1})")
                return {
                    'success': True,
                    'app': app_info,
                    'input_apk': str(apk_path),
                    'output_apk': str(output_path),
                    'log_file': str(log_file),
                    'attempts': attempt + 1
                }
            else:
                error_msg = result.stderr or result.stdout
                last_error = {
                    'error': error_msg,
                    'return_code': result.returncode,
                    'attempt': attempt + 1
                }
                
                if attempt < max_retries - 1:
                    print(f"✗ Patching failed (attempt {attempt + 1}), retrying...")
                    print(f"  Return code: {result.returncode}")
                    if result.stderr:
                        print(f"  Error: {result.stderr[:200]}")
                    print(f"🔄 Waiting 3 seconds before retry...")
                    import time
                    time.sleep(3)
                else:
                    print(f"✗ Failed to patch {app_name} after {max_retries} attempts")
                    print(f"  Final return code: {result.returncode}")
                    if result.stderr:
                        print(f"  Final error: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Patching timed out after 10 minutes (attempt {attempt + 1})"
            print(f"✗ {error_msg}")
            last_error = {
                'error': error_msg,
                'return_code': -1,
                'attempt': attempt + 1
            }
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying after timeout...")
                import time
                time.sleep(3)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)} (attempt {attempt + 1})"
            print(f"✗ {error_msg}")
            last_error = {
                'error': error_msg,
                'return_code': -1,
                'attempt': attempt + 1
            }
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying after error...")
                import time
                time.sleep(3)
    
    # All attempts failed
    return {
        'success': False,
        'app': app_info,
        'input_apk': str(apk_path),
        'error': last_error['error'],
        'return_code': last_error['return_code'],
        'log_file': str(log_file),
        'attempts': max_retries
    }


def main():
    """
    Patch downloaded APKs using ReVanced with proper exit code handling:
    - Exit 0: Success (at least some patches completed)
    - Exit 1: Critical error (script crash, missing tools, config issues) 
    - Exit 2: All patches failed (but script ran successfully)
    """
    try:
        print("🔧 Starting APK patching process...\n")
        
        # Load download results
        download_results_file = DOWNLOADS_DIR / "download_results.json"
        if not download_results_file.exists():
            print("❌ Critical Error: No download results found. Run downloader.py first.")
            return 1  # Critical error - missing prerequisite
        
        try:
            with open(download_results_file, 'r') as f:
                download_results = json.load(f)
        except Exception as e:
            print(f"❌ Critical Error: Failed to load download results: {e}")
            return 1  # Critical error - file corruption
        
        if not download_results['successful']:
            print("⚠️  No APKs were successfully downloaded - nothing to patch.")
            return 2  # No inputs to process (application-level issue)
        
        # Find ReVanced files
        try:
            revanced_files = find_revanced_files()
            print("✅ Found ReVanced tools:")
            for key, path in revanced_files.items():
                print(f"  {key}: {path.name}")
        except FileNotFoundError as e:
            print(f"❌ Critical Error: {e}")
            return 1  # Critical error - missing tools
        
        # Load configuration for retry settings
        config_file = Path("config/apps.json")
        max_patch_retries = 3  # Default
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    max_patch_retries = config.get('settings', {}).get('max_patch_retries', 3)
                    print(f"📋 Patch retry limit: {max_patch_retries}")
            except Exception as e:
                print(f"⚠️  Could not load config, using default retry limit: {e}")
        
        # Patch each downloaded APK
        results = {
            'successful': [],
            'failed': [],
            'timestamp': datetime.now().isoformat()
        }
        
        for item in download_results['successful']:
            app_info = item['app']
            apk_paths = item['paths']  # Multiple APKs possible
            
            for apk_path_str in apk_paths:
                apk_path = Path(apk_path_str)
                
                if not apk_path.exists():
                    print(f"✗ APK not found: {apk_path}")
                    results['failed'].append({
                        'app': app_info,
                        'error': 'APK file not found'
                    })
                    continue
                
                result = patch_apk(apk_path, app_info, revanced_files, max_patch_retries)
                
                if result['success']:
                    results['successful'].append(result)
                else:
                    results['failed'].append(result)
        
        # Save results for next steps
        results_file = OUTPUT_DIR / "patch_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Patching Summary:")
        print(f"  Successful: {len(results['successful'])}")
        print(f"  Failed: {len(results['failed'])}")
        print(f"{'='*60}")
        
        if results['successful']:
            print("\nSuccessfully patched:")
            for item in results['successful']:
                app_name = item['app']['name']
                apk_file = Path(item['input_apk']).name
                # Extract architecture from filename (e.g., "app-v1.0-arm64-v8a.apk" -> "arm64-v8a")
                arch = _extract_architecture_from_filename(apk_file)
                print(f"  ✓ {app_name}-{arch}")
        
        if results['failed']:
            print("\nFailed to patch:")
            for item in results['failed']:
                app_name = item['app']['name']
                if 'input_apk' in item:
                    apk_file = Path(item['input_apk']).name
                    arch = _extract_architecture_from_filename(apk_file)
                    print(f"  ✗ {app_name}-{arch}")
                else:
                    print(f"  ✗ {app_name}-unknown")
        
        # Set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"success_count={len(results['successful'])}\n")
                f.write(f"failure_count={len(results['failed'])}\n")
    
        # Return appropriate exit codes
        if len(results['successful']) == 0 and len(results['failed']) > 0:
            print(f"\n⚠️  All patches failed - exit code 2")
            return 2  # All patches failed
        elif len(results['failed']) > 0:
            print(f"\n⚠️  Some patches failed - exit code 0 (partial success)")
            return 0  # Partial success
        else:
            print(f"\n✅ All patches successful - exit code 0")
            return 0  # Complete success
        
    except Exception as e:
        print(f"\n❌ Critical Error: Unexpected script failure: {e}")
        import traceback
        traceback.print_exc()
        return 1  # Critical script error

if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)