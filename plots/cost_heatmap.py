import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Read the data from the provided CSV file
csv_path = 'plots/data/costs.csv'
data = pd.read_csv(csv_path, index_col=0)
data.columns = [name[:4] for name in data.columns]

# Plot the heatmap with adjustments
plt.figure(figsize=(5, 3))

# Create the heatmap
sns.heatmap(data, annot=True, fmt=".2f", cmap="coolwarm", cbar=True, linewidths=0.5, 
            cbar_kws={"shrink": 0.7})

# Move the x-axis to the top
plt.gca().xaxis.set_ticks_position('top')
plt.xticks(fontsize=10)
plt.yticks(rotation=0, fontsize=10)  # Keep hardware labels readable

# Set the labels for axes
plt.ylabel("AWS VM Type", fontsize=12)

plt.tight_layout()

# Save the plot
output_path = 'plots/output/cost_heatmap'
jpg_path = output_path + '.jpg'
pdf_path = output_path + '.pdf'
plt.savefig(jpg_path, dpi=300, bbox_inches='tight')
plt.savefig(pdf_path, bbox_inches='tight')
plt.show()

print("Done")