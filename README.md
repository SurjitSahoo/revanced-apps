# Release Logs# ReVanced Apps Patch & Release Automation



This branch contains only the pipeline execution logs and release history for the ReVanced Apps project.## Project Overview



## Generated FilesThis project automates the process of downloading APK files for selected Android applications, patching them using [ReVanced CLI](https://github.com/ReVanced/revanced-cli), and publishing the successfully patched APKs as a GitHub Release. If any APK fails to patch, the workflow automatically creates a GitHub Issue with error details for further investigation.



- `pipeline_history.json` - Complete history of all pipeline runs**Key Features:**

- `release_history.json` - History of all GitHub releases created

- `pending_release.json` - Information about releases that are pending- Downloads APKs from specified mirror links.

- `dashboard.html` - HTML dashboard with pipeline status overview- Patches APKs using the latest ReVanced tools.

- Publishes patched APKs as a GitHub Release with summary notes.

## Purpose- Creates detailed GitHub Issues for failed patches.

- **📊 Comprehensive pipeline logging and status tracking**

This branch is automatically updated by GitHub Actions to keep logs separate from the main source code branch.- **🎯 Visual dashboard for monitoring pipeline health**

- Designed to run as a scheduled or manual GitHub Actions workflow.

The main source code remains clean in the `main` branch, while all operational logs are maintained here.

> **Note:** The project is a proof-of-concept for the backend automation. A companion Flutter client app is planned for the future.

Generated on: $(date)
---

## Project Structure

```
.env
.gitignore
requirements.txt
.github/
  workflows/
    patch_apps.yml
config/
  apps.json
scripts/
  downloader.py
  issue_manager.py
  patcher.py
  release_manager.py
  setup_revanced.py
```

### File & Directory Descriptions

#### Root Files

- **.env**  
  Stores environment variables such as `GITHUB_TOKEN` for local development. (Ignored by git.)

- **requirements.txt**  
  Lists Python dependencies:
  - `requests` (HTTP requests)
  - `PyGithub` (GitHub API)
  - `tqdm` (progress bars)

#### Configuration

- **config/apps.json**  
  Main configuration file listing the apps to patch.
  - Each app entry includes: `name`, `package_name`, `download_url`, `version`, `patches`, `exclude_patches`, and `enabled` flag.
  - `settings` section controls retry logic and issue creation.

#### GitHub Actions Workflow

- **.github/workflows/patch_apps.yml**  
  Defines the CI workflow:
  - Triggers on schedule, manual dispatch, or config changes.
  - Steps: checkout, set up Python/Java, install dependencies, run scripts, create releases/issues, and cleanup.

#### Scripts

- **scripts/setup_revanced.py**  
  Downloads the latest ReVanced CLI, patches, and integrations from GitHub releases.

- **scripts/downloader.py**  
  Downloads APKs for enabled apps from their configured URLs.

  - Handles retries and basic validation.
  - Saves results to `downloads/download_results.json`.

- **scripts/patcher.py**  
  Patches downloaded APKs using ReVanced CLI and tools.

  - Logs output and errors.
  - Saves patch results to `output/patch_results.json`.

- **scripts/release_manager.py**  
  Creates a GitHub Release for successfully patched APKs.

  - Attaches APKs and writes release notes.
  - Saves release info to `output/release_info.json`.

- **scripts/issue_manager.py**  
  Creates GitHub Issues for each failed patch.
  - Includes error logs and app configuration in the issue body.

---

## Workflow Summary

1. **Setup ReVanced Tools:**  
   Downloads the latest CLI, patches, and integrations.

2. **Download APKs:**  
   Fetches APKs for all enabled apps from their mirror links.

3. **Patch APKs:**  
   Uses ReVanced CLI to patch each APK. Logs results.

4. **Create GitHub Release:**  
   Publishes a release with all successfully patched APKs.

5. **Create Issues for Failures:**  
   For each failed patch, creates a GitHub Issue with logs and details.

6. **Log Pipeline Results:**  
   Records complete pipeline status, metrics, and generates visual dashboard.

7. **Cleanup:**  
   Removes temporary files and directories.

---

## 📊 Pipeline Monitoring

This project includes comprehensive logging and monitoring:

- **📈 Pipeline Status Tracking**: Complete history of all runs with success rates
- **🎁 Release History**: Detailed tracking of all GitHub releases
- **📱 Visual Dashboard**: Auto-generated HTML dashboard for easy monitoring
- **🔍 Failure Analysis**: Detailed logs and automatic issue creation

See [docs/LOGGING.md](docs/LOGGING.md) for complete documentation.

**Quick Commands:**

```bash
# View pipeline summary
python scripts/pipeline_orchestrator.py summary

# Generate visual dashboard
python scripts/dashboard_generator.py
```

---

## Future Work

- **Flutter Companion App:**  
  A client app will be developed to check for new releases and help users keep their patched apps up to date.

---

## References

- [ReVanced CLI](https://github.com/ReVanced/revanced-cli)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
