"""Publication figures.

All figures share one palette and one style so the manuscript and the web
dashboard read as a single piece of work. Figures are written at 300 dpi to
``analysis/figures/`` and copied by the build into ``manuscript/figures/`` and
``docs/figures/`` -- the copy is done by the pipeline rather than by hand, so a
figure in the manuscript is always the figure the current code produced.
"""

from __future__ import annotations

import logging

import matplotlib
matplotlib.use("Agg")  # no display available in CI

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .harmonise import ELEMENT_SYMBOLS

logger = logging.getLogger(__name__)

# Palette shared with docs/css/style.css.
NAVY = "#2F5985"
BLUE = "#3B6EA5"
TEAL = "#3FB6A8"
MINT = "#54C9BA"
GOLD = "#D4AF37"
CORAL = "#E07A5F"
SLATE = "#64748B"
INK = "#1E293B"

CROP_COLOURS = {"lettuce": BLUE, "tokyo_bekana": TEAL}
CROP_LABELS = {"lettuce": "Lettuce (OSD-745)", "tokyo_bekana": "Tokyo Bekana (OSD-655)"}
CONDITION_COLOURS = {"Flight": CORAL, "Ground": SLATE}

DPI = 300


def apply_style() -> None:
    """Set the shared matplotlib style."""
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.edgecolor": "#CBD5E1",
        "axes.labelcolor": INK,
        "axes.grid": True,
        "grid.color": "#E2E8F0",
        "grid.linewidth": 0.6,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.frameon": False,
    })


def symbol(element: str) -> str:
    return ELEMENT_SYMBOLS.get(element, element)


