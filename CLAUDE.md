# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Docker container unpack performance benchmarking project that measures pure extraction/unpacking time, isolated from download overhead. The project uses containerd's `ctr` commands with snapshot management to ensure accurate, reproducible benchmarks.

## Architecture

- **Benchmarking Target**: Pure containerd unpack phase (excluding download)
- **Isolation Method**: Docker-in-Docker setup with containerd inside containers
- **Metrics Collection**: Docker stats for real-time resource monitoring
- **Snapshot Management**: Clear unpacked layers between runs using `ctr snapshots rm`
- **Test Image Recommendation**: tensorflow/tensorflow:latest (16-17 second unpack time)

## Quick Start

```bash
# Build and run benchmark with default settings
docker compose build
docker compose up

# Custom benchmark
TARGET_IMAGE=docker.io/library/ubuntu:latest NUM_RUNS=10 docker compose up

# Clean restart with fresh cache
docker compose down -v
docker compose up
```

## Development Commands

- `docker compose build` - Build the optimized benchmark image
- `docker compose up` - Run benchmark with configured settings
- `docker compose down -v` - Clean up containers and volumes
- `TARGET_IMAGE=image:tag NUM_RUNS=N docker compose up` - Custom benchmark run

## Implementation Details

### Key Technical Decisions

1. **Snapshot Clearing Strategy**
   - Use `ctr snapshots rm` to remove unpacked filesystem layers
   - Preserves downloaded content in content store
   - Forces complete re-unpacking on each run
   - Ensures consistent benchmark conditions

2. **Pre-built Docker Image**
   - Dependencies installed during build (containerd, docker.io, python3)
   - Eliminates runtime installation overhead
   - Faster benchmark startup times

3. **Python Orchestration**
   - `run-benchmark.py` manages the entire benchmark lifecycle
   - Threaded stats collection at 100ms intervals
   - JSON output for programmatic analysis
   - Peak metric tracking (CPU, memory, PIDs)

### Critical Functions

- `ensure_image_downloaded()`: Pre-downloads image content once
- `clear_all_snapshots()`: Removes all unpacked layers via `ctr snapshots rm`
- `prepare_unpack_benchmark()`: Clears snapshots between each run
- `collect_stats()`: Background thread monitoring via `docker stats --format json`

### Benchmark Phases

1. **Initialization**: Start containerd daemon, create results directory
2. **Pre-download**: Pull image once to populate content store
3. **Benchmark Loop**:
   - Clear snapshots (remove unpacked layers)
   - Start metrics collection
   - Run `ctr image pull` (unpacks from content store)
   - Stop metrics collection
   - Record duration and peak metrics
4. **Results**: Save JSON with all runs and summary statistics

## Configuration

Key files:
- `.env` - Environment variables for benchmark configuration
- `docker-compose.yml` - Container orchestration and volume mounts
- `Dockerfile` - Pre-built image with all dependencies

Environment variables:
- `TARGET_IMAGE`: Container image to benchmark (default: tensorflow/tensorflow:latest)
- `NUM_RUNS`: Number of unpack iterations (default: 5)
- `OUTPUT_DIR`: Results directory (default: /workspace/results)
- `CONTAINER_NAME`: Docker container name for stats monitoring

## Key Concepts

- Focus on extraction/unpack performance rather than download performance
- Measure entire container performance instead of individual processes
- Use resource isolation to ensure accurate benchmarking results
- JSON output format for programmatic analysis

## Verified Performance Metrics

### TensorFlow Image (580MB compressed, 1.8GB uncompressed)
- **Unpack time**: 16-17 seconds
- **CPU usage**: 237% peak (multi-core)
- **Memory**: 196MB peak
- **Processes**: 76 peak

### Alpine Image (3.6MB compressed)
- **Unpack time**: 0.7-0.8 seconds
- **CPU usage**: 24% peak
- **Memory**: 55MB peak

## Important Implementation Notes

- **Use full image URLs**: Always use complete registry URLs (e.g., `docker.io/library/alpine:latest`)
- **Snapshot clearing is critical**: Without clearing snapshots, subsequent runs use cached unpacked layers (~0.7s instead of 16s for TensorFlow)
- **Volume persistence**: The `containerd-cache` volume preserves downloaded content across runs
- **Privileged mode required**: Docker-in-Docker needs privileged container access
- **CA certificates**: Essential for TLS registry communication