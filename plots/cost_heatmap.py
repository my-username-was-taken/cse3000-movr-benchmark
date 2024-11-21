import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Read the data from the provided CSV file
csv_path = 'plots/data/costs.csv'  # Adjust the path if needed
data = pd.read_csv(csv_path, index_col=0)

# Plot the heatmap with adjustments
plt.figure(figsize=(5, 3))  # Adjusted to make the table about 67% shorter

# Create the heatmap
sns.heatmap(data, annot=True, fmt=".2f", cmap="coolwarm", cbar=True, linewidths=0.5, 
            cbar_kws={"shrink": 0.7})

# Move the x-axis to the top
plt.gca().xaxis.set_ticks_position('top')
plt.xticks(fontsize=10)
plt.yticks(rotation=0, fontsize=10)  # Keep hardware labels readable

# Set the labels for axes
#plt.xlabel("Databases", fontsize=12)
plt.ylabel("AWS Hardware", fontsize=12)

plt.tight_layout()

# Save the plot
output_path = 'plots/output/cost_heatmap'
jpg_path = output_path + '.jpg'
pdf_path = output_path + '.pdf'
plt.savefig(jpg_path, dpi=300, bbox_inches='tight')
plt.savefig(pdf_path, bbox_inches='tight')
plt.show()

print("Done")