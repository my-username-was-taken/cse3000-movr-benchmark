import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Read the data from the provided CSV file
csv_path = 'plots/data/rtt_matrix_regions.csv'
data = pd.read_csv(csv_path, index_col=0)

# Replace 'N/A' with np.nan for numeric calculations
data.replace('N/A', np.nan, inplace=True)

# Convert numeric columns to float
data = data.apply(pd.to_numeric, errors='coerce')
np_data = data.to_numpy()

# Round numeric values and replace NaN with placeholders for display
rounded_data = data.round().to_numpy()  # Convert to numpy for easier handling
annot = np.where(np.isnan(rounded_data), 'N/A', rounded_data.astype(int)).astype(str)  # Annotation matrix

# For equal source and destination, make an exception: The annotation will include 2 decimal places
for i in range(len(np_data)):
    annot[i,i] = str(np_data[i,i].round(2))

# Map long region names to abbreviations
short_region_map = {
    "ap-northeast-1": "apne1",
    "ap-northeast-2": "apne2",
    "eu-west-1": "euw1",
    "eu-west-2": "euw2",
    "us-east-1": "use1",
    "us-east-2": "use2",
    "us-west-1": "usw1",
    "us-west-2": "usw2"
}
data.columns = [short_region_map[name] for name in data.columns]
data.index = [short_region_map[name] for name in data.index]

# Plot the heatmap
plt.figure(figsize=(5, 3))
sns.heatmap(
    data=data,  # Plot the rounded numpy data
    annot=annot,        # Custom annotation matrix
    fmt='',             # Allow custom formatting
    cmap="coolwarm", 
    cbar=True, 
    linewidths=0.5,
    cbar_kws={"shrink": 0.7}, 
    mask=np.isnan(rounded_data),  # Mask NaN values
    vmin=0,
    vmax=250
)

# Move the x-axis to the top
plt.gca().xaxis.set_ticks_position('top')
plt.gca().set_xticklabels(data.columns, fontsize=9)
plt.gca().set_yticklabels(data.index, rotation=0, fontsize=9)  # Keep region labels readable

plt.tight_layout()

# Save the plot
output_path = 'plots/output/RTT_heatmap'
jpg_path = output_path + '.jpg'
pdf_path = output_path + '.pdf'
plt.savefig(jpg_path, dpi=300, bbox_inches='tight')
plt.savefig(pdf_path, bbox_inches='tight')
plt.show()

print("Done")
