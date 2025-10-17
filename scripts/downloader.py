#!/usr/bin/env python3
"""
Download APKs from APKMirror with proper parsing and architecture selection
"""

import os
import json
import requests
import time
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    print("⚠️  BeautifulSoup4 not installed. Please install it with: pip install beautifulsoup4")
    BEAUTIFULSOUP_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Fallback progress function
    class tqdm:
        def __init__(self, **kwargs):
            self.total = kwargs.get('total', 0)
            self.desc = kwargs.get('desc', '')
            self.leave = kwargs.get('leave', True)
            self.n = 0
            
        def update(self, n):
            self.n += n
            if self.total > 0:
                percent = (self.n / self.total) * 100
                print(f"\r{self.desc} {percent:.1f}%", end='')
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            if not self.leave:
                print()

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

CONFIG_FILE = Path("config/apps.json")

def load_config():
    """Load app configuration"""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

class APKMirrorParser:
    """Parse APKMirror pages to find APK download links"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/118.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
        })
    
    def get_all_version_pages(self, app_url, limit=50):
        """Get all available version pages from the app's main page - comprehensive search"""
        try:
            response = self.session.get(app_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for ALL version links - multiple APKMirror patterns
            version_links = []
            
            # Pattern 1: Standard release links
            links1 = soup.find_all('a', href=re.compile(r'.*-release/$'))
            version_links.extend(links1)
            
            # Pattern 2: Version-specific patterns
            links2 = soup.find_all('a', href=re.compile(r'.*/[^/]+-\d+(?:[.-]\d+)*.*-release/$'))
            version_links.extend(links2)
            
            # Pattern 3: Look in version listing tables/divs
            version_divs = soup.find_all(['div', 'section'], class_=re.compile(r'.*version.*|.*release.*', re.I))
            for div in version_divs:
                div_links = div.find_all('a', href=re.compile(r'.*release.*'))
                version_links.extend(div_links)
            
            # Pattern 4: Look for any links with version patterns in the URL
            all_links = soup.find_all('a', href=re.compile(r'.*\d+[.-]\d+[.-]\d+.*'))
            for link in all_links:
                href = link.get('href', '')
                if 'release' in href or re.search(r'\d+[.-]\d+[.-]\d+', href):
                    version_links.append(link)
            
            # Remove duplicates and process
            seen_hrefs = set()
            unique_links = []
            for link in version_links:
                href = link.get('href')
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    unique_links.append(link)
            
            version_pages = []
            for link in unique_links[:limit]:
                href = link.get('href')
                if href:
                    # Remove fragment identifiers
                    if '#' in href:
                        href = href.split('#')[0]
                    full_url = urljoin(app_url, href)
                    
                    # Extract version from URL
                    version_str = self._extract_version_from_url(href)
                    if version_str != "0.0.0":
                        # Filter out obviously wrong versions - make app-specific
                        try:
                            parts = version_str.split('.')
                            if len(parts) >= 2:
                                major = int(parts[0])
                                
                                # App-specific version validation
                                if 'youtube' in app_url and (major < 10 or major > 50):
                                    continue  # YouTube versions typically 15-25
                                elif 'photos' in app_url and (major < 1 or major > 20):
                                    continue  # Google Photos versions typically 1-20
                                elif major < 1 or major > 100:
                                    continue  # General sanity check
                        except:
                            pass
                        
                        version_pages.append({
                            'url': full_url,
                            'version': version_str,
                            'href': href
                        })
            
            # Remove duplicate versions (keep first occurrence)
            seen_versions = set()
            unique_versions = []
            for vp in version_pages:
                if vp['version'] not in seen_versions:
                    seen_versions.add(vp['version'])
                    unique_versions.append(vp)
            
            return unique_versions[:limit]
            
        except Exception as e:
            print(f"  ✗ Error getting version pages: {e}")
            return []
    
    def _extract_version_from_url(self, url):
        """Extract version string from APKMirror URL - improved detection"""
        import re
        
        # APKMirror URLs can have various patterns:
        # /apk/google-inc/youtube/youtube-20-14-43-release/
        # /apk/google-inc/photos/google-photos-7-50-0-818774663-release/
        
        # Pattern 1: Google Photos special patterns (with build number)
        if 'google-photos' in url or '/photos/' in url:
            # google-photos-7-50-0-818774663-release -> extract 7.50.0
            version_match = re.search(r'google-photos-(\d+)-(\d+)-(\d+)-\d+-release', url)
            if version_match:
                return f"{version_match.group(1)}.{version_match.group(2)}.{version_match.group(3)}"
            
            # photos-5-64-0-405502726-release -> extract 5.64.0  
            version_match = re.search(r'photos-(\d+)-(\d+)-(\d+)-\d+-release', url)
            if version_match:
                return f"{version_match.group(1)}.{version_match.group(2)}.{version_match.group(3)}"
        
        # Pattern 2: Standard release pattern (most common)
        version_match = re.search(r'-(\d+(?:-\d+)+)-release', url)
        if version_match:
            return version_match.group(1).replace('-', '.')
        
        # Pattern 3: Alternative patterns for different apps
        version_match = re.search(r'/([^/]+)-(\d+(?:\.\d+)+(?:\.\d+)*(?:-release)?(?:\.0)*)', url)
        if version_match:
            version_part = version_match.group(2)
            # Clean up version string
            version_part = re.sub(r'-release.*', '', version_part)
            return version_part
        
        # Pattern 4: Direct version numbers
        version_match = re.search(r'(\d+\.\d+\.\d+(?:\.\d+)*)', url)
        if version_match:
            return version_match.group(1)
        
        # Pattern 4: Dash-separated numbers (convert to dots)
        version_match = re.search(r'-(\d+)-(\d+)-(\d+)(?:-(\d+))?-', url)
        if version_match:
            groups = [g for g in version_match.groups() if g is not None]
            return '.'.join(groups)
        
        return "0.0.0"  # fallback
    

    
    def _get_variants_from_version_page(self, version_page_url, architectures, prefer_nodpi=True, debug=False):
        """Get real APK variants from a specific version page - simplified and more reliable"""
        try:
            response = self.session.get(version_page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            variants = []
            
            if debug:
                print(f"      🔍 Parsing version page for architecture-specific variants...")
            
            # Method 1: Look for architecture names and their associated download links
            arch_keywords = {
                'armeabi-v7a': ['armeabi-v7a', 'armeabi'],
                'arm64-v8a': ['arm64-v8a', 'arm64'],
                'x86': ['x86'],
                'x86_64': ['x86_64'],
                'universal': ['universal', 'noarch']
            }
            
            # Find elements containing architecture names
            for arch in architectures:
                if arch not in arch_keywords:
                    continue
                    
                for keyword in arch_keywords[arch]:
                    # Find elements containing this architecture keyword
                    arch_elements = soup.find_all(string=lambda text: text and keyword in text.lower())
                    
                    for arch_element in arch_elements:
                        # Look for download links near this architecture element
                        parent = arch_element.parent
                        grandparent = parent.find_parent() if parent else None
                        
                        # Search in parent and grandparent for download links
                        for container in [parent, grandparent]:
                            if not container:
                                continue
                                
                            download_links = container.find_all('a', href=re.compile(r'.*-apk-download/?$'))
                            
                            for link in download_links:
                                href = link.get('href', '')
                                if href and not href.endswith('#disqus_thread'):  # Skip comment links
                                    full_url = urljoin(version_page_url, href)
                                    
                                    # Avoid duplicates
                                    if not any(v['url'] == full_url for v in variants):
                                        variants.append({
                                            'url': full_url,
                                            'text': link.get_text(strip=True),
                                            'architecture': arch,
                                            'context': f'architecture_specific_{arch}'
                                        })
                                        
                                        if debug:
                                            print(f"      ✓ Found {arch} variant: {href}")
                                        break  # Only take the first download link for this arch
                        
                        # Continue collecting all variants - don't break early
            
            # Method 2: Look for all download links and capture multiple variants per architecture
            all_download_links = soup.find_all('a', href=re.compile(r'.*-apk-download/?$'))
            
            if debug:
                print(f"      🔍 Checking {len(all_download_links)} download links for variants...")
            
            for link in all_download_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if href and not href.endswith('#disqus_thread'):
                    full_url = urljoin(version_page_url, href)
                    
                    # Skip if we already have this exact URL
                    if any(v['url'] == full_url for v in variants):
                        continue
                    
                    # Try to detect architecture from the URL or surrounding context
                    parent = link.find_parent()
                    context = parent.get_text(strip=True) if parent else ""
                    
                    # Also check table row context if available
                    row = link.find_parent('tr')
                    if row:
                        context += " " + row.get_text(strip=True)
                    
                    full_text = f"{text} {href} {context}".lower()
                    
                    # Detect architecture - STRICT MATCHING ONLY
                    arch_found = None
                    for arch in architectures:
                        if arch == 'armeabi-v7a' and any(variant in full_text for variant in ['armeabi', 'armv7', 'arm-v7a']):
                            arch_found = arch
                            break
                        elif arch == 'arm64-v8a' and any(variant in full_text for variant in ['arm64', 'aarch64']):
                            arch_found = arch
                            break
                        elif arch == 'x86_64' and 'x86_64' in full_text:
                            arch_found = arch
                            break
                        elif arch == 'x86' and 'x86' in full_text and 'x86_64' not in full_text:
                            arch_found = arch
                            break
                        elif arch == 'universal' and any(variant in full_text for variant in ['universal', 'noarch', 'all-arch']):
                            arch_found = arch
                            break
                    
                    # If no architecture detected but we have valid download link, assume universal
                    if not arch_found and 'universal' in architectures:
                        arch_found = 'universal'
                    
                    if arch_found:
                        variants.append({
                            'url': full_url,
                            'text': text,
                            'architecture': arch_found,
                            'context': context[:100]
                        })
                        
                        if debug:
                            print(f"      ✓ Found {arch_found} variant: {href}")
                    else:
                        if debug:
                            print(f"      ❌ Could not identify architecture for: {text[:30]}... (URL: {href[:50]}...)")
            
            if debug:
                print(f"      📦 Total variants found: {len(variants)}")
            
            # Filter to prefer APK downloads over Bundle downloads
            if variants:
                variants = self._filter_prefer_apk_downloads(variants, debug)
            
            return variants
            
        except Exception as e:
            if debug:
                print(f"      ✗ Error parsing version page: {e}")
            return []
    
    def _filter_prefer_apk_downloads(self, variants, debug=False):
        """
        Filter variants to prefer APK downloads over Bundle downloads.
        APKMirror offers both formats, we prefer monolithic APKs for ReVanced.
        """
        if not variants:
            return variants
        
        # Group variants by architecture
        arch_groups = {}
        for variant in variants:
            arch = variant.get('architecture', 'unknown')
            if arch not in arch_groups:
                arch_groups[arch] = []
            arch_groups[arch].append(variant)
        
        filtered_variants = []
        
        for arch, arch_variants in arch_groups.items():
            if len(arch_variants) == 1:
                # Only one option, use it
                filtered_variants.append(arch_variants[0])
                continue
            
            # Check for APK vs Bundle indicators in text and URL
            apk_variants = []
            bundle_variants = []
            other_variants = []
            
            for variant in arch_variants:
                text_lower = variant.get('text', '').lower()
                url_lower = variant.get('url', '').lower()
                context_lower = variant.get('context', '').lower()
                
                combined_text = f"{text_lower} {url_lower} {context_lower}"
                
                # APKMirror URL patterns for multiple variants:
                # Bundle: /app-name-version-android-apk-download/ (first variant, no number)
                # APK: /app-name-version-2-android-apk-download/ (second variant with "-2-")
                
                # Look for variant URLs with single digits before android-apk-download (like "-2-android-apk-download")
                # These are usually monolithic APKs (second, third variants)
                if re.search(r'-[2-9]-android-apk-download', url_lower):
                    apk_variants.append(variant)
                    if debug:
                        print(f"        🔸 Classified as APK (variant number): {url_lower[-50:]}")
                # Look for first variant URLs (no single digit before android-apk-download)
                # These are usually bundles  
                elif re.search(r'-android-apk-download/?$', url_lower) and not re.search(r'-[2-9]-android-apk-download', url_lower):
                    bundle_variants.append(variant)
                    if debug:
                        print(f"        📦 Classified as Bundle (non-numbered): {url_lower[-50:]}")
                # Look for explicit Bundle indicators in text
                elif any(indicator in combined_text for indicator in ['bundle', 'aab', 'app bundle']):
                    bundle_variants.append(variant)
                    if debug:
                        print(f"        📦 Classified as Bundle (text indicator): {combined_text[:50]}")
                # Look for explicit APK indicators
                elif any(indicator in combined_text for indicator in ['apk', 'android package']):
                    apk_variants.append(variant)
                    if debug:
                        print(f"        🔸 Classified as APK (text indicator): {combined_text[:50]}")
                # Fallback to other
                else:
                    other_variants.append(variant)
                    if debug:
                        print(f"        ❓ Unclassified variant: {url_lower[-50:]}")
            
            # Prefer APK over Bundle over Other
            if apk_variants:
                if debug:
                    print(f"      🎯 Preferring APK download for {arch} (found {len(apk_variants)} APK vs {len(bundle_variants)} Bundle)")
                filtered_variants.extend(apk_variants[:1])  # Take first APK variant
            elif bundle_variants:
                if debug:
                    print(f"      📦 Using Bundle download for {arch} (no APK available)")
                filtered_variants.extend(bundle_variants[:1])  # Take first Bundle variant
            elif other_variants:
                filtered_variants.extend(other_variants[:1])  # Take first other variant
        
        if debug and len(filtered_variants) != len(variants):
            print(f"      ✨ Filtered from {len(variants)} to {len(filtered_variants)} variants (preferring APK)")
        
        return filtered_variants
    
    def _get_context_text(self, link):
        """Extract context text from surrounding elements"""
        context_elements = []
        
        # Get parent and sibling context
        parent = link.find_parent()
        if parent:
            # Look for table cells, spans, divs with architecture info
            siblings = parent.find_all(['td', 'th', 'span', 'div', 'strong', 'b'])
            context_elements.extend(siblings)
            
            # Check grandparent too
            grandparent = parent.find_parent()
            if grandparent and grandparent.name in ['tr', 'li']:
                gp_elements = grandparent.find_all(['td', 'th', 'span', 'div'])
                context_elements.extend(gp_elements)
        
        # Extract text and clean it
        context_texts = [elem.get_text(strip=True) for elem in context_elements]
        return ' '.join(context_texts)
    
    def _extract_architecture_info(self, text, href, context_text, architectures):
        """Extract architecture information from text, URL, and context - STRICT matching only"""
        combined_text = (text + ' ' + href + ' ' + context_text).lower()
        
        # Only check for EXPLICIT architecture mentions - no guessing!
        
        # 1. Check for exact architecture strings in URL path (most reliable)
        url_lower = href.lower()
        for arch in architectures:
            if arch.lower() in url_lower:
                return arch
        
        # 2. Check for architecture variations in the combined text
        arch_variations = {
            'arm64-v8a': ['arm64-v8a', 'arm64v8a', 'arm64', 'aarch64'],
            'armeabi-v7a': ['armeabi-v7a', 'armeabiv7a', 'armeabi', 'armv7a', 'armv7'],
            'x86_64': ['x86_64', 'x8664', 'x64', 'amd64', 'x86-64'],
            'universal': ['universal', 'noarch', 'all-arch', 'fat']
        }
        
        for arch in architectures:
            if arch in arch_variations:
                for variation in arch_variations[arch]:
                    if variation in combined_text:
                        return arch
        
        # 3. Check for architecture indicators in URL structure
        # APKMirror sometimes uses patterns like "arm64" in the download path
        import re
        arch_patterns = {
            'arm64-v8a': [r'\barm64\b', r'\baarch64\b'],
            'armeabi-v7a': [r'\barmeabi\b', r'\barmv7\b', r'\barm32\b'],
            'x86_64': [r'\bx86_64\b', r'\bx64\b', r'\bamd64\b'],
            'universal': [r'\buniversal\b', r'\bnoarch\b']
        }
        
        for arch in architectures:
            if arch in arch_patterns:
                for pattern in arch_patterns[arch]:
                    if re.search(pattern, combined_text, re.IGNORECASE):
                        return arch
        
        # 4. NO FALLBACK to 'universal' - only return if explicitly found
        return None
    
    def _get_variants_from_subpage(self, subpage_url, architectures, prefer_nodpi, debug):
        """Try to get variants from a subpage that might list more download options"""
        try:
            response = self.session.get(subpage_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            variants = []
            
            if debug:
                print(f"      🔍 Checking subpage: {subpage_url}")
            
            # Look for download links on this subpage
            download_links = soup.find_all('a', href=re.compile(r'.*(?:download|apk).*'))
            
            for link in download_links:
                href = link.get('href')
                text = link.get_text(strip=True)
                
                if not href or any(skip in href for skip in ['#', 'javascript:', 'mailto:']):
                    continue
                
                # Check if this looks like an architecture-specific variant
                arch_found = self._extract_architecture_info(text, href, '', architectures)
                
                if arch_found:
                    full_url = urljoin(subpage_url, href)
                    variant = {
                        'url': full_url,
                        'text': text,
                        'context': text,
                        'architecture': arch_found,
                        'type': 'subpage_variant'
                    }
                    variants.append(variant)
                    
                    if debug:
                        print(f"      ✓ Found subpage variant: {text[:30]}... ({arch_found})")
            
            return variants
            
        except Exception as e:
            if debug:
                print(f"      ✗ Error parsing subpage: {e}")
            return []
    
    def get_direct_download_link(self, variant_page_url, debug=False):
        """Get the direct download link from variant/APK page through APKMirror's multi-step process"""
        try:
            if debug:
                print(f"      🔍 Getting direct download from: {variant_page_url}")
            
            # Step 1: Get the APK download page
            response = self.session.get(variant_page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # APKMirror has a specific download process:
            # 1. The APK page has a "Download APK" button
            # 2. That leads to a download confirmation page
            # 3. That page has the actual download link
            
            # Look for the main download button - APKMirror specific patterns
            download_button = None
            
            # Pattern 1: Look for the specific download APK button
            download_button = soup.find('a', class_=re.compile(r'.*downloadButton.*', re.IGNORECASE))
            if not download_button:
                # Pattern 2: Look for button with "Download APK" text
                download_button = soup.find('a', string=re.compile(r'.*download.*apk.*', re.IGNORECASE))
            if not download_button:
                # Pattern 3: Look for any prominent download link
                download_button = soup.find('a', class_=re.compile(r'.*(download|btn-primary).*', re.IGNORECASE))
            if not download_button:
                # Pattern 4: Look for link with specific download href pattern
                download_button = soup.find('a', href=re.compile(r'.*download.*'))
            
            if debug and download_button:
                print(f"      📋 Found download button: {download_button.get_text(strip=True)}")
                print(f"      📋 Button href: {download_button.get('href', 'No href')}")
            
            if not download_button:
                if debug:
                    print(f"      ✗ No download button found on APK page")
                    # Let's see what buttons are available
                    all_buttons = soup.find_all('a')
                    print(f"      📋 Available links ({len(all_buttons)}):")
                    for i, btn in enumerate(all_buttons[:10]):
                        text = btn.get_text(strip=True)
                        href = btn.get('href', 'No href')
                        print(f"        [{i+1}] {text[:30]}... -> {href[:50]}...")
                return None
            
            download_href = download_button.get('href')
            if not download_href:
                if debug:
                    print(f"      ✗ Download button has no href")
                return None
            
            # Handle fragment-only hrefs (like #safeDownload)
            if download_href.startswith('#'):
                if debug:
                    print(f"      📋 Fragment href detected: {download_href}")
                # Look for JavaScript or meta refresh that might contain the real URL
                # Or look for form submission URLs
                form = soup.find('form')
                if form:
                    action = form.get('action')
                    if action:
                        download_url = urljoin(variant_page_url, action)
                        if debug:
                            print(f"      📋 Using form action: {download_url}")
                    else:
                        download_url = variant_page_url  # Submit to same page
                else:
                    # Look for any other download links on the page
                    other_links = soup.find_all('a', href=re.compile(r'.*(?:download|\.apk).*'))
                    if other_links:
                        download_href = other_links[0].get('href')
                        download_url = urljoin(variant_page_url, download_href)
                        if debug:
                            print(f"      � Using alternative link: {download_url}")
                    else:
                        if debug:
                            print(f"      ✗ No alternative download method found")
                        return None
            else:
                download_url = urljoin(variant_page_url, download_href)
            
            if debug:
                print(f"      📄 Trying download URL: {download_url}")
            
            # Step 2: Follow the download URL
            # For APKMirror, this might require posting form data or handling redirects
            try:
                # Try GET first
                response2 = self.session.get(download_url, timeout=30, allow_redirects=True)
                response2.raise_for_status()
                
                # Check if this is the actual APK file
                content_type = response2.headers.get('content-type', '').lower()
                content_disposition = response2.headers.get('content-disposition', '')
                
                if ('application/vnd.android.package-archive' in content_type or 
                    'application/octet-stream' in content_type or
                    '.apk' in content_disposition or
                    response2.url.endswith('.apk')):
                    if debug:
                        print(f"      ✓ Direct APK download found: {response2.url}")
                    return response2.url
                
                # If not APK, parse the page for final download link
                soup2 = BeautifulSoup(response2.content, 'html.parser')
                
                # Look for the final download link patterns
                final_patterns = [
                    r'.*\.apk(\?.*)?$',  # Direct APK links
                    r'.*download\.php.*',  # Download script links
                    r'.*getdownload.*',  # Alternative download patterns
                ]
                
                for pattern in final_patterns:
                    final_links = soup2.find_all('a', href=re.compile(pattern))
                    if final_links:
                        final_href = final_links[0].get('href')
                        final_url = urljoin(download_url, final_href)
                        if debug:
                            print(f"      ✓ Final APK URL found: {final_url}")
                        return final_url
                
                # Look for auto-redirect meta tags
                meta_refresh = soup2.find('meta', attrs={'http-equiv': 'refresh'})
                if meta_refresh:
                    content = meta_refresh.get('content', '')
                    if 'url=' in content.lower():
                        redirect_url = content.split('url=')[1].strip()
                        final_url = urljoin(download_url, redirect_url)
                        if debug:
                            print(f"      ✓ Meta redirect URL found: {final_url}")
                        return final_url
                
                if debug:
                    print(f"      ✗ Could not find final download link in response")
                    print(f"      📋 Response content type: {content_type}")
                    print(f"      📋 Response URL: {response2.url}")
                
            except Exception as e:
                if debug:
                    print(f"      ✗ Error following download URL: {e}")
            
            return None
            
        except Exception as e:
            print(f"      ✗ Error getting direct download link: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            return None

def load_patch_analysis():
    """Load the patch analysis results"""
    analysis_file = Path("downloads/patch_analysis.json")
    if analysis_file.exists():
        with open(analysis_file, 'r') as f:
            return json.load(f)
    return {}

def download_single_apk(download_url, output_path, max_retries=3, retry_delay=5):
    """Download a single APK file with progress bar and retry logic"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/118.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.apkmirror.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
    })
    
    for attempt in range(max_retries):
        try:
            response = session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                if total_size > 0:
                    with tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        desc=f"  {output_path.name}",
                        leave=False
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    f.write(response.content)
            
            return True
            
        except requests.RequestException as e:
            print(f"✗ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"✗ Failed to download after {max_retries} attempts")
                return False
    
    return False



def download_app_apks(app, settings):
    """
    Download APKs for an app - targeting specific ReVanced-supported versions
    Only downloads explicitly identified architecture variants - NO GUESSING!
    """

    # Load patch analysis to get supported versions
    patch_analysis = load_patch_analysis()
    package_name = app['package_name']
    
    if package_name in patch_analysis:
        app_patch_info = patch_analysis[package_name]
        supported_versions = app_patch_info['supported_versions']
        recommended_version = app_patch_info['recommended_version']
        supports_any_version = app_patch_info.get('supports_any_version', False)
        
        if supports_any_version:
            print(f"  🎯 ReVanced supports ANY version - downloading latest available")
            print(f"  🎯 No version restrictions for this app")
        else:
            print(f"  🎯 ReVanced supported versions: {', '.join(supported_versions[:3])}{'...' if len(supported_versions) > 3 else ''}")
            print(f"  🎯 Targeting version: {recommended_version}")
    else:
        print(f"  ⚠️  No ReVanced patch analysis found - downloading latest available")
        supported_versions = []
        recommended_version = None
        supports_any_version = False
    
    parser = APKMirrorParser()
    architectures = settings.get('architectures', ['armeabi-v7a', 'arm64-v8a', 'x86_64', 'universal'])
    prefer_nodpi = settings.get('prefer_nodpi', True)
    download_multiple = settings.get('download_multiple_architectures', True)
    max_retries = settings.get('max_retries', 3)
    retry_delay = settings.get('retry_delay', 5)
    
    # Create app-specific directory
    app_dir = DOWNLOADS_DIR / app['package_name']
    app_dir.mkdir(exist_ok=True)
    
    downloaded_files = []
    missing_architectures = []  # Track architectures we couldn't find
    
    # Determine version strategy based on patch support
    if supports_any_version or (supported_versions and supported_versions[0] == "any"):
        # App supports any version - discover latest available versions
        print("  🔍 App supports any version - discovering latest available versions...")
        version_pages = parser.get_all_version_pages(app['download_url'], limit=10)
        
        # Debug output for troubleshooting
        if not version_pages and app['name'] == 'Google Photos':
            print("  🔍 Debug: Testing Google Photos page parsing...")
            try:
                response = parser.session.get(app['download_url'], timeout=30)
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, 'html.parser')
                    release_links = soup.find_all('a', href=re.compile(r'.*-release/?$'))
                    print(f"    📋 Found {len(release_links)} total release links")
                    if release_links:
                        for i, link in enumerate(release_links[:3]):
                            href = link.get('href')
                            version = parser._extract_version_from_url(href)
                            print(f"    📄 Link {i+1}: {href} -> version {version}")
                else:
                    print(f"    ❌ HTTP {response.status_code} when accessing page")
            except Exception as e:
                print(f"    ❌ Debug error: {e}")
        
        if not version_pages:
            print(f"  ✗ Could not find any version pages for {app['name']}")
            return False, []
        
        print(f"  📄 Found {len(version_pages)} versions to try (any version is supported)")
        
    elif supported_versions and supported_versions != ["any"]:
        # App has specific supported versions - construct direct URLs
        print(f"  🔍 Constructing direct URLs for supported versions...")
        
        version_pages = []
        for version in supported_versions:
            # Skip "any" markers
            if version == "any":
                continue
                
            # Construct direct URL for this version
            # Convert version format: 20.14.43 -> youtube-20-14-43-release
            version_parts = version.replace('.', '-')
            
            # Extract app name from base URL
            # https://www.apkmirror.com/apk/google-inc/youtube/ -> youtube
            app_name = app['download_url'].rstrip('/').split('/')[-1]
            
            # Construct the release URL
            version_url = f"{app['download_url']}{app_name}-{version_parts}-release/"
            
            version_pages.append({
                'url': version_url,
                'version': version,
                'constructed': True
            })
            
            print(f"    📍 Constructed URL for v{version}: {version_url}")
        
        print(f"  📄 Will try {len(version_pages)} specific versions")
        
    else:
        # Fallback to discovering versions from main page (no patch analysis)
        print("  🔍 No ReVanced patch analysis - discovering from main page...")
        version_pages = parser.get_all_version_pages(app['download_url'], limit=5)
        
        if not version_pages:
            print(f"  ✗ Could not find any version pages for {app['name']}")
            return False, []
        
        print(f"  📄 Found {len(version_pages)} versions to check")
    
    # Track what we've successfully found and downloaded
    found_variants = {}
    

    
    # Check each version for real architecture variants
    for version_info in version_pages:
        version_url = version_info['url']
        version_str = version_info['version']
        
        # Since we're using direct URLs, all versions in the list are supported
        if version_info.get('constructed'):
            print(f"  🔍 Checking version {version_str} - ✓ ReVanced supported!")
        else:
            print(f"  🔍 Checking version {version_str} (latest available)...")
        
        # Add delay to avoid rate limiting
        time.sleep(1)
        
        # Get variants from this version
        variants = parser._get_variants_from_version_page(version_url, architectures, prefer_nodpi, debug=False)
        
        if variants:
            print(f"    📦 Found {len(variants)} real variants in v{version_str}")
            
            for variant in variants:
                arch = variant['architecture']
                
                # Only download if we haven't found this architecture yet
                if arch not in found_variants:
                    filename = f"{app['package_name']}-v{version_str}-{arch}.apk"
                    output_path = app_dir / filename
                    
                    # Skip if already exists
                    if output_path.exists():
                        print(f"    ✓ {filename} already exists")
                        found_variants[arch] = str(output_path)
                        downloaded_files.append(str(output_path))
                        continue
                    
                    print(f"    ⬇️  Downloading {filename}...")
                    
                    # Get download link
                    direct_link = parser.get_direct_download_link(variant['url'], debug=False)
                    if not direct_link:
                        print(f"    ✗ Could not get download link for {arch}")
                        continue
                    
                    # Download
                    success = download_single_apk(direct_link, output_path, max_retries, retry_delay)
                    
                    if success:
                        print(f"    ✓ Downloaded {filename}")
                        
                        found_variants[arch] = str(output_path)
                        downloaded_files.append(str(output_path))
                    else:
                        print(f"    ✗ Failed to download {filename}")
                        if output_path.exists():
                            output_path.unlink()
                else:
                    print(f"    ⚠️  No variants found in v{version_str} - checking next version...")
        else:
            print(f"    ❌ No real variants found in v{version_str}")
        
        # Stop if we've found all requested architectures or we found the recommended version
        if not download_multiple or len(found_variants) >= len(architectures):
            break
        
        # Also stop if we successfully downloaded the recommended version
        if recommended_version and version_str == recommended_version and found_variants:
            print(f"  🎯 Successfully downloaded recommended version {recommended_version}")
            break
    
    # Check for missing architectures and log them
    requested_architectures = set(architectures)
    found_architectures = set(found_variants.keys())
    missing_architectures = requested_architectures - found_architectures
    
    if missing_architectures:
        print(f"  ⚠️  Missing architectures: {list(missing_architectures)}")
        
        # Save missing architecture info for investigation
        missing_info = {
            'app': app['name'],
            'package_name': app['package_name'],
            'requested_architectures': list(requested_architectures),
            'found_architectures': list(found_architectures),
            'missing_architectures': list(missing_architectures),
            'versions_checked': [v['version'] for v in version_pages],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Append to missing architectures log
        missing_log_file = DOWNLOADS_DIR / "missing_architectures.json"
        if missing_log_file.exists():
            with open(missing_log_file, 'r') as f:
                missing_log = json.load(f)
        else:
            missing_log = []
        
        missing_log.append(missing_info)
        
        with open(missing_log_file, 'w') as f:
            json.dump(missing_log, f, indent=2)
        
        print(f"  📝 Missing architecture info logged to: {missing_log_file}")
    
    # Summary
    if found_variants:
        print(f"  ✅ Successfully found variants for: {list(found_variants.keys())}")
    else:
        print(f"  ❌ No real architecture variants found for {app['name']}")
    
    success = len(downloaded_files) > 0
    return success, downloaded_files

def main():
    """
    Main function with proper exit code handling:
    - Exit 0: Success (at least some downloads completed)
    - Exit 1: Critical error (script crash, missing dependencies, config issues)
    - Exit 2: All downloads failed (but script ran successfully)
    """
    try:
        print("🚀 Starting APK downloads from APKMirror...\n")
        
        # Check dependencies
        if not BEAUTIFULSOUP_AVAILABLE:
            print("❌ Critical Error: BeautifulSoup4 is required for parsing APKMirror pages.")
            print("Please install it with: pip install beautifulsoup4")
            return 1  # Critical error - missing dependency
        
        try:
            config = load_config()
            settings = config.get('settings', {})
        except Exception as e:
            print(f"❌ Critical Error: Failed to load configuration: {e}")
            return 1  # Critical error - config issue
        
        print("📋 Configuration:")
        print(f"  Architectures: {settings.get('architectures', ['armeabi-v7a', 'arm64-v8a', 'x86_64', 'universal'])}")
        print(f"  Prefer noDPI: {settings.get('prefer_nodpi', True)}")
        print(f"  Download multiple architectures: {settings.get('download_multiple_architectures', True)}")
        print(f"  Max retries: {settings.get('max_retries', 3)}")
        
        results = {
            'successful': [],
            'failed': []
        }
        
        enabled_apps = [app for app in config['apps'] if app.get('enabled', True)]
        
        print(f"\n📱 Processing {len(enabled_apps)} enabled apps...\n")
        
        for i, app in enumerate(enabled_apps, 1):
            print(f"\n 📱 [{i}/{len(enabled_apps)}] {app['name']} - Processing...")
            
            success, paths = download_app_apks(app, settings)
            
            if success:
                results['successful'].append({
                    'app': app,
                    'paths': paths,
                    'count': len(paths)
                })
                print(f"  ✅ Successfully downloaded {len(paths)} APK(s)")
            else:
                results['failed'].append({
                    'app': app,
                    'error': 'No APK variants could be downloaded'
                })
                print(f"  ❌ Failed to download any APKs")
        
        # Save results for next step
        results_file = Path("downloads/download_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Summary
        total_apks = sum(item.get('count', 0) for item in results['successful'])
        
        print(f"\n{'='*60}")
        print(f"📊 Download Summary:")
        print(f"  Apps processed: {len(enabled_apps)}")
        print(f"  Apps successful: {len(results['successful'])}")
        print(f"  Apps failed: {len(results['failed'])}")
        print(f"  Total APKs downloaded: {total_apks}")
        print(f"{'='*60}")
        
        if results['successful']:
            print("\n✅ Successful downloads:")
            for item in results['successful']:
                app_name = item['app']['name']
                count = item.get('count', 0)
                print(f"  - {app_name}: {count} APK(s)")
        
        if results['failed']:
            print("\n❌ Failed downloads:")
            for item in results['failed']:
                print(f"  - {item['app']['name']}: {item['error']}")
        
        print(f"\n💾 Results saved to: {results_file}")
        
        # Return appropriate exit codes
        if len(results['successful']) == 0:
            print(f"\n⚠️  All downloads failed - exit code 2")
            return 2  # All downloads failed
        elif len(results['failed']) > 0:
            print(f"\n⚠️  Some downloads failed - exit code 0 (partial success)")
            return 0  # Partial success
        else:
            print(f"\n✅ All downloads successful - exit code 0")
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