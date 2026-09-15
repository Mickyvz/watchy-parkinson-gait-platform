import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import pearsonr

# Data
subjects = ['01', '01', '01', '02', '02', '02']
real_steps = [17, 17, 16, 16, 17, 17]
estimated_steps = [16, 16, 14, 12, 22, 18]

# Calculate correlation
correlation, p_value = pearsonr(real_steps, estimated_steps)

# Create figure
plt.figure(figsize=(10, 8))

# Scatter plot
plt.scatter(real_steps, estimated_steps, s=150, alpha=0.6, color='#2E86AB', edgecolors='black', linewidth=1.5)

# Add regression line
min_val = min(min(real_steps), min(estimated_steps)) - 1
max_val = max(max(real_steps), max(estimated_steps)) + 1
z = np.polyfit(real_steps, estimated_steps, 1)
p = np.poly1d(z)
x_line = np.linspace(min_val, max_val, 100)
plt.plot(x_line, p(x_line), 'g-', linewidth=2, label=f'Linear Fit (R={correlation:.3f})', alpha=0.7)

# Labels for each point
for i, subj in enumerate(subjects):
    plt.annotate(f'S{subj}-T{i+1}', (real_steps[i], estimated_steps[i]), 
                 xytext=(5, 5), textcoords='offset points', fontsize=9, alpha=0.7)

# Customize plot
plt.xlabel('Real Steps', fontsize=13, fontweight='bold')
plt.ylabel('Estimated Steps by Watchy', fontsize=13, fontweight='bold')
plt.title('Validation: Real Steps vs Estimated Steps by Watchy', fontsize=14, fontweight='bold', pad=20)
plt.legend(fontsize=11, loc='upper left')
plt.grid(True, alpha=0.3, linestyle='--')

# Add correlation text box
textstr = f'Pearson r = {correlation:.3f}\np-value = {p_value:.4f}'
props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
plt.text(0.95, 0.05, textstr, transform=plt.gca().transAxes, fontsize=11,
         verticalalignment='bottom', horizontalalignment='right', bbox=props)

plt.tight_layout()

# Save the figure
plt.savefig('steps_validation.png', dpi=300, bbox_inches='tight')
print("Validation graph saved as 'steps_validation.png'")
print(f"Pearson correlation: {correlation:.3f}")
print(f"P-value: {p_value:.4f}")
plt.close()