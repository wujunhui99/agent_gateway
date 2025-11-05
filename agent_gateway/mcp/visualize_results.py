#!/usr/bin/env python3
"""Generate performance comparison visualizations."""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Read results
results_file = Path(__file__).parent / "benchmark_results.json"
with open(results_file) as f:
    data = json.load(f)

baseline = data["baseline"]
optimized = data["optimized"]

# Extract test names (remove prefix)
test_names = [r["name"].replace("Baseline - ", "").replace("_", " ").title() for r in baseline]


def plot_latency_comparison():
    """Plot latency comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Baseline latencies
    baseline_avg = [r["avg_time_ms"] for r in baseline]
    baseline_p95 = [r["p95_time_ms"] for r in baseline]

    # Optimized latencies
    optimized_avg = [r["avg_time_ms"] for r in optimized]
    optimized_p95 = [r["p95_time_ms"] for r in optimized]

    x = np.arange(len(test_names))
    width = 0.35

    # Plot 1: Average latency
    bars1 = ax1.bar(x - width/2, baseline_avg, width, label='Baseline', color='#e74c3c')
    bars2 = ax1.bar(x + width/2, optimized_avg, width, label='Optimized', color='#2ecc71')

    ax1.set_ylabel('Average Latency (ms)', fontsize=12)
    ax1.set_title('Average Latency Comparison', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(test_names, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=8)

    # Plot 2: P95 latency
    bars3 = ax2.bar(x - width/2, baseline_p95, width, label='Baseline', color='#e74c3c')
    bars4 = ax2.bar(x + width/2, optimized_p95, width, label='Optimized', color='#2ecc71')

    ax2.set_ylabel('P95 Latency (ms)', fontsize=12)
    ax2.set_title('P95 Latency Comparison', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(test_names, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('latency_comparison.png', dpi=300, bbox_inches='tight')
    print("✓ Saved latency_comparison.png")
    plt.close()


def plot_throughput_comparison():
    """Plot throughput comparison."""
    fig, ax = plt.subplots(figsize=(14, 8))

    baseline_throughput = [r["throughput"] for r in baseline]
    optimized_throughput = [r["throughput"] for r in optimized]

    x = np.arange(len(test_names))
    width = 0.35

    bars1 = ax.bar(x - width/2, baseline_throughput, width, label='Baseline', color='#e74c3c')
    bars2 = ax.bar(x + width/2, optimized_throughput, width, label='Optimized', color='#2ecc71')

    ax.set_ylabel('Throughput (calls/sec)', fontsize=12)
    ax.set_title('Throughput Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(test_names, rotation=45, ha='right')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=8, rotation=0)

    plt.tight_layout()
    plt.savefig('throughput_comparison.png', dpi=300, bbox_inches='tight')
    print("✓ Saved throughput_comparison.png")
    plt.close()


def plot_improvement_percentage():
    """Plot improvement percentage."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Calculate improvements
    latency_improvements = [
        (baseline[i]["avg_time_ms"] - optimized[i]["avg_time_ms"]) / baseline[i]["avg_time_ms"] * 100
        for i in range(len(baseline))
    ]

    throughput_improvements = [
        (optimized[i]["throughput"] - baseline[i]["throughput"]) / baseline[i]["throughput"] * 100
        for i in range(len(baseline))
    ]

    x = np.arange(len(test_names))

    # Plot 1: Latency improvement
    bars1 = ax1.barh(x, latency_improvements, color='#3498db')
    ax1.set_xlabel('Latency Reduction (%)', fontsize=12)
    ax1.set_title('Latency Improvement by Test', fontsize=14, fontweight='bold')
    ax1.set_yticks(x)
    ax1.set_yticklabels(test_names)
    ax1.grid(axis='x', alpha=0.3)

    # Add value labels
    for i, bar in enumerate(bars1):
        width = bar.get_width()
        ax1.text(width - 5, bar.get_y() + bar.get_height()/2.,
                f'{width:.1f}%',
                ha='right', va='center', fontsize=10, fontweight='bold', color='white')

    # Plot 2: Throughput improvement
    bars2 = ax2.barh(x, throughput_improvements, color='#9b59b6')
    ax2.set_xlabel('Throughput Increase (%)', fontsize=12)
    ax2.set_title('Throughput Improvement by Test', fontsize=14, fontweight='bold')
    ax2.set_yticks(x)
    ax2.set_yticklabels(test_names)
    ax2.grid(axis='x', alpha=0.3)

    # Add value labels
    for i, bar in enumerate(bars2):
        width = bar.get_width()
        # Format large numbers more readably
        if width > 10000:
            label = f'{width/1000:.1f}k%'
        else:
            label = f'{width:.0f}%'
        ax2.text(width * 0.95, bar.get_y() + bar.get_height()/2.,
                label,
                ha='right', va='center', fontsize=10, fontweight='bold', color='white')

    plt.tight_layout()
    plt.savefig('improvement_percentage.png', dpi=300, bbox_inches='tight')
    print("✓ Saved improvement_percentage.png")
    plt.close()


def plot_summary_metrics():
    """Plot summary metrics."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Metric 1: Average latency
    ax = axes[0, 0]
    avg_baseline = np.mean([r["avg_time_ms"] for r in baseline])
    avg_optimized = np.mean([r["avg_time_ms"] for r in optimized])
    bars = ax.bar(['Baseline', 'Optimized'], [avg_baseline, avg_optimized], color=['#e74c3c', '#2ecc71'])
    ax.set_ylabel('Average Latency (ms)')
    ax.set_title('Overall Average Latency', fontweight='bold')
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.2f}ms',
               ha='center', va='bottom', fontsize=12, fontweight='bold')

    # Metric 2: Average throughput
    ax = axes[0, 1]
    avg_baseline_tput = np.mean([r["throughput"] for r in baseline])
    avg_optimized_tput = np.mean([r["throughput"] for r in optimized])
    bars = ax.bar(['Baseline', 'Optimized'], [avg_baseline_tput, avg_optimized_tput], color=['#e74c3c', '#2ecc71'])
    ax.set_ylabel('Throughput (calls/sec)')
    ax.set_title('Overall Average Throughput', fontweight='bold')
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}/s',
               ha='center', va='bottom', fontsize=12, fontweight='bold')

    # Metric 3: Latency reduction
    ax = axes[1, 0]
    reduction = (avg_baseline - avg_optimized) / avg_baseline * 100
    bars = ax.bar(['Latency Reduction'], [reduction], color='#3498db')
    ax.set_ylabel('Improvement (%)')
    ax.set_title('Average Latency Reduction', fontweight='bold')
    ax.set_ylim([0, 105])
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}%',
               ha='center', va='bottom', fontsize=14, fontweight='bold')

    # Metric 4: Speedup factor
    ax = axes[1, 1]
    speedup = avg_baseline / avg_optimized
    bars = ax.bar(['Speedup Factor'], [speedup], color='#9b59b6')
    ax.set_ylabel('Factor')
    ax.set_title('Average Speedup Factor', fontweight='bold')
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.0f}x',
               ha='center', va='bottom', fontsize=14, fontweight='bold')

    plt.tight_layout()
    plt.savefig('summary_metrics.png', dpi=300, bbox_inches='tight')
    print("✓ Saved summary_metrics.png")
    plt.close()


def main():
    """Generate all visualizations."""
    print("\n📊 Generating performance visualizations...")

    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
    except ImportError:
        print("❌ Error: matplotlib is required")
        print("Install it with: pip install matplotlib")
        return

    plot_latency_comparison()
    plot_throughput_comparison()
    plot_improvement_percentage()
    plot_summary_metrics()

    print("\n✅ All visualizations generated successfully!")
    print("\nGenerated files:")
    print("  - latency_comparison.png")
    print("  - throughput_comparison.png")
    print("  - improvement_percentage.png")
    print("  - summary_metrics.png")


if __name__ == "__main__":
    main()
