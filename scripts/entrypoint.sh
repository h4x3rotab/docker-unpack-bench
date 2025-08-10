#!/bin/bash
set -e

# Configuration from environment variables
TARGET_IMAGE="${TARGET_IMAGE:-docker.io/tensorflow/tensorflow:latest}"
NUM_RUNS="${NUM_RUNS:-5}"
OUTPUT_DIR="${OUTPUT_DIR:-/workspace/results}"
CONTAINER_NAME="${CONTAINER_NAME:-unpack-benchmark}"
CPU_LIMIT="${CPU_LIMIT:-0}"
MEMORY_LIMIT="${MEMORY_LIMIT:-0}"

echo "🚀 Starting unpack benchmark"
echo "  Image: $TARGET_IMAGE"
echo "  Runs: $NUM_RUNS"
echo "  Container: $CONTAINER_NAME"
echo "  CPU Limit: $CPU_LIMIT"
echo "  Memory Limit: $MEMORY_LIMIT"

# Ensure results directory exists
mkdir -p "$OUTPUT_DIR"

echo "⚙️  Dependencies pre-installed via Dockerfile"

# Start containerd in background
echo "🔧 Starting containerd daemon..."
containerd -c /etc/containerd/config.toml > /var/log/containerd.log 2>&1 &
CONTAINERD_PID=$!

# Wait for containerd to be ready
echo "⏳ Waiting for containerd to be ready..."
for i in {1..30}; do
    if ctr version > /dev/null 2>&1; then
        echo "✅ containerd is ready"
        break
    fi
    sleep 1
done

if ! ctr version > /dev/null 2>&1; then
    echo "❌ Failed to start containerd"
    exit 1
fi

# Generate timestamp for this benchmark session
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_FILE="$OUTPUT_DIR/benchmark_${TIMESTAMP}.json"

echo "📊 Starting benchmark session..."
echo "  Results will be saved to: $RESULT_FILE"

# Run the benchmark script
python3 /workspace/scripts/run-benchmark.py "$TARGET_IMAGE" "$NUM_RUNS" "$RESULT_FILE" "$CONTAINER_NAME" "$CPU_LIMIT" "$MEMORY_LIMIT"

echo "✅ Benchmark completed! Results saved to $RESULT_FILE"

# Keep container running for inspection (optional)
# sleep infinity