import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import argparse



def make_plot():

    if args.plot == 'mh_proportions':
        x_lab = 'Multi-Home Txns (%)'
    elif args.plot == 'network':
        x_lab = 'Max bandwidth (Gbps)'
    elif args.plot == 'skew':
        x_lab = 'Skew factor (Theta)'
    elif args.plot == 'scalability':
        x_lab = 'Machines per region'

    # Read data from CSV
    csv_path = f'plots/data/{args.plot}.csv'  # Adjust this path
    data = pd.read_csv(csv_path)

    # Extract data
    percent_multi_home = data['PercentMultiHome']
    metrics = ['Latency', 'Throughput', 'BytesTransferred', 'Aborts', 'Cost']
    y_labels = [
        'Latency (ms)',
        'Throughput (txn/s)',
        'Bytes Transferred (MB)',
        'Aborts (#)',
        'Cost ($)'
    ]
    databases = ['Calvin', 'SLOG', 'Detock', 'Mencius', 'Atomic Multicast', 'Caerus']
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

    for ax, metric, y_label in zip(axes, metrics, y_labels):
        for db, color, style in zip(databases, colors, line_styles):
            column_name = f'{metric}_{db}'
            if column_name in data.columns:  # Plot only if the column exists in the CSV
                ax.plot(
                    percent_multi_home,
                    data[column_name],
                    label=db,
                    color=color,
                    linestyle=style
                )
        ax.set_title(metric)
        ax.set_ylabel(y_label)
        ax.set_xlabel(x_lab)
        ax.grid(True)
        if args.plot == 'mh_proportions':
            ax.set_xticks(np.linspace(0, 100, 6))  # 0%, 20%, ..., 100%
            ax.set_xlim(0, 100)
        elif args.plot == 'network':
            ax.set_xlim(left=0)
        elif args.plot == 'skew':
            ax.set_xticks(np.linspace(0.0, 1.0, 6))  # 0.0, 0.2, ..., 1.0
            ax.set_xlim(0, 1)
        elif args.plot == 'scalability':
            ax.set_xlim(left=1)
        ax.set_ylim(bottom=0)  # Remove extra whitespace below y=0

    # Add legend and adjust layout
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=len(databases), bbox_to_anchor=(0.5, 1.1))
    plt.tight_layout(rect=[0, 0, 1, 1])  # Further reduce whitespace

    # Save figures
    output_path = f'plots/output/{args.plot}'
    jpg_path = output_path + '.jpg'
    pdf_path = output_path + '.pdf'
    plt.savefig(jpg_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System Evaluation Script")
    parser.add_argument("plot", default="mh_proportions", choices=["mh_proportions", "network", "skew", "scalability"], help="Action to perform: start or stop the cluster.")
    args = parser.parse_args()

    make_plot()

    print("Done")