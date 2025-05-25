import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import argparse

# Extracted data will contain p50, p90, p95, p99
# TODO: Change to use p50, p95, and p99 latencies
LATENCY_PERCENTILE = 'p95'

def make_plot(plot='baseline', workload='ycsbt', latency_percentiles=[50, 95, 99]):

    # For the resource demads and cost, we use a different script
    if plot == 'baseline':
        x_lab = 'Multi-Home Txns (%)'
    elif plot == 'skew':
        x_lab = 'Skew factor (Theta)'
    elif plot == 'scalability':
        x_lab = 'Clients'
    elif plot == 'network':
        x_lab = 'Extra delay (ms)'
    elif plot == 'packet_loss':
        x_lab = 'Packets lost (%)'
    elif plot == 'example':
        x_lab = 'Example x-axis'

    # Read data from CSV
    csv_path = f'plots/data/final/{workload}/{plot}.csv'  # Adjust this path
    data = pd.read_csv(csv_path)

    # Extract data
    xaxis_points = data['x_var']
    # For some experiments, we have to adjust the x_values
    if workload == 'tpcc' and plot == 'baseline':
        #xaxis_points = [0, 4, 8, 15, 20, 25, 29]
        xaxis_points = [0, 4, 8, 15, 20, 25, 29, 32, 34, 36, 38, 39]
    elif workload == 'tpcc' and plot == 'skew':
        xaxis_points = [250 - point for point in xaxis_points]

    #metrics = ['throughput', LATENCY_PERCENTILE, 'aborts', 'bytes', 'cost']
    metrics = ['throughput', 'latency', 'aborts', 'bytes', 'cost']
    y_labels = [
        'Throughput (txn/s)',
        #f'{LATENCY_PERCENTILE} Latency (ms)',
        'Latency (ms)',
        'Aborts (%)',
        'Bytes Transferred (MB)',
        'Cost ($)'
    ]
    subplot_titles = ['Throughput', 'Latency', 'Aborts', 'Bytes', 'Cost']
    databases = ['Calvin', 'SLOG', 'Detock', 'Mencius', 'Caerus', 'ddr_only']
    line_styles = ['-', '--', '-.', ':', '-', '--']
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown']

    # Configure Matplotlib global font size
    plt.rcParams.update({
        'font.size': 12,        # Increase font size for better readability
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10
    })

    # Create figure and subplots
    fig, axes = plt.subplots(1, 5, figsize=(15, 3), sharex=True)

    for ax, metric, y_label, subplot_title in zip(axes, metrics, y_labels, subplot_titles):
        for db, color, style in zip(databases, colors, line_styles):
            if metric != 'latency':
                column_name = f'{db}_{metric}'
                if column_name in data.columns:  # Plot only if the column exists in the CSV
                    ax.plot(
                        xaxis_points,
                        data[column_name],
                        label=db,
                        color=color,
                        linestyle=style
                        # TODO: Find a way to distinguish between the the 3 percentiles (e.g., via darkness of the color)
                    )
            else:
                for percentile in latency_percentiles:
                    column_name = f'{db}_p{percentile}'
                    if column_name in data.columns:  # Plot only if the column exists in the CSV
                        ax.plot(
                            xaxis_points,
                            data[column_name],
                            label=db,
                            color=color,
                            linestyle=style
                        )

        ax.set_title(subplot_title)
        ax.set_ylabel(y_label)
        ax.set_xlabel(x_lab)
        ax.grid(True)
        if plot == 'baseline':
            ax.set_xticks(np.linspace(0, 100, 6))  # 0%, 20%, ..., 100%
            ax.set_xlim(0, 100)
        elif plot == 'skew':
            ax.set_xticks(np.linspace(0.0, 1.0, 6))  # 0.0, 0.2, ..., 1.0
            ax.set_xlim(0, 1)
        elif plot == 'scalability':
            ax.set_xlim(left=1)
            ax.set_xscale('log')
        elif plot == 'network':
            ax.set_xlim(left=0)
        elif plot == 'packet_loss':
            ax.set_xlim(0, 10)
        ax.set_ylim(bottom=0)  # Remove extra whitespace below y=0

    # Add legend and adjust layout
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=len(databases), bbox_to_anchor=(0.5, 1.1))
    plt.tight_layout(rect=[0, 0, 1, 1])  # Further reduce whitespace

    # Save figures
    output_path = f'plots/output/{workload}/{plot}'
    jpg_path = output_path + '.jpg'
    pdf_path = output_path + '.pdf'
    os.makedirs('/'.join(output_path.split('/')[:-1]), exist_ok=True)
    plt.savefig(jpg_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System Evaluation Script")
    parser.add_argument("-p",  "--plot", default="baseline", choices=["baseline", "skew", "scalability", "network", "packet_loss", "example"], help="The name of the experiment we want to plot.")
    parser.add_argument("-w",  "--workload", default="ycsbt", choices=["ycsbt", "tpcc"], help="The workload that was evaluated.")
    parser.add_argument("-lp", "--latency_percentiles", default="50;95;99", help="The latency percentiles to plot")
    args = parser.parse_args()

    latencies = [int(latency) for latency in args.latency_percentiles.split(';')]

    make_plot(plot=args.plot, workload=args.workload, latency_percentiles=latencies)

    print("Done")