# Benchmark Results

This directory contains test results from various benchmarks.

## Structure

```
results/
├── README.md
├── alfworld/
│   ├── run_1.json
│   ├── run_1.csv
│   └── run_1_summary.txt
├── stulife/
│   └── ...
└── webshop/
    └── ...
```

## Result Files

Each benchmark run generates three files:

1. **{run_id}.json** - Complete results in JSON format
   - Configuration
   - Agent tree details
   - All episode results
   - Summary statistics

2. **{run_id}.csv** - Episode-level data in CSV format
   - Easy to analyze with spreadsheet tools
   - One row per episode

3. **{run_id}_summary.txt** - Human-readable summary
   - Overall statistics
   - Per-agent performance
   - Per-task-type performance

## Viewing Results

Run the results viewer:
```bash
python scripts/view_results.py --benchmark alfworld --run latest
```

Or manually open the files in this directory.

## Data Excluded from Git

Result data files (*.json, *.csv) are excluded from git to keep the repository clean.
Only the directory structure and README are tracked.
