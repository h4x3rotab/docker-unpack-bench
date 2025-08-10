#!/usr/bin/env python3
"""
Convert benchmark JSON results to CSV format for analysis.
"""
import json
import os
import sys
import glob
from datetime import datetime

def extract_basic_stats(result_file):
    """Extract basic statistics from a benchmark JSON file."""
    try:
        with open(result_file, 'r') as f:
            data = json.load(f)
        
        config = data.get('benchmark_config', {})
        summary = data.get('summary', {})
        runs = data.get('runs', [])
        
        # Get peak metrics across all successful runs
        successful_runs = [r for r in runs if r.get('success', False)]
        if not successful_runs:
            return None
            
        # Calculate peak metrics across all runs
        all_metrics = [r.get('peak_metrics', {}) for r in successful_runs]
        
        max_cpu = max((m.get('cpu_peak_percent', 0) for m in all_metrics), default=0)
        max_mem = max((m.get('memory_peak_mb', 0) for m in all_metrics), default=0)
        max_write = max((m.get('block_io_total_write_mb', 0) for m in all_metrics), default=0)
        avg_cpu = sum(m.get('cpu_avg_percent', 0) for m in all_metrics) / len(all_metrics) if all_metrics else 0
        avg_mem = sum(m.get('memory_avg_mb', 0) for m in all_metrics) / len(all_metrics) if all_metrics else 0
        
        return {
            'timestamp': config.get('timestamp', ''),
            'target_image': config.get('target_image', ''),
            'num_runs': config.get('num_runs', 0),
            'cpu_limit': config.get('cpu_limit', '0'),
            'memory_limit': config.get('memory_limit', '0'),
            'successful_runs': summary.get('successful_runs', 0),
            'failed_runs': summary.get('failed_runs', 0),
            'avg_duration_seconds': summary.get('avg_duration_seconds', 0),
            'min_duration_seconds': summary.get('min_duration_seconds', 0),
            'max_duration_seconds': summary.get('max_duration_seconds', 0),
            'peak_cpu_percent': max_cpu,
            'avg_cpu_percent': avg_cpu,
            'peak_memory_mb': max_mem,
            'avg_memory_mb': avg_mem,
            'total_disk_write_mb': max_write,
            'filename': os.path.basename(result_file)
        }
    except Exception as e:
        print(f"Error processing {result_file}: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) > 1:
        results_dir = sys.argv[1]
    else:
        results_dir = "tmp/results"
    
    if not os.path.exists(results_dir):
        print(f"Results directory '{results_dir}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Find all benchmark JSON files
    pattern = os.path.join(results_dir, "benchmark_*.json")
    result_files = glob.glob(pattern)
    
    if not result_files:
        print(f"No benchmark files found in {results_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Sort files by modification time (newest first)
    result_files.sort(key=os.path.getmtime, reverse=True)
    
    # Extract statistics from all files
    all_stats = []
    for result_file in result_files:
        stats = extract_basic_stats(result_file)
        if stats:
            all_stats.append(stats)
    
    if not all_stats:
        print("No valid benchmark data found", file=sys.stderr)
        sys.exit(1)
    
    # Print transposed CSV (metrics as rows, runs as columns)
    headers = [
        'timestamp', 'target_image', 'num_runs', 'cpu_limit', 'memory_limit',
        'successful_runs', 'failed_runs', 'avg_duration_seconds', 
        'min_duration_seconds', 'max_duration_seconds',
        'peak_cpu_percent', 'avg_cpu_percent', 'peak_memory_mb', 'avg_memory_mb',
        'total_disk_write_mb', 'filename'
    ]
    
    # Create column headers from filenames (shortened)
    col_headers = ['metric'] + [stats['filename'].replace('benchmark_', '').replace('.json', '') for stats in all_stats]
    print(','.join(col_headers))
    
    # Print each metric as a row
    for header in headers:
        row = [header]
        for stats in all_stats:
            row.append(str(stats.get(header, '')))
        print(','.join(row))

if __name__ == "__main__":
    main()