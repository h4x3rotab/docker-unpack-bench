# Container Unpack Performance Benchmark

Measures pure container image unpacking performance, isolated from download overhead.

## 🚀 One-Line Quick Start

```bash
curl -sL https://gist.githubusercontent.com/h4x3rotab/89374fdf8048550986f5e3b3935fa072/raw/gist-docker-compose.yml -o docker-compose.yml && docker compose up
```

## 🎯 Custom Benchmarks

```bash
# Quick Alpine test
curl -sL https://gist.githubusercontent.com/h4x3rotab/89374fdf8048550986f5e3b3935fa072/raw/gist-docker-compose.yml -o docker-compose.yml && TARGET_IMAGE=docker.io/library/alpine:latest NUM_RUNS=3 docker compose up

# Heavy TensorFlow benchmark with resource limits
curl -sL https://gist.githubusercontent.com/h4x3rotab/89374fdf8048550986f5e3b3935fa072/raw/gist-docker-compose.yml -o docker-compose.yml && TARGET_IMAGE=docker.io/tensorflow/tensorflow:latest NUM_RUNS=3 CPU_LIMIT=4 MEMORY_LIMIT=4g docker compose up
```

## 📊 View Results

```bash
# Summary
cat results/benchmark_*.json | jq '.summary'

# Peak metrics from latest run
cat results/benchmark_$(ls -t results/ | head -1) | jq '.runs[0].peak_metrics'

# All results
ls -la results/
```

## 🔧 How It Works

1. **Pre-download**: Downloads image layers once to populate content store
2. **Snapshot clearing**: Removes unpacked filesystem layers between runs  
3. **Pure unpack measurement**: Each run measures only extraction from content store to filesystem
4. **Metrics collection**: Captures CPU, Memory, Disk I/O, and Network stats during unpacking

## 📈 Sample Results

**TensorFlow Image** (580MB compressed, 1.8GB uncompressed):
- **Unpack time**: 15-17 seconds
- **CPU usage**: 240% peak (multi-core)
- **Disk writes**: 2.5-3.8GB during unpacking
- **Memory**: 200MB peak

**Alpine Image** (3.6MB compressed):
- **Unpack time**: 0.8-2.3 seconds  
- **CPU usage**: 25% peak
- **Disk writes**: 7-18MB during unpacking

## 🐳 Architecture

- **Docker-in-Docker**: Containerd runs inside Docker containers for isolation
- **Real-time monitoring**: Live CPU/Memory/Disk I/O stats during unpacking  
- **JSON output**: Structured results for analysis and automation
- **Volume caching**: Persistent storage for downloaded content across runs

## 🛠️ Requirements

- Docker with docker compose
- Privileged container support (for Docker-in-Docker)
- ~1GB free disk space for caching

## ⚙️ Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `TARGET_IMAGE` | Container image to benchmark | `docker.io/tensorflow/tensorflow:latest` | `docker.io/library/ubuntu:22.04` |
| `NUM_RUNS` | Number of benchmark iterations | `5` | `10` |
| `CPU_LIMIT` | CPU core limit (0=unlimited) | `0` | `2.0` |
| `MEMORY_LIMIT` | Memory limit (0=unlimited) | `0` | `4g` |

## 🔗 Links

- **Docker Hub**: https://hub.docker.com/r/h4x3rotab/bench-unpack
- **Source Code**: https://github.com/user/repo (if public)
