#!/usr/bin/env python3
"""Build the released LaTeX manuscript without modifying scientific inputs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def main() -> None:
    candidates = [PAPER / "paper-agent-economics-aaai27.tex", PAPER / "paper.tex"]
    tex = next((path for path in candidates if path.is_file()), None)
    if tex is None:
        raise SystemExit("final paper source is not present in this checkout")
    if shutil.which("latexmk"):
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=PAPER, check=True)
    elif shutil.which("pdflatex"):
        for _ in range(2):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=PAPER, check=True)
    else:
        raise SystemExit("install latexmk or pdflatex to build the paper")
    print(PAPER / f"{tex.stem}.pdf")


if __name__ == "__main__":
    main()
