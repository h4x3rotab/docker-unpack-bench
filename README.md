# Container Unpack Performance Benchmark

## Overview

A Docker-based benchmarking system that accurately measures container image unpacking/extraction performance, isolating it from network download overhead. This tool uses containerd's `ctr` directly to benchmark the actual filesystem extraction phase.

## Key Features

- **Pure unpack measurement**: Separates download from extraction phases
- **Snapshot clearing**: Removes unpacked layers between runs while preserving downloaded content
- **Docker stats monitoring**: Captures CPU, memory, and process metrics during unpacking
- **JSON output**: Structured results for analysis and visualization
- **Docker-in-Docker isolation**: Ensures clean, reproducible benchmarking environment

## Benchmark Results

### TensorFlow Image (docker.io/tensorflow/tensorflow:latest)
- **Image size**: ~580MB compressed, ~1.8GB uncompressed
- **Unpack time**: 16-17 seconds average
- **CPU usage**: 237% peak (multi-core utilization)
- **Memory usage**: 196MB peak
- **Process count**: 76 processes peak

### Alpine Image (docker.io/library/alpine:latest)
- **Image size**: 3.6MB compressed
- **Unpack time**: 0.7-0.8 seconds
- **CPU usage**: 24% peak
- **Memory usage**: 55MB peak

## Quick Start

```bash
# Build the benchmark image
docker compose build

# Run benchmark with default settings (TensorFlow, 5 runs)
docker compose up

# Run with custom image and iterations
TARGET_IMAGE=docker.io/library/ubuntu:latest NUM_RUNS=10 docker compose up

# View results
ls -la results/
cat results/benchmark_*.json | jq '.summary'
```

## How It Works

### Architecture

1. **Pre-download Phase**: Downloads all image layers once using `ctr image pull`
2. **Snapshot Clearing**: Between runs, removes unpacked filesystem layers using `ctr snapshots rm`
3. **Pure Unpack Measurement**: Each run measures only the extraction from content store to filesystem
4. **Metrics Collection**: Docker stats monitors resource usage at 100ms intervals

### Technical Implementation

- **Containerd isolation**: Runs containerd inside Docker container for clean environment
- **Volume caching**: Persistent volume stores downloaded content across runs
- **Snapshot management**: Clears `/var/lib/containerd/io.containerd.snapshotter.v1.overlayfs` between runs
- **Python orchestration**: Manages benchmark runs, stats collection, and result aggregation

## Configuration

### Environment Variables (.env file)

```bash
# Target image to benchmark
TARGET_IMAGE=docker.io/tensorflow/tensorflow:latest

# Number of unpack iterations
NUM_RUNS=5
```

### Supported Images

Any valid container image URL:
- `docker.io/library/alpine:latest`
- `docker.io/tensorflow/tensorflow:latest`
- `docker.io/library/ubuntu:22.04`
- `gcr.io/your-project/your-image:tag`

## Output Format

Results are saved as JSON in the `results/` directory:

```json
{
  "benchmark_config": {
    "target_image": "docker.io/tensorflow/tensorflow:latest",
    "num_runs": 5,
    "timestamp": "2025-08-10T07:14:27.213540"
  },
  "summary": {
    "successful_runs": 5,
    "failed_runs": 0,
    "avg_duration_seconds": 16.68,
    "min_duration_seconds": 16.05,
    "max_duration_seconds": 17.31
  },
  "runs": [
    {
      "run_id": 1,
      "duration_seconds": 16.05,
      "peak_metrics": {
        "cpu_peak_percent": 237.73,
        "memory_peak_mb": 196.8,
        "pid_peak_count": 76
      }
    }
  ]
}
```

## Development

### Project Structure

```
.
├── docker-compose.yml   # Orchestration configuration
├── Dockerfile          # Pre-built image with dependencies
├── .env               # Environment configuration
├── scripts/
│   ├── entrypoint.sh  # Container startup script
│   └── run-benchmark.py # Main benchmark logic
└── results/           # JSON output files
```

### Key Components

- **Dockerfile**: Pre-installs containerd, docker.io, python3 for fast startup
- **run-benchmark.py**: Orchestrates benchmark runs, snapshot clearing, and metrics collection
- **docker-compose.yml**: Configures privileged container with necessary mounts

## Troubleshooting

### Benchmark shows fast times (~0.7s for large images)

**Cause**: Snapshots not properly cleared, containerd using cached unpacked layers

**Solution**: Ensure `ctr snapshots rm` is called between runs. Check implementation in `prepare_unpack_benchmark()`

### "Missing parent bucket: not found" error

**Cause**: Corrupted containerd cache from incomplete cleanup

**Solution**: Reset the cache volume:
```bash
docker compose down -v
docker compose up
```

### Metrics not collected

**Cause**: Docker socket not mounted or stats collection timing issue

**Solution**: Verify `/var/run/docker.sock` is mounted in docker-compose.yml

## Contributing

Contributions welcome! Key areas for improvement:
- Support for different storage drivers (devicemapper, btrfs, zfs)
- Parallel benchmark runs for throughput testing  
- Integration with CI/CD systems
- Advanced metrics visualization