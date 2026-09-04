#!/usr/bin/env python3
"""Generate publication plots of Inspiration4 crew vs NHANES population norms."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path

# Load comparison data
comparison_path = Path("data/processed/nhanes_astronaut_comparison.csv")
if not comparison_path.exists():
    raise FileNotFoundError(f"Run 'make fetch-nhanes' first to generate {comparison_path}")

df = pd.read_csv(comparison_path)

# Crew metadata for nicer labels
crew_info = {
    "C001": {"name": "Jared Isaacman", "age": 38, "sex": "M", "role": "Commander"},
    "C002": {"name": "Hayley Arceneaux", "age": 29, "sex": "F", "role": "Medical Officer"},
    "C003": {"name": "Chris Sembroski", "age": 41, "sex": "M", "role": "Specialist"},
    "C004": {"name": "Sian Proctor", "age": 51, "sex": "F", "role": "Pilot"},
}

# ============================================================================
# Figure 1: Grid of Pre/Post Percentiles by Crew and Analyte
# ============================================================================

fig, axes = plt.subplots(
    nrows=4, ncols=3, figsize=(14, 12),
    constrained_layout=True
)
fig.suptitle(
    "Inspiration4 Serum Mineral Levels vs NHANES Population Percentiles",
    fontsize=16, fontweight="bold", y=0.995
)

analytes = sorted(df["analyte"].unique())
subjects = ["C001", "C002", "C003", "C004"]

for row_idx, subject in enumerate(subjects):
    crew = crew_info[subject]
    subject_data = df[df["subject"] == subject]

    for col_idx, analyte in enumerate(analytes):
        ax = axes[row_idx, col_idx]
        analyte_data = subject_data[subject_data["analyte"] == analyte]

        if analyte_data.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            continue

        row = analyte_data.iloc[0]
        pre_pct = row["preflight_percentile"]
        post_pct = row["postflight_percentile"]

        # Draw population reference (0-100 percentile range)
        ax.barh([0.5], [100], height=0.15, color="#e0e0e0", edgecolor="gray", linewidth=0.5)

        # Draw reference range (5th to 95th percentile)
        ref_range = row["nhanes_range_5_95"].split("-")
        ref_min = float(ref_range[0])
        ref_max = float(ref_range[1])
        median = row["nhanes_median"]

        # Add population distribution annotation
        ax.axvline(median, color="red", linestyle="--", linewidth=1.5, alpha=0.7, label="Population median")

        # Pre-flight marker
        ax.scatter([pre_pct], [0.7], s=200, marker="o", color="steelblue",
                  edgecolor="navy", linewidth=2, zorder=5, label="Pre-flight")

        # Post-flight marker
        ax.scatter([post_pct], [0.3], s=200, marker="s", color="coral",
                  edgecolor="darkred", linewidth=2, zorder=5, label="Post-flight")

        # Arrow showing change
        if abs(post_pct - pre_pct) > 2:
            ax.annotate("", xy=(post_pct, 0.35), xytext=(pre_pct, 0.65),
                       arrowprops=dict(arrowstyle="->", color="gray", lw=1, alpha=0.5))

        # Formatting
        ax.set_xlim(-5, 105)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Percentile Rank" if row_idx == 3 else "", fontsize=10)
        ax.set_yticks([0.3, 0.7])
        ax.set_yticklabels(["Post", "Pre"], fontsize=9)
        ax.grid(axis="x", alpha=0.3, linestyle=":")

        # Title
        title = analyte.capitalize()
        if row_idx == 0:
            ax.set_title(title, fontsize=11, fontweight="bold")
        if col_idx == 0:
            ax.set_ylabel(f"{crew['name']}\n({crew['age']}{crew['sex']})",
                         fontsize=10, fontweight="bold")

        # Add percentile values as text
        ax.text(pre_pct, 0.75, f"{pre_pct:.0f}%", ha="center", fontsize=8, fontweight="bold")
        ax.text(post_pct, 0.25, f"{post_pct:.0f}%", ha="center", fontsize=8, fontweight="bold")

# Add single legend at bottom
handles = [
    plt.scatter([], [], s=200, marker="o", color="steelblue", edgecolor="navy", linewidth=2),
    plt.scatter([], [], s=200, marker="s", color="coral", edgecolor="darkred", linewidth=2),
    plt.Line2D([], [], color="red", linestyle="--", linewidth=1.5, label="Population median"),
]
fig.legend(handles, ["Pre-flight", "Post-flight", "Population median"],
          loc="lower center", ncol=3, fontsize=11, frameon=True, bbox_to_anchor=(0.5, -0.02))

plt.savefig("figures/nhanes_crew_comparison_grid.pdf", dpi=300, bbox_inches="tight")
plt.savefig("figures/nhanes_crew_comparison_grid.png", dpi=300, bbox_inches="tight")
print("✓ Saved: figures/nhanes_crew_comparison_grid.pdf")

# ============================================================================
# Figure 2: Percentile Change (Pre to Post) by Crew and Analyte
# ============================================================================

fig, ax = plt.subplots(figsize=(12, 6))

# Prepare data for grouped bar chart
x_pos = np.arange(len(subjects))
width = 0.25

for col_idx, analyte in enumerate(analytes):
    changes = []
    for subject in subjects:
        subject_data = df[(df["subject"] == subject) & (df["analyte"] == analyte)]
        if subject_data.empty:
            changes.append(0)
        else:
            changes.append(subject_data.iloc[0]["percentile_change"])

    ax.bar(x_pos + col_idx * width, changes, width, label=analyte.capitalize(), alpha=0.8)

ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
ax.set_xlabel("Crew Member", fontsize=12, fontweight="bold")
ax.set_ylabel("Percentile Rank Change (Post - Pre)", fontsize=12, fontweight="bold")
ax.set_title("Inspiration4 Post-Flight Mineral Changes vs NHANES Population",
            fontsize=14, fontweight="bold")
ax.set_xticks(x_pos + width)
ax.set_xticklabels([f"{crew_info[s]['name'].split()[0]}\n({crew_info[s]['age']}{crew_info[s]['sex']})"
                     for s in subjects], fontsize=10)
ax.legend(title="Analyte", fontsize=10, title_fontsize=11)
ax.grid(axis="y", alpha=0.3, linestyle=":")
ax.set_ylim(-50, 40)

plt.tight_layout()
plt.savefig("figures/nhanes_percentile_changes.pdf", dpi=300, bbox_inches="tight")
plt.savefig("figures/nhanes_percentile_changes.png", dpi=300, bbox_inches="tight")
print("✓ Saved: figures/nhanes_percentile_changes.pdf")

# ============================================================================
# Figure 3: Heatmap of Percentile Ranks
# ============================================================================

fig, (ax_pre, ax_post) = plt.subplots(1, 2, figsize=(10, 5))

# Pivot data for heatmap
pre_data = df.pivot_table(values="preflight_percentile", index="subject", columns="analyte")
post_data = df.pivot_table(values="postflight_percentile", index="subject", columns="analyte")

# Reorder for better display
pre_data = pre_data.reindex(["C001", "C002", "C003", "C004"])
post_data = post_data.reindex(["C001", "C002", "C003", "C004"])
pre_data = pre_data[[col for col in ["calcium", "potassium", "sodium"] if col in pre_data.columns]]
post_data = post_data[[col for col in ["calcium", "potassium", "sodium"] if col in post_data.columns]]

# Create heatmaps
im_pre = ax_pre.imshow(pre_data.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)
ax_pre.set_xticks(range(len(pre_data.columns)))
ax_pre.set_yticks(range(len(pre_data.index)))
ax_pre.set_xticklabels([c.capitalize() for c in pre_data.columns])
ax_pre.set_yticklabels([crew_info[s]["name"] for s in pre_data.index])
ax_pre.set_title("Pre-Flight Percentiles", fontsize=12, fontweight="bold")

for i, subject in enumerate(pre_data.index):
    for j, analyte in enumerate(pre_data.columns):
        text = ax_pre.text(j, i, f"{pre_data.iloc[i, j]:.0f}",
                          ha="center", va="center", color="black", fontsize=10, fontweight="bold")

im_post = ax_post.imshow(post_data.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)
ax_post.set_xticks(range(len(post_data.columns)))
ax_post.set_yticks(range(len(post_data.index)))
ax_post.set_xticklabels([c.capitalize() for c in post_data.columns])
ax_post.set_yticklabels([crew_info[s]["name"] for s in post_data.index])
ax_post.set_title("Post-Flight Percentiles", fontsize=12, fontweight="bold")

for i, subject in enumerate(post_data.index):
    for j, analyte in enumerate(post_data.columns):
        text = ax_post.text(j, i, f"{post_data.iloc[i, j]:.0f}",
                           ha="center", va="center", color="black", fontsize=10, fontweight="bold")

# Colorbar
cbar = fig.colorbar(im_post, ax=[ax_pre, ax_post], orientation="horizontal",
                   pad=0.1, label="Percentile Rank")

fig.suptitle("Inspiration4 Serum Mineral Levels: Population Percentile Ranks",
            fontsize=14, fontweight="bold", y=1.02)

plt.tight_layout()
plt.savefig("figures/nhanes_percentile_heatmap.pdf", dpi=300, bbox_inches="tight")
plt.savefig("figures/nhanes_percentile_heatmap.png", dpi=300, bbox_inches="tight")
print("✓ Saved: figures/nhanes_percentile_heatmap.pdf")

print("\n✅ All plots generated successfully!")
print("\nFiles created:")
print("  - figures/nhanes_crew_comparison_grid.pdf/png")
print("  - figures/nhanes_percentile_changes.pdf/png")
print("  - figures/nhanes_percentile_heatmap.pdf/png")
