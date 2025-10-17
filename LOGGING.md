# 📊 Pipeline Status Tracking

This project includes comprehensive logging and tracking of all pipeline runs, patch results, and releases.

## 📁 Logging Structure

```
logs/
├── pipeline_history.json    # Complete history of all pipeline runs
├── release_history.json     # History of all GitHub releases
└── dashboard.html          # Visual dashboard (auto-generated)
```

## 🎯 What Gets Tracked

### Pipeline Runs

- **Trigger type**: Schedule, manual, config change
- **Download results**: Success/failure counts per app
- **Patch results**: Success/failure counts per architecture
- **Release creation**: Whether GitHub release was created
- **Issues created**: Number of issues opened for failures
- **Timing**: Complete timestamps and duration
- **GitHub metadata**: Run ID, commit SHA, actor

### Releases

- **Released apps**: All successfully patched APKs
- **Architecture variants**: Which CPU architectures per app
- **File sizes**: Total release size and per-APK breakdown
- **Release URLs**: Direct links to GitHub releases
- **App versions**: Exact version numbers patched

## 🔧 Usage

### View Pipeline Summary

```bash
python scripts/pipeline_orchestrator.py summary
```

### Generate Visual Dashboard

```bash
python scripts/dashboard_generator.py
```

### Manual Pipeline Logging

```bash
python scripts/pipeline_orchestrator.py log
```

## 📈 Dashboard Features

The auto-generated HTML dashboard (`logs/dashboard.html`) provides:

- **Success Rate Metrics**: Overall and recent pipeline performance
- **Recent Runs**: Last 10 pipeline executions with status
- **Release History**: Recent releases with app counts and sizes
- **Architecture Breakdown**: Which CPU variants were released
- **Direct Links**: Click-through to actual GitHub releases

## 🤖 Automated Integration

The GitHub Actions workflow automatically:

1. **Logs each pipeline run** with complete results
2. **Tracks release creation** with detailed app breakdown
3. **Commits logs to repository** for persistence
4. **Generates dashboard** after each run
5. **Maintains history limits** (50 runs, 30 releases max)

## 📊 Status Tracking Locations

| Information           | Primary Location             | Backup/Details           |
| --------------------- | ---------------------------- | ------------------------ |
| **Pipeline Overview** | `logs/pipeline_history.json` | GitHub Actions logs      |
| **Release Details**   | `logs/release_history.json`  | GitHub Releases API      |
| **Current Results**   | `output/patch_results.json`  | Temporary (cleaned up)   |
| **Visual Summary**    | `logs/dashboard.html`        | Auto-generated           |
| **Issues Created**    | GitHub Issues                | Tracked in pipeline logs |

## 🔄 Data Retention

- **Pipeline History**: Last 50 runs (auto-trimmed)
- **Release History**: Last 30 releases (auto-trimmed)
- **Dashboard**: Always current (regenerated each run)
- **GitHub Integration**: Permanent (until manually deleted)

This system provides complete visibility into your ReVanced patching pipeline's health and history!
