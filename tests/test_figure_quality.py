"""Enforce the scientific-figure contract.

Every closure and closed-48 panel must be **square** and carry explicit x and y
axis labels. These tests build the figures in memory and inspect the Matplotlib
objects, then verify that the saved PNGs are square in pixels.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from protacxtend.validation import closure_figures as cf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLOSED48 = ROOT / "benchmark_results" / "closed48" / "closed48_locked"


# ── helpers ─────────────────────────────────────────────────────────────

def _data_axes(fig):
    """Return axes that are not colourbars."""
    return [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]


def _assert_labelled_and_square(fig, *, min_axes: int = 1):
    axes = _data_axes(fig)
    assert len(axes) >= min_axes, f"expected >= {min_axes} panels, found {len(axes)}"
    for ax in axes:
        assert ax.get_xlabel().strip(), "panel is missing an x-axis label"
        assert ax.get_ylabel().strip(), "panel is missing a y-axis label"
        assert ax.get_box_aspect() == pytest.approx(1.0), "panel box aspect is not square"
    plt.close(fig)


def _load_closed48_script():
    spec = importlib.util.spec_from_file_location(
        "plot_closed_48", ROOT / "scripts" / "plot_closed_48.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _closed48_predictions():
    if not (CLOSED48 / "predictions.jsonl").exists():
        pytest.skip("closed48 run not present")
    return _load_closed48_script().load(CLOSED48)


# ── closure figures ─────────────────────────────────────────────────────

def test_closure_status_figure_is_labelled_and_square():
    _assert_labelled_and_square(cf.build_closure_status_figure())


def test_closure_denominator_figure_is_labelled_and_square():
    _assert_labelled_and_square(cf.build_closure_denominator_figure())


def test_closed48_outcomes_figure_is_labelled_and_square():
    _assert_labelled_and_square(cf.build_closed48_outcomes_figure())


def test_execution_funnel_figure_is_labelled_and_square():
    _assert_labelled_and_square(cf.build_execution_funnel_figure())


def test_baseline_capability_figure_is_labelled_and_square():
    _assert_labelled_and_square(cf.build_baseline_capability_figure())


def test_closure_overview_has_four_square_panels():
    _assert_labelled_and_square(cf.build_closure_overview_figure(), min_axes=4)


def test_saved_closure_png_is_square(tmp_path):
    fig = cf.build_closure_status_figure()
    out = tmp_path / "square.png"
    cf.save_square(fig, out)
    with Image.open(out) as image:
        assert image.size[0] == image.size[1], image.size


# ── closed-48 figures ───────────────────────────────────────────────────

def test_closed48_figures_are_labelled_and_square(tmp_path):
    module = _load_closed48_script()
    preds = _closed48_predictions()
    out = tmp_path / "closed48_figure_quality"
    out.mkdir(parents=True, exist_ok=True)
    captions: list[str] = []

    # Capture the figure before the builder closes it, so labels can be checked.
    captured: list = []

    def capture(fig, path, *, size_in=6.5, dpi=300):
        captured.append(fig)
        fig.set_size_inches(size_in, size_in)
        fig.savefig(path, dpi=dpi)

    module.save_square = capture
    builders = [
        module.fig_outcomes_by_arm,
        module.fig_outcomes_by_capability,
        module.fig_runtime,
        module.fig_failure_taxonomy,
    ]
    for builder in builders:
        builder(preds, out, captions)
        fig = captured[-1]
        _assert_labelled_and_square(fig)
        name = captions[-1].splitlines()[0].replace("## ", "")
        with Image.open(out / name) as image:
            assert image.size[0] == image.size[1], f"{name} is not square: {image.size}"


def test_existing_closure_pngs_are_square():
    figures = ROOT / "benchmark_results" / "figures"
    pngs = sorted(figures.glob("*.png"))
    if not pngs:
        pytest.skip("closure figures not generated")
    for path in pngs:
        with Image.open(path) as image:
            assert image.size[0] == image.size[1], f"{path.name} is not square: {image.size}"


def test_existing_closed48_pngs_are_square():
    pngs = sorted((CLOSED48 / "figures").glob("*.png"))
    if not pngs:
        pytest.skip("closed48 figures not generated")
    for path in pngs:
        with Image.open(path) as image:
            assert image.size[0] == image.size[1], f"{path.name} is not square: {image.size}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
