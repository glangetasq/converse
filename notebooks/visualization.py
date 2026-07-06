"""Plot helpers for the RAG A/B notebook, over the dataframes `load_run` returns.

Views, Nord-themed:
- `dumbbell(df_a, df_b)` — two pointwise runs, one dot per arm on a shared 1-5 axis.
- `pairwise_bars(df)` — one pairwise run, stacked win/tie/loss share per metric.
- `pairwise_bars_by(df, metric, pivot)` — one metric, stacked win/tie/loss per pivot value.
- `length_delta_hists(df)` — histograms of the per-case chars/words delta (b − a).
- `agreement_bars(df_a, df_b, pairwise)` — per-metric agree / almost / hard split.
- `hist(series)` — a single themed histogram of any series.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

BLUE = "#5E81AC"  # arm B / "preferred" side
ORANGE = "#D08770"  # arm A
TIE = "#C0C8D6"
GRID = "#DDE1E9"
INK = "#2E3440"
MUTED = "#6A7488"
AGREE = "#6F9F5F"  # same verdict
ALMOST = "#C99A3B"  # tie vs a preference
HARD = "#C0505A"  # opposite winners

_META_POINTWISE = {
    "case_id",
    "arm_name",
    "repeat_index",
    "judge_name",
    "scorecard_version",
    "verdict",
    "rationale",
    "error",
    "run_id",
    "candidate_key",
    "chars",
    "words",
}
_META_PAIRWISE = {
    "case_id",
    "repeat_index",
    "arm_a",
    "arm_b",
    "judge_name",
    "scorecard_version",
    "winner",
    "rationale",
    "error",
    "run_id",
    "chars_a",
    "words_a",
    "chars_b",
    "words_b",
}


def _pretty(metric: str) -> str:
    return metric.replace("_", " ").capitalize()


def _pointwise_metrics(df: pd.DataFrame) -> list[str]:
    return [
        c
        for c in df.columns
        if c not in _META_POINTWISE and pd.api.types.is_numeric_dtype(df[c])
    ]


def _pairwise_metrics(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in _META_PAIRWISE]


def _style(ax: Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    for label in ax.get_yticklabels():
        label.set_color(INK)


def hist(
    series: pd.Series,
    *,
    bins: int | str = "auto",
    color: str = BLUE,
    median: bool = True,
    ax: Axes | None = None,
    title: str | None = None,
    xlabel: str | None = None,
) -> Axes:
    """Themed histogram of a single series (NaNs dropped). A solid line marks the median
    unless `median=False`; `xlabel` defaults to the series name."""
    series = series.dropna()
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))
    ax.hist(series, bins=bins, color=color, zorder=2)
    if median and len(series):
        med = float(series.median())
        ax.axvline(med, color=INK, lw=1.4, zorder=3)
        ax.text(
            med,
            ax.get_ylim()[1] * 0.98,
            f" median {med:g}",
            ha="left",
            va="top",
            color=INK,
            fontsize=9,
        )
    ax.set_ylabel("count", color=MUTED, fontsize=10)
    label = (
        xlabel
        if xlabel is not None
        else (_pretty(str(series.name)) if series.name is not None else None)
    )
    if label:
        ax.set_xlabel(label, color=MUTED, fontsize=10)
    ax.grid(axis="y", color=GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=INK, fontsize=13, loc="center", pad=12)
    _style(ax)
    return ax


def dumbbell(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    labels: tuple[str, str] = ("no_rag", "full_rag"),
    metrics: list[str] | None = None,
    sort: bool = True,
    ax: Axes | None = None,
    title: str | None = "Mean score by metric",
) -> Axes:
    """Dumbbell of per-metric mean scores for two pointwise runs (biggest lift on top).

    `df_a`/`df_b` are each one arm's pointwise dataframe, named by `labels`. A given
    `metrics` list fixes both the selection and the top-to-bottom order; otherwise rows
    are auto-sorted by lift.
    """
    provided = metrics is not None
    metrics = metrics or _pointwise_metrics(df_a)
    mean_a = df_a[metrics].mean()
    mean_b = df_b[metrics].mean()

    rows = [(m, float(mean_a[m]), float(mean_b[m])) for m in metrics]
    if sort and not provided:
        rows.sort(key=lambda r: r[2] - r[1], reverse=True)

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.2))

    for y, (metric, a, b) in enumerate(rows):
        ax.plot([a, b], [y, y], color=GRID, lw=2, zorder=1)
        delta = round(b - a, 1) or 0.0  # collapse -0.0
        ax.annotate(
            f"{'+' if delta >= 0 else ''}{delta:.1f}",
            (max(a, b) + 0.08, y),
            va="center",
            fontsize=9,
            color=INK if delta >= 0 else MUTED,
        )
    ax.scatter(
        [r[1] for r in rows],
        range(len(rows)),
        color=ORANGE,
        s=70,
        zorder=3,
        label=labels[0],
    )
    ax.scatter(
        [r[2] for r in rows],
        range(len(rows)),
        color=BLUE,
        s=70,
        zorder=3,
        label=labels[1],
    )

    ax.set_yticks(range(len(rows)), [_pretty(r[0]) for r in rows])
    ax.set_xlim(1, 5.4)
    ax.set_xticks(range(1, 6))
    ax.set_xlabel("mean score (1-5)", color=MUTED, fontsize=10)
    ax.invert_yaxis()
    ax.grid(axis="x", color=GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncols=2,
        frameon=False,
        fontsize=10,
    )
    if title:
        ax.set_title(title, color=INK, fontsize=13, loc="center", pad=12)
    _style(ax)
    return ax


def _stack_row(ax: Axes, y: float, loss: float, tie: float, win: float) -> None:
    ax.barh(y, loss, left=0, color=ORANGE, height=0.62, zorder=2)
    ax.barh(y, tie, left=loss, color=TIE, height=0.62, zorder=2)
    ax.barh(y, win, left=loss + tie, color=BLUE, height=0.62, zorder=2)
    ax.text(
        0.01, y, f"{loss * 100:.0f}%", ha="left", va="center", fontsize=9, color=INK
    )
    ax.text(
        1.015,
        y,
        f"{win * 100:.0f}%",
        ha="left",
        va="center",
        fontsize=9,
        color=INK,
        clip_on=False,
    )


def pairwise_bars(
    df: pd.DataFrame,
    *,
    labels: tuple[str, str] = ("no_rag", "full_rag"),
    metrics: list[str] | None = None,
    sort: bool = True,
    ax: Axes | None = None,
    title: str | None = "Pairwise preference",
) -> Axes:
    """Stacked win/tie/loss bars (0-100%) from one pairwise run.

    Each row is `labels[0] | tie | labels[1]` left-to-right (arm_a on the left, arm_b on
    the right); the two preference shares are labelled at the ends, tie is unlabelled. A
    `metrics` list fixes the selection and top-to-bottom order. An "Overall winner" row
    (from the `winner` column) is pinned to the bottom.
    """
    provided = metrics is not None
    metrics = metrics or _pairwise_metrics(df)
    neg_token, pos_token = "a", "b"  # arm_a left, arm_b right

    rows = []
    for m in metrics:
        counts = df[m].value_counts()
        total = int(counts.reindex(["a", "b", "tie"]).fillna(0).sum())
        if total == 0:
            continue
        win = int(counts.get(pos_token, 0)) / total
        loss = int(counts.get(neg_token, 0)) / total
        tie = int(counts.get("tie", 0)) / total
        rows.append((m, win, tie, loss))
    if sort and not provided:
        rows.sort(
            key=lambda r: r[1], reverse=True
        )  # largest win first (top after invert)

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.2))

    for y, (metric, win, tie, loss) in enumerate(rows):
        _stack_row(ax, y, loss, tie, win)

    overall = None
    if "winner" in df.columns:
        wc = df["winner"].value_counts()
        wtot = int(wc.reindex(["a", "b", "tie"]).fillna(0).sum())
        if wtot:
            overall = (
                wc.get(neg_token, 0) / wtot,
                wc.get("tie", 0) / wtot,
                wc.get(pos_token, 0) / wtot,
            )
    overall_y = len(rows) + 0.4
    if overall:
        _stack_row(ax, overall_y, *overall)
        ax.axhline(len(rows) - 0.3, color=GRID, lw=1)

    ticks = list(range(len(rows))) + ([overall_y] if overall else [])
    ylabels = [_pretty(r[0]) for r in rows] + (["Overall winner"] if overall else [])
    ax.set_yticks(ticks, ylabels)
    ax.invert_yaxis()
    if overall:
        ax.get_yticklabels()[-1].set_fontweight("bold")
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_xlabel("share of comparisons", color=MUTED, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)
    handles = [
        Patch(color=ORANGE, label=f"{labels[0]} preferred"),
        Patch(color=TIE, label="tie"),
        Patch(color=BLUE, label=f"{labels[1]} preferred"),
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncols=3,
        frameon=False,
        fontsize=9,
    )
    if title:
        ax.set_title(title, color=INK, fontsize=13, loc="center", pad=12)
    _style(ax)
    return ax


def _looks_continuous(s: pd.Series) -> bool:
    """A pivot is continuous if it's a float axis or a high-cardinality integer; bool,
    category, and string are always categorical."""
    if pd.api.types.is_bool_dtype(s) or isinstance(s.dtype, pd.CategoricalDtype):
        return False
    if not pd.api.types.is_numeric_dtype(s):
        return False
    n = s.nunique(dropna=True)
    return n > 12 if pd.api.types.is_float_dtype(s) else n > 20


def _group_order(s: pd.Series) -> list:
    """Natural row order: category order if categorical (e.g. pd.cut intervals), else sorted."""
    if isinstance(s.dtype, pd.CategoricalDtype):
        present = set(s.dropna().unique())
        return [c for c in s.cat.categories if c in present]
    return sorted(s.dropna().unique())


def pairwise_bars_by(
    df: pd.DataFrame,
    metric: str,
    pivot: pd.Series,
    *,
    labels: tuple[str, str] = ("no_rag", "full_rag"),
    order: list | None = None,
    ax: Axes | None = None,
    title: str | None = None,
) -> Axes:
    """Stacked win/tie/loss bars for a single pairwise `metric`, one row per `pivot` value.

    `pivot` is aligned to `df` by index and must be categorical — string, bool, or
    low-cardinality integer are fine; a continuous (float / high-cardinality) pivot
    raises, so bin it first (pd.cut / pd.qcut). Rows follow `order` if given, else the
    pivot's natural (category / sorted) order. Each bar is `labels[0] | tie | labels[1]`;
    win/loss shares are labelled at the ends and the group size shown as `n=` in the tick.
    """
    if metric not in df.columns:
        raise KeyError(f"{metric!r} is not a column of the pairwise frame")
    groups = pivot.reindex(df.index)
    if _looks_continuous(groups):
        raise ValueError(
            f"pivot {groups.name!r} looks continuous ({groups.nunique()} distinct values) — "
            "pass a categorical / binary / integer pivot, e.g. pd.cut(pivot, bins=...)."
        )

    rows = []
    for g in order or _group_order(groups):
        counts = df.loc[groups == g, metric].value_counts()
        total = int(counts.reindex(["a", "b", "tie"]).fillna(0).sum())
        if total == 0:
            continue
        win = int(counts.get("b", 0)) / total
        loss = int(counts.get("a", 0)) / total
        tie = int(counts.get("tie", 0)) / total
        rows.append((g, win, tie, loss, total))

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.2))

    for y, (_, win, tie, loss, _n) in enumerate(rows):
        _stack_row(ax, y, loss, tie, win)

    pivot_name = groups.name or "group"
    ax.set_yticks(range(len(rows)), [f"{g}  (n={n})" for g, *_, n in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_ylabel(_pretty(str(pivot_name)), color=MUTED, fontsize=10)
    ax.set_xlabel("share of comparisons", color=MUTED, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)
    handles = [
        Patch(color=ORANGE, label=f"{labels[0]} preferred"),
        Patch(color=TIE, label="tie"),
        Patch(color=BLUE, label=f"{labels[1]} preferred"),
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncols=3,
        frameon=False,
        fontsize=9,
    )
    ax.set_title(
        title or f"{_pretty(metric)} by {_pretty(str(pivot_name))}",
        color=INK,
        fontsize=13,
        loc="center",
        pad=12,
    )
    _style(ax)
    return ax


def _delta_arrows(ax: Axes, labels: tuple[str, str]) -> None:
    """`labels[0] longer` ← | → `labels[1] longer`, below the x-axis (delta = b - a)."""
    for x_head, x_tail, x_text, color, text in [
        (0.02, 0.40, 0.21, ORANGE, f"{labels[0]} longer"),
        (0.98, 0.60, 0.79, BLUE, f"{labels[1]} longer"),
    ]:
        ax.annotate(
            "",
            xy=(x_head, -0.20),
            xytext=(x_tail, -0.20),
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "->", "color": color, "lw": 1.6},
        )
        ax.text(
            x_text,
            -0.27,
            text,
            transform=ax.transAxes,
            ha="center",
            va="top",
            color=color,
            fontsize=9,
        )


def length_delta_hists(
    df: pd.DataFrame,
    *,
    labels: tuple[str, str] = ("no_rag", "full_rag"),
    bins: int | str = "auto",
    axes: list[Axes] | None = None,
    title: str | None = None,
) -> list[Axes]:
    """Side-by-side histograms of `chars_delta` and `words_delta` (b − a) for a pairwise
    run. A dashed line marks zero (equal length), a solid line the mean; direction arrows
    under each axis read `labels[0] longer` (left) vs `labels[1] longer` (right). `title`
    defaults to naming the two arms from `labels`."""
    title = (
        title
        if title is not None
        else f"Length delta ({labels[1]} − {labels[0]}) per case"
    )
    missing = {"chars_a", "chars_b", "words_a", "words_b"} - set(df.columns)
    if missing:
        raise KeyError(
            f"need per-side length columns (pairwise load_run); missing {sorted(missing)}"
        )
    panels = [("chars", "Δ characters"), ("words", "Δ words")]

    if axes is None:
        _, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes = list(axes)

    for ax, (key, panel_title) in zip(axes, panels):
        a, b = df[f"{key}_a"], df[f"{key}_b"]
        delta = (b - a).dropna()
        counts, edges, patches = ax.hist(delta, bins=bins, zorder=2)
        for patch in patches:
            patch.set_color(
                BLUE if patch.get_x() + patch.get_width() / 2 >= 0 else ORANGE
            )
        ax.axvline(0, color=MUTED, lw=1, ls="--", alpha=0.8, zorder=1)
        mean = float(delta.mean())
        ax.axvline(mean, color=INK, lw=1.4, zorder=3)
        ax.text(
            mean,
            ax.get_ylim()[1] * 0.98,
            f" mean {mean:+.0f}",
            ha="left",
            va="top",
            color=INK,
            fontsize=9,
        )
        for i, (name, series, color) in enumerate(
            [(labels[0], a, ORANGE), (labels[1], b, BLUE)]
        ):
            ax.text(
                0.98,
                0.98 - i * 0.08,
                f"median {name}: {series.median():.0f}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                color=color,
                fontsize=9,
            )
        ax.set_title(panel_title, color=INK, fontsize=12, loc="center", pad=10)
        ax.set_ylabel("cases", color=MUTED, fontsize=10)
        ax.grid(axis="y", color=GRID, lw=1, alpha=0.6)
        ax.set_axisbelow(True)
        _style(ax)
        _delta_arrows(ax, labels)

    if title:
        axes[0].figure.suptitle(title, color=INK, fontsize=13, y=1.02)
    return axes


def _majority_token(s: pd.Series) -> str | None:
    counts = s.value_counts()
    if counts.empty:
        return None
    top = counts.index[counts == counts.max()]
    return top[0] if len(top) == 1 else "tie"  # a split vote reads as a tie


def _pointwise_verdicts(
    df_a: pd.DataFrame, df_b: pd.DataFrame, metrics: list[str], tau: float
) -> pd.DataFrame:
    delta = (
        df_b.groupby("case_id")[metrics]
        .mean()
        .subtract(df_a.groupby("case_id")[metrics].mean())
    )
    return delta.map(
        lambda d: (
            None
            if pd.isna(d)
            else "full" if d >= tau else "none" if d <= -tau else "tie"
        )
    )


def _pairwise_verdicts(pairwise: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    token = {"a": "none", "b": "full", "tie": "tie"}
    grouped = pairwise.groupby("case_id")[metrics].agg(_majority_token)
    return grouped.map(lambda t: token.get(t))


def _agreement(p: str, q: str) -> str:
    if p == q:
        return "agree"
    if p == "tie" or q == "tie":
        return "almost"
    return "hard"


def agreement_bars(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    pairwise: pd.DataFrame,
    *,
    tie_threshold: float = 0.5,
    labels: tuple[str, str] = ("no_rag", "full_rag"),
    metrics: list[str] | None = None,
    sort: bool = True,
    ax: Axes | None = None,
    title: str | None = "Pointwise vs pairwise agreement",
) -> Axes:
    """Per-metric 3-way agreement between the two pointwise runs and the pairwise run.

    Per case, the pointwise verdict is `sign(mean_b - mean_a)` with a `tie_threshold`
    dead-zone, the pairwise verdict is the majority `a/b/tie`. Each case is then:
    agree (same verdict), almost (tie vs a preference), or hard (opposite preferences).
    `df_a`/`df_b` must align with the pairwise `arm_a`/`arm_b` order. A `metrics` list
    fixes the selection and order. Bars are %; the segment labels are case counts.
    `labels` is accepted for parity with the other plots (this view is arm-agnostic).
    """
    provided = metrics is not None
    metrics = metrics or [
        m for m in _pointwise_metrics(df_a) if m in set(_pairwise_metrics(pairwise))
    ]
    pv = _pointwise_verdicts(df_a, df_b, metrics, tie_threshold)
    qv = _pairwise_verdicts(pairwise, metrics)

    rows = []
    for m in metrics:
        p, q = pv[m].dropna(), qv[m].dropna()
        cats = [_agreement(p[c], q[c]) for c in p.index.intersection(q.index)]
        if not cats:
            continue
        rows.append(
            (
                m,
                cats.count("agree"),
                cats.count("almost"),
                cats.count("hard"),
                len(cats),
            )
        )
    if sort and not provided:
        rows.sort(
            key=lambda r: r[1] / r[4], reverse=True
        )  # best agree share first (top after invert)

    if ax is None:
        _, ax = plt.subplots(figsize=(8.4, 0.5 * len(rows) + 1.3))

    for y, (m, agree, almost, hard, n) in enumerate(rows):
        segments = [
            (agree, AGREE, "white"),
            (almost, ALMOST, INK),
            (hard, HARD, "white"),
        ]
        left = 0.0
        for count, color, text_color in segments:
            width = count / n
            if width <= 0:
                left += width
                continue
            ax.barh(y, width, left=left, color=color, height=0.62, zorder=2)
            ax.text(
                left + width / 2,
                y,
                str(count),
                ha="center",
                va="center",
                fontsize=9,
                color=text_color,
                fontweight="bold",
            )
            left += width
        ax.text(
            1.015,
            y,
            f"n={n}",
            ha="left",
            va="center",
            fontsize=8.5,
            color=MUTED,
            clip_on=False,
        )

    ax.set_yticks(range(len(rows)), [_pretty(r[0]) for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_xlabel("share of cases", color=MUTED, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)
    handles = [
        Patch(color=AGREE, label="agree (same verdict)"),
        Patch(color=ALMOST, label="almost (tie vs preference)"),
        Patch(color=HARD, label="hard (opposite preferences)"),
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncols=3,
        frameon=False,
        fontsize=9,
    )
    if title:
        ax.set_title(title, color=INK, fontsize=13, loc="center", pad=12)
    _style(ax)
    return ax