def fig_fold_change_comparison(comparison: pd.DataFrame, path):
    """Raw concentration vs CLR fold changes, per crop -- the central figure.

    Shows which apparent flight effects survive correction for dry-matter
    dilution. Elements are ordered by their raw concentration fold change so the
    collapse of the divalent cations after correction is visible at a glance.
    """
    apply_style()
    crops = sorted(comparison["group"].unique())
    fig, axes = plt.subplots(1, len(crops), figsize=(11, 4.6), sharex=True)
    if len(crops) == 1:
        axes = [axes]

    for ax, crop in zip(axes, crops):
        sub = comparison[comparison["group"] == crop].copy()
        sub = sub.sort_values("fold_change_conc")
        y = np.arange(len(sub))

        ax.axvline(1.0, color="#94A3B8", lw=1.2, ls="--", zorder=1)
        ax.scatter(sub["fold_change_conc"], y + 0.16, s=54, color=CORAL,
                   label="Raw concentration", zorder=3, edgecolor="white", linewidth=0.6)
        ax.scatter(sub["fold_change_clr"], y - 0.16, s=54, color=NAVY,
                   label="CLR (dilution-corrected)", zorder=3,
                   edgecolor="white", linewidth=0.6)

        for i, row in enumerate(sub.itertuples()):
            ax.plot([row.fold_change_conc, row.fold_change_clr], [i + 0.16, i - 0.16],
                    color="#CBD5E1", lw=1.0, zorder=2)
            # Significance markers are offset to the right of the point in data
            # coordinates rather than stacked above/below it: at this figure size
            # a vertical offset puts the asterisk inside the marker, where the
            # two series' stars overlap and become unreadable.
            if row.significant_fdr05_conc:
                ax.annotate("*", (row.fold_change_conc, i + 0.16),
                            textcoords="offset points", xytext=(8, -3),
                            color=CORAL, fontsize=13, fontweight="bold", zorder=4)
            if row.significant_fdr05_clr:
                ax.annotate("*", (row.fold_change_clr, i - 0.16),
                            textcoords="offset points", xytext=(8, -3),
                            color=NAVY, fontsize=13, fontweight="bold", zorder=4)

        ax.set_yticks(y)
        ax.set_yticklabels([symbol(e) for e in sub["element"]])
        ax.set_xlabel("Flight / Ground fold change")
        ax.set_title(CROP_LABELS.get(crop, crop), color=CROP_COLOURS.get(crop, INK))
        ax.set_xlim(0.3, 2.4)

    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle(
        "Apparent flight effects before and after correcting for dry-matter dilution",
        fontsize=11, fontweight="bold", y=1.02,
    )
    fig.text(0.5, -0.05, "* = FDR q < 0.05 within crop", ha="center",
             fontsize=8, color=SLATE)
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_crop_divergence(comparison: pd.DataFrame, path):
    """Lettuce vs Tokyo Bekana fold change per element, on both scales."""
    apply_style()
    wide = comparison.pivot(index="element", columns="group",
                            values=["fold_change_conc", "fold_change_clr"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))

    for ax, kind, title in zip(
        axes, ("conc", "clr"),
        ("Raw concentration", "CLR (dilution-corrected)"),
    ):
        x = pd.to_numeric(wide[(f"fold_change_{kind}", "lettuce")], errors="coerce")
        y = pd.to_numeric(wide[(f"fold_change_{kind}", "tokyo_bekana")], errors="coerce")
        keep = x.notna() & y.notna()

        ax.axhline(1.0, color="#94A3B8", lw=1.0, ls="--")
        ax.axvline(1.0, color="#94A3B8", lw=1.0, ls="--")
        lim = (0.4, 2.4)
        ax.plot(lim, lim, color="#E2E8F0", lw=1.0, zorder=1)

        ax.scatter(x[keep], y[keep], s=90, color=GOLD, edgecolor=NAVY,
                   linewidth=1.0, zorder=3)
        for element in wide.index[keep]:
            ax.annotate(symbol(element), (x[element], y[element]),
                        textcoords="offset points", xytext=(7, 4), fontsize=9,
                        fontweight="bold", color=INK)

        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel("Lettuce  F/G fold change")
        ax.set_ylabel("Tokyo Bekana  F/G fold change")
        ax.set_title(title)

    fig.suptitle("The two Veggie crops do not share a flight ionome response",
                 fontsize=11, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_element_profiles(elemental: pd.DataFrame, path):
    """Per-element concentration by crop and condition."""
    apply_style()
    elements = [e for e in sorted(ELEMENT_SYMBOLS) if e in elemental.columns]
    elements = [e for e in elements
                if pd.to_numeric(elemental[e], errors="coerce").notna().sum() > 10]

    ncols = 4
    nrows = int(np.ceil(len(elements) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 2.5 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, element in zip(axes, elements):
        data, labels, colours = [], [], []
        for crop in sorted(elemental["crop"].unique()):
            for condition in ("Ground", "Flight"):
                values = pd.to_numeric(
                    elemental[(elemental["crop"] == crop)
                              & (elemental["condition"] == condition)][element],
                    errors="coerce",
                ).dropna()
                if values.empty:
                    continue
                data.append(values)
                labels.append(f"{'Let' if crop == 'lettuce' else 'TB'}\n{condition[:3]}")
                colours.append(CONDITION_COLOURS[condition])

        box = ax.boxplot(data, patch_artist=True, widths=0.6,
                         medianprops={"color": INK, "linewidth": 1.4},
                         flierprops={"marker": "o", "markersize": 3,
                                     "markerfacecolor": SLATE, "alpha": 0.6})
        for patch, colour in zip(box["boxes"], colours):
            patch.set_facecolor(colour); patch.set_alpha(0.65)
            patch.set_edgecolor(INK); patch.set_linewidth(0.7)

        ax.set_xticklabels(labels, fontsize=7)
        ax.set_title(f"{symbol(element)}  ({element})", fontsize=9)
        ax.set_ylabel("µg/g DW", fontsize=8)

    for ax in axes[len(elements):]:
        ax.axis("off")

    fig.suptitle("Elemental concentrations by crop and flight condition",
                 fontsize=11, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_astronaut_trajectories(serum: pd.DataFrame, path):
    """Per-subject serum mineral trajectories with clinical reference bands."""
    apply_style()
    minerals = ["calcium", "potassium", "sodium", "chloride"]
    minerals = [m for m in minerals if m in serum.columns]

    fig, axes = plt.subplots(1, len(minerals), figsize=(3.0 * len(minerals), 3.6))
    axes = np.atleast_1d(axes)
    subject_colours = dict(zip(sorted(serum["subject"].unique()),
                               [NAVY, TEAL, GOLD, CORAL]))

    for ax, mineral in zip(axes, minerals):
        low_col, high_col = f"{mineral}_range_min", f"{mineral}_range_max"
        if low_col in serum.columns and serum[low_col].notna().any():
            ax.axhspan(serum[low_col].dropna().iloc[0], serum[high_col].dropna().iloc[0],
                       color=MINT, alpha=0.16, zorder=0, label="Clinical range")

        for subject, group in serum.groupby("subject"):
            group = group.sort_values("day_relative")
            ax.plot(group["day_relative"], group[mineral], "-o", markersize=4,
                    lw=1.4, color=subject_colours[subject], label=subject, zorder=3)

        ax.axvline(0, color=INK, lw=1.0, ls="--", alpha=0.6)
        ax.set_title(f"Serum {mineral}")
        ax.set_xlabel("Days relative to return")
        unit_col = f"{mineral}_unit"
        unit = serum[unit_col].dropna().iloc[0] if unit_col in serum else ""
        ax.set_ylabel(unit.replace("_", " "), fontsize=7)

    axes[-1].legend(fontsize=7, loc="best")
    fig.suptitle(
        "Inspiration4 serum minerals (n = 4, 3-day mission, no in-flight sample)",
        fontsize=11, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_serving_contribution(contributions: pd.DataFrame, path):
    """Percentage of the NASA daily requirement supplied by a 100 g serving."""
    apply_style()
    ref = contributions[
        (contributions["serving_fresh_g"] == 100.0)
        & (contributions["dry_matter_assumption"] == "high")
        & (contributions["condition"] == "Flight")
        & contributions["percent_of_requirement"].notna()
    ]
    pivot = ref.pivot(index="element", columns="crop",
                      values="percent_of_requirement").sort_values(
        "lettuce", ascending=True)

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    y = np.arange(len(pivot))
    height = 0.38
    for offset, crop in ((+height / 2, "lettuce"), (-height / 2, "tokyo_bekana")):
        if crop in pivot.columns:
            ax.barh(y + offset, pivot[crop], height=height,
                    color=CROP_COLOURS[crop], label=CROP_LABELS[crop],
                    edgecolor="white", linewidth=0.6)

    ax.axvline(100, color=CORAL, lw=1.4, ls="--", label="100% of daily requirement")
    ax.set_yticks(y)
    ax.set_yticklabels([symbol(e) for e in pivot.index])
    ax.set_xlabel("% of NASA daily requirement (JSC-67378 Rev 1)")
    ax.set_title("A 100 g fresh serving of spaceflight-grown produce\n"
                 "against crew mineral requirements", fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_ml_performance(ml_results: dict, path):
    """Model balanced accuracy against baselines, per CV scheme."""
    apply_style()
    schemes = list(ml_results["schemes"])
    fig, axes = plt.subplots(1, len(schemes), figsize=(5.2 * len(schemes), 4.0),
                             sharey=True)
    axes = np.atleast_1d(axes)

    for ax, scheme_name in zip(axes, schemes):
        scheme = ml_results["schemes"][scheme_name]
        names = list(scheme["models"])
        values = [scheme["models"][n]["balanced_accuracy"] for n in names]
        colours = [SLATE if scheme["models"][n]["is_baseline"] else NAVY for n in names]

        bars = ax.bar(range(len(names)), values, color=colours,
                      edgecolor="white", linewidth=0.8)
        ax.axhline(0.5, color=CORAL, lw=1.3, ls="--", label="Chance (0.5)")
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012,
                    f"{value:.3f}", ha="center", fontsize=8)

        ax.set_xticks(range(len(names)))
        ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=7.5)
        ax.set_ylim(0, 0.85)
        ax.set_title(f"{scheme_name}\n({scheme['n_folds']} folds)", fontsize=9.5)

    axes[0].set_ylabel("Balanced accuracy")
    axes[0].legend(fontsize=8)
    fig.suptitle("Flight vs ground classification does not beat chance",
                 fontsize=11, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)


def fig_lsda_landscape(summary: dict, path):
    """The LSDA access landscape: what mineral data exists and can it be obtained."""
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    # Left: measured-mineral counts per element.
    measured = summary["by_mineral_measured"]
    items = sorted(
        ((k, v) for k, v in measured.items() if v > 0), key=lambda kv: kv[1]
    )
    axes[0].barh([symbol(k) for k, _ in items], [v for _, v in items],
                 color=NAVY, edgecolor="white", linewidth=0.6)
    axes[0].set_xlabel("LSDA experiments measuring this element")
    axes[0].set_title("Mineral coverage across the LSDA catalog", fontsize=10)
    for i, (_, value) in enumerate(items):
        axes[0].text(value + 2, i, str(value), va="center", fontsize=8)

    # Right: access categories.
    access = summary["measured_by_access_category"]
    labels = {
        "open": "Open", "request_required": "Request required",
        "not_submitted": "Never submitted", "held_elsewhere": "Held elsewhere",
        "other": "Other", "unknown": "Unknown",
    }
    colours = {
        "open": TEAL, "request_required": GOLD, "not_submitted": CORAL,
        "held_elsewhere": SLATE, "other": "#CBD5E1", "unknown": "#E2E8F0",
    }
    keys = sorted(access, key=lambda k: -access[k])
    wedges, _, autotexts = axes[1].pie(
        [access[k] for k in keys],
        labels=[labels.get(k, k) for k in keys],
        colors=[colours.get(k, SLATE) for k in keys],
        autopct=lambda p: f"{p:.0f}%", startangle=110,
        wedgeprops={"edgecolor": "white", "linewidth": 1.4},
        textprops={"fontsize": 8.5},
    )
    for text in autotexts:
        text.set_color("white"); text.set_fontweight("bold"); text.set_fontsize(8)
    axes[1].set_title(
        f"Accessibility of the {summary['n_measured_mineral_or_nutrition']} "
        f"experiments\nthat measured a mineral or nutritional variable", fontsize=10)

    fig.suptitle(
        f"NASA LSDA: {summary['n_experiments_total']} experiments surveyed",
        fontsize=11, fontweight="bold", y=1.0,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("wrote %s", path)
