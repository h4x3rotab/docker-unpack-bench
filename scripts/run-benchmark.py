#!/usr/bin/env python3
"""
Container extraction performance benchmark using docker stats and containerd.
"""
import json
import subprocess
import threading
import time
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

class BenchmarkRunner:
    def __init__(self, target_image: str, num_runs: int, output_file: str, container_name: str):
        self.target_image = target_image
        self.num_runs = num_runs
        self.output_file = output_file
        self.container_name = container_name
        self.stats_data: List[Dict] = []
        self.stats_thread = None
        self.monitoring = False

    def collect_stats(self):
        """Collect docker stats in a separate thread using JSON format."""
        print(f"📈 Starting stats collection for container: {self.container_name}")

        cmd = ["docker", "stats", self.container_name, "--format", "json", "--no-stream"]
        sample_count = 0

        while self.monitoring:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    stats_json = json.loads(result.stdout.strip())
                    stats_json['timestamp'] = datetime.now().isoformat()
                    self.stats_data.append(stats_json)

                    # Show live progress every second (10 samples at 100ms)
                    sample_count += 1
                    if sample_count % 10 == 0:
                        self.show_live_progress(stats_json)

                time.sleep(0.1)  # Sample every 100ms
            except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
                # Continue monitoring even if we get occasional errors
                time.sleep(0.1)
                continue

    def start_monitoring(self):
        """Start monitoring in background thread."""
        self.monitoring = True
        self.stats_data = []
        self.stats_thread = threading.Thread(target=self.collect_stats, daemon=True)
        self.stats_thread.start()
        time.sleep(0.5)  # Give monitoring a moment to start

    def stop_monitoring(self):
        """Stop monitoring and return collected data."""
        self.monitoring = False
        if self.stats_thread:
            self.stats_thread.join(timeout=2)
        return self.stats_data.copy()

    def ensure_image_downloaded(self):
        """Ensure the image is downloaded but not unpacked."""
        try:
            # Check if content already exists by trying to pull
            print(f"⬇️  Ensuring {self.target_image} content is available...")
            result = subprocess.run(["ctr", "image", "pull", self.target_image],
                                  capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise Exception(f"Failed to download image: {result.stderr}")
            print(f"✅ Image content ready")

            # Now remove all snapshots to clear unpacked data
            # This keeps downloaded content but removes extracted layers
            self.clear_all_snapshots()

        except Exception as e:
            raise Exception(f"Failed to prepare image: {str(e)}")

    def clear_all_snapshots(self):
        """Clear all snapshots to force re-unpacking while keeping content."""
        print("- Clear all snapshots")
        try:
            # List all snapshots (without -q flag which isn't supported)
            result = subprocess.run(["ctr", "snapshots", "list"],
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                # Skip header line and extract snapshot names from first column
                snapshots = []
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        # First column is the snapshot key/name
                        snapshot_name = line.split()[0]
                        snapshots.append(snapshot_name)
                
                if snapshots:
                    print(f"🧹 Clearing {len(snapshots)} snapshots to force re-unpacking...")
                    for snapshot in snapshots:
                        subprocess.run(["ctr", "snapshots", "rm", snapshot],
                                     capture_output=True)

            # Also remove the image metadata to force re-unpacking
            subprocess.run(["ctr", "image", "rm", self.target_image],
                         capture_output=True)

        except Exception as e:
            print(f"   Warning: {str(e)}")
            pass  # Ignore errors, this is cleanup

    def prepare_unpack_benchmark(self):
        """Prepare for pure unpack benchmark by clearing snapshots."""
        # Clear all snapshots to force complete re-unpacking
        self.clear_all_snapshots()

    def run_single_benchmark(self, run_id: int) -> Dict[str, Any]:
        """Run a single benchmark iteration focusing on unpack phase only."""
        print(f"🔄 Run {run_id}/{self.num_runs}: Preparing...")

        # Remove image but keep layers for pure unpack benchmark
        self.prepare_unpack_benchmark()

        # Start monitoring
        self.start_monitoring()

        print(f"🔄 Run {run_id}/{self.num_runs}: Unpacking {self.target_image}...")
        start_time = time.time()

        # Run containerd pull - with snapshots cleared, this will unpack from content store
        cmd = ["ctr", "image", "pull", self.target_image]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            end_time = time.time()

            # Stop monitoring and clear progress line
            stats_data = self.stop_monitoring()
            print()  # New line after progress display

            duration = end_time - start_time
            success = result.returncode == 0

            if success:
                print(f"✅ Run {run_id}/{self.num_runs}: Unpacked in {duration:.3f}s")
            else:
                print(f"❌ Run {run_id}/{self.num_runs}: Failed after {duration:.3f}s")
                print(f"Error: {result.stderr}")

            # Parse stats for peak values
            peak_stats = self.analyze_stats(stats_data)

            return {
                "run_id": run_id,
                "success": success,
                "duration_seconds": duration,
                "target_image": self.target_image,
                "peak_metrics": peak_stats,
                "raw_stats_count": len(stats_data),
                "containerd_stdout": result.stdout,
                "containerd_stderr": result.stderr if not success else ""
            }

        except subprocess.TimeoutExpired:
            self.stop_monitoring()
            print(f"⏰ Run {run_id}/{self.num_runs}: Timeout after 300s")
            return {
                "run_id": run_id,
                "success": False,
                "duration_seconds": 300,
                "target_image": self.target_image,
                "error": "timeout"
            }

    def analyze_stats(self, stats_data: List[Dict]) -> Dict[str, Any]:
        """Analyze collected stats to find peak values from JSON data."""
        if not stats_data:
            return {}

        try:
            cpu_values = []
            memory_values = []
            pid_values = []
            block_io_read = []
            block_io_write = []
            net_io_rx = []
            net_io_tx = []

            for stat in stats_data:
                # All fields are now from JSON format

                # Parse CPU (e.g., "25.45%" -> 25.45)
                cpu_str = stat.get('CPUPerc', '0%').replace('%', '')
                try:
                    cpu_values.append(float(cpu_str))
                except ValueError:
                    pass

                # Parse Memory (e.g., "150.1MiB / 31.33GiB")
                mem_usage = stat.get('MemUsage', '0B / 0B')
                if ' / ' in mem_usage:
                    mem_str = mem_usage.split(' / ')[0]
                    memory_values.append(self.parse_size_to_mb(mem_str))

                # Parse PIDs (already a string number in JSON)
                try:
                    pid_values.append(int(stat.get('PIDs', '0')))
                except (ValueError, TypeError):
                    pass

                # Parse Block I/O (e.g., "1.56MB / 10.2MB")
                block_io = stat.get('BlockIO', '0B / 0B')
                if ' / ' in block_io:
                    read_str, write_str = block_io.split(' / ')
                    block_io_read.append(self.parse_size_to_mb(read_str))
                    block_io_write.append(self.parse_size_to_mb(write_str))

                # Parse Network I/O (e.g., "648KB / 12KB")
                net_io = stat.get('NetIO', '0B / 0B')
                if ' / ' in net_io:
                    rx_str, tx_str = net_io.split(' / ')
                    net_io_rx.append(self.parse_size_to_mb(rx_str))
                    net_io_tx.append(self.parse_size_to_mb(tx_str))

            return {
                "cpu_peak_percent": max(cpu_values) if cpu_values else 0,
                "cpu_avg_percent": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                "memory_peak_mb": max(memory_values) if memory_values else 0,
                "memory_avg_mb": sum(memory_values) / len(memory_values) if memory_values else 0,
                "pid_peak_count": max(pid_values) if pid_values else 0,
                "block_io_read_peak_mb": max(block_io_read) if block_io_read else 0,
                "block_io_write_peak_mb": max(block_io_write) if block_io_write else 0,
                "block_io_total_write_mb": block_io_write[-1] if block_io_write else 0,
                "net_io_rx_mb": max(net_io_rx) if net_io_rx else 0,
                "net_io_tx_mb": max(net_io_tx) if net_io_tx else 0,
                "samples_collected": len(stats_data)
            }
        except Exception as e:
            return {"error": f"Stats analysis failed: {str(e)}"}

    def parse_size_to_mb(self, size_str: str) -> float:
        """Parse size string like '1.56MB', '2.3GiB', '512KB' to MB."""
        size_str = size_str.strip()
        if not size_str or size_str == '0B':
            return 0.0

        try:
            # Extract number and unit using regex
            import re
            match = re.match(r'^([0-9.]+)\s*([A-Za-z]+)$', size_str)
            if not match:
                return 0.0

            value = float(match.group(1))
            unit = match.group(2).upper()

            # Convert to MB based on unit
            conversions = {
                'B': 1 / (1024 * 1024),
                'KB': 1 / 1024,
                'KIB': 1 / 1024,
                'MB': 1,
                'MIB': 1,
                'GB': 1024,
                'GIB': 1024,
                'TB': 1024 * 1024,
                'TIB': 1024 * 1024
            }

            return value * conversions.get(unit, 1)
        except (ValueError, AttributeError):
            return 0.0

    def show_live_progress(self, current_stats: Dict):
        """Display live progress during unpacking."""
        try:
            # Parse current stats
            cpu = current_stats.get('CPUPerc', '0%').replace('%', '')
            mem_usage = current_stats.get('MemUsage', '0B / 0B').split(' / ')[0]
            block_io = current_stats.get('BlockIO', '0B / 0B')
            pids = current_stats.get('PIDs', '0')

            # Parse block I/O
            read_write = block_io.split(' / ')
            read_mb = self.parse_size_to_mb(read_write[0]) if len(read_write) > 0 else 0
            write_mb = self.parse_size_to_mb(read_write[1]) if len(read_write) > 1 else 0
            mem_mb = self.parse_size_to_mb(mem_usage)

            # Show progress line (overwrite previous)
            progress = f"\r⚡ CPU: {cpu:>6}% | Mem: {mem_mb:>6.1f}MB | Write: {write_mb:>7.1f}MB | PIDs: {pids:>2}"
            print(progress, end='', flush=True)

        except Exception:
            pass  # Don't let progress display break the benchmark

    def run_benchmark_suite(self) -> Dict[str, Any]:
        """Run the complete benchmark suite."""
        print(f"🎯 Starting unpack benchmark suite")
        print(f"   Target: {self.target_image}")
        print(f"   Runs: {self.num_runs}")

        # First, ensure the image is downloaded
        self.ensure_image_downloaded()

        results = []
        for i in range(1, self.num_runs + 1):
            run_result = self.run_single_benchmark(i)
            results.append(run_result)

            # Brief pause between runs
            if i < self.num_runs:
                time.sleep(2)

        # Generate summary statistics
        successful_runs = [r for r in results if r.get('success', False)]
        durations = [r['duration_seconds'] for r in successful_runs]

        summary = {
            "benchmark_config": {
                "target_image": self.target_image,
                "num_runs": self.num_runs,
                "timestamp": datetime.now().isoformat()
            },
            "summary": {
                "successful_runs": len(successful_runs),
                "failed_runs": len(results) - len(successful_runs),
                "avg_duration_seconds": sum(durations) / len(durations) if durations else 0,
                "min_duration_seconds": min(durations) if durations else 0,
                "max_duration_seconds": max(durations) if durations else 0
            },
            "runs": results
        }

        return summary

    def save_results(self, results: Dict[str, Any]):
        """Save results to JSON file."""
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to: {self.output_file}")

def main():
    print(f"🐍 Python benchmark script starting...")
    print(f"   Script: {sys.argv[0]}")
    print(f"   Arguments: {sys.argv[1:]}")

    if len(sys.argv) != 5:
        print("Usage: run-benchmark.py <target_image> <num_runs> <output_file> <container_name>")
        sys.exit(1)

    target_image = sys.argv[1]
    num_runs = int(sys.argv[2])
    output_file = sys.argv[3]
    container_name = sys.argv[4]

    print(f"🎯 Initializing benchmark runner...")
    print(f"   Target: {target_image}")
    print(f"   Runs: {num_runs}")
    print(f"   Output: {output_file}")

    runner = BenchmarkRunner(target_image, num_runs, output_file, container_name)

    try:
        results = runner.run_benchmark_suite()
        runner.save_results(results)

        # Print summary
        summary = results['summary']
        print(f"\n📊 Benchmark Summary:")
        print(f"   Successful runs: {summary['successful_runs']}/{num_runs}")
        print(f"   Average duration: {summary['avg_duration_seconds']:.3f}s")
        if summary['successful_runs'] > 0:
            print(f"   Duration range: {summary['min_duration_seconds']:.3f}s - {summary['max_duration_seconds']:.3f}s")

            # Show peak metrics from all runs if available
            if results.get('runs') and len(results['runs']) > 0:
                # Get max values across all runs
                all_metrics = [r.get('peak_metrics', {}) for r in results['runs'] if r.get('success')]
                if all_metrics:
                    max_cpu = max((m.get('cpu_peak_percent', 0) for m in all_metrics), default=0)
                    max_mem = max((m.get('memory_peak_mb', 0) for m in all_metrics), default=0)
                    max_write = max((m.get('block_io_total_write_mb', 0) for m in all_metrics), default=0)

                    print(f"\n📈 Peak Metrics:")
                    print(f"   CPU: {max_cpu:.1f}%")
                    print(f"   Memory: {max_mem:.1f} MB")
                    print(f"   Disk Write: {max_write:.1f} MB")

    except KeyboardInterrupt:
        print("\n🛑 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Benchmark failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
