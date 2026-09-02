"""Guard: this project must never generate its own data.

The predecessor analysis of these same studies reported flight effects, model
accuracies and cross-species generalisation that were produced by a
numpy.random data generator and by hardcoded literals inside `except` blocks,
not by measurement. These tests make that class of failure impossible to
introduce here without the build going red.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Source files that participate in producing results. Tests are excluded (this
# file necessarily contains the forbidden patterns as string literals).
SOURCE_FILES = [
    *sorted((REPO / "src" / "spacemineralatlas").glob("*.py")),
    *sorted(REPO.glob("scripts_*.py")),
]

# Random-number generation used to fabricate measurements. `default_rng` is
# permitted only in ml.py, where it drives bootstrap resampling of real values.
FORBIDDEN_RANDOM = [
    r"np\.random\.normal",
    r"np\.random\.uniform",
    r"numpy\.random\.normal",
    r"numpy\.random\.uniform",
    r"random\.gauss",
    r"make_classification",
    r"make_regression",
]


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_synthetic_data_generation(path: Path) -> None:
    """No module may fabricate numeric observations."""
    text = path.read_text()
    for pattern in FORBIDDEN_RANDOM:
        assert not re.search(pattern, text), (
            f"{path.name} contains {pattern!r}. This project analyses measured "
            f"data only; synthetic generation is prohibited."
        )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_hardcoded_metrics_in_except_blocks(path: Path) -> None:
    """No `except` handler may substitute a plausible-looking result.

    Catches the specific pattern that produced a reported 89.6% accuracy in the
    predecessor project: a model fails, and the handler supplies a literal.
    """
    lines = path.read_text().splitlines()
    inside_except = False
    except_indent = 0

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())

        if stripped.startswith(("except ", "except:")):
            inside_except, except_indent = True, indent
            continue
        if inside_except and indent <= except_indent and not stripped.startswith("#"):
            inside_except = False

        if inside_except:
            # A float literal between 0 and 1 assigned inside an exception
            # handler is the signature of a fabricated metric.
            assert not re.search(r"=\s*0\.\d+", stripped), (
                f"{path.name}:{number} assigns a numeric literal inside an "
                f"except block: {stripped!r}. A failed computation must "
                f"propagate, not be replaced by a plausible number."
            )


def test_fetch_failure_is_fatal() -> None:
    """The HTTP layer must raise on exhausted retries, never return a default."""
    source = (REPO / "src" / "spacemineralatlas" / "http.py").read_text()
    assert "raise requests.HTTPError" in source, (
        "http.fetch must raise when it cannot retrieve a URL."
    )
    assert "return False" not in source, (
        "http.fetch must not signal failure by returning a value that a caller "
        "could interpret as 'use a fallback'."
    )
