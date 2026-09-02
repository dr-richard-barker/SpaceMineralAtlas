"""Verify that every generated-number macro used in the manuscript is defined.

LaTeX already fails on an undefined control sequence, but it fails one macro at a
time and buries the message in a thousand lines of font loading. This check
reports every mismatch at once, before the build, and is fast enough to run on
every commit.

It deliberately only considers macros that look like generated-number macros
(capitalised, alphabetic, not a known LaTeX or package command), so ordinary
LaTeX markup does not produce false positives.

Run:  python scripts_check_macros.py
Exit: 0 if every used macro is defined, 1 otherwise.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from spacemineralatlas.paths import MANUSCRIPT

# Commands provided by LaTeX itself or by the packages sma-style loads. A macro
# in this set is never reported as missing.
KNOWN_COMMANDS = {
    "LaTeX", "TeX", "Huge", "Large", "LARGE", "Big", "Bigg", "P", "S",
    "Roman", "Alph", "Alt", "AA", "Delta", "Omega", "Sigma", "Gamma", "Lambda",
    "Theta", "Phi", "Psi", "Xi", "Pi", "Upsilon",
}


def main() -> int:
    numbers_file = MANUSCRIPT / "generated_numbers.tex"
    if not numbers_file.exists():
        print("ERROR: generated_numbers.tex missing; run `make numbers` first")
        return 1

    defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", numbers_file.read_text()))

    sources = [MANUSCRIPT / "main.tex", *sorted((MANUSCRIPT / "chapters").glob("*.tex"))]
    used: dict[str, list[str]] = {}

    for source in sources:
        text = source.read_text()
        # Strip comments so a commented-out macro is not reported.
        text = re.sub(r"(?<!\\)%.*", "", text)
        for match in re.finditer(r"\\([A-Z][A-Za-z]*)\b", text):
            name = match.group(1)
            if name in KNOWN_COMMANDS:
                continue
            used.setdefault(name, []).append(source.name)

    missing = {n: sorted(set(f)) for n, f in used.items() if n not in defined}
    unused = sorted(defined - set(used))

    if missing:
        print(f"MISSING: {len(missing)} macro(s) used but not defined\n")
        for name, files in sorted(missing.items()):
            close = sorted(
                d for d in defined if d.lower() == name.lower()
            )
            hint = f"   -> did you mean \\{close[0]}?" if close else ""
            print(f"  \\{name:28s} used in {', '.join(files)}{hint}")
        print()

    print(f"defined: {len(defined)} | used: {len(used)} | "
          f"missing: {len(missing)} | defined-but-unused: {len(unused)}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
