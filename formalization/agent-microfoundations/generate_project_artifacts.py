#!/usr/bin/env python3
"""Generate theorem audit and index directly from the Lean source tree."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
LEAN_ROOT = ROOT / "AgentMicrofoundations"
MAIN = ROOT / "AgentMicrofoundations.lean"
SOURCES = sorted(path for path in LEAN_ROOT.rglob("*.lean")
                 if "Methods" not in path.relative_to(LEAN_ROOT).parts
                 and "ResearchTargets" not in path.relative_to(LEAN_ROOT).parts) + [MAIN]
METHOD_SOURCES = sorted((LEAN_ROOT / "Methods").rglob("*.lean"))


def strip_comments(text: str) -> str:
    text = re.sub(r"/-.*?-/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"--[^\n]*", "", text)


theorems: list[tuple[str, Path, int]] = []
for path in SOURCES:
    source = path.read_text()
    code = strip_comments(source)
    for match in re.finditer(r"\btheorem\s+([A-Za-z_][\w.]*)", code):
        line = code.count("\n", 0, match.start()) + 1
        name = match.group(1)
        if path == MAIN and not name.startswith("AgentMicrofoundations."):
            name = f"AgentMicrofoundations.{name}"
        elif path != MAIN:
            module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
            if not name.startswith(module + "."):
                name = f"{module}.{name}"
        theorems.append((name, path, line))

if not theorems:
    raise SystemExit("No Lean theorem declarations found; refusing to generate an empty theory project.")

audit_lines = ["import AgentMicrofoundations", ""]
audit_lines += [f"#print axioms {name}" for name, _, _ in theorems]
(ROOT / "Audit.lean").write_text("\n".join(audit_lines) + "\n")

method_theorems: list[tuple[str, Path, int]] = []
for path in METHOD_SOURCES:
    source = path.read_text()
    code = strip_comments(source)
    for match in re.finditer(r"\btheorem\s+([A-Za-z_][\w.]*)", code):
        line = code.count("\n", 0, match.start()) + 1
        name = match.group(1)
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if not name.startswith(module + "."):
            name = f"{module}.{name}"
        method_theorems.append((name, path, line))

method_audit_lines = ["import AgentMicrofoundations.Methods", ""]
method_audit_lines += [f"#print axioms {name}" for name, _, _ in method_theorems]
(ROOT / "MethodsAudit.lean").write_text("\n".join(method_audit_lines) + "\n")

method_index_lines = [
    "# Auxiliary mathematical tools",
    "",
    "> Generated from Lean sources under `AgentMicrofoundations/Methods/`. These are reusable proof tools, not agent-economics foundation claims.",
    "",
    f"Auxiliary theorem declarations found: **{len(method_theorems)}**.",
    "",
    "| Result | Lean source | Status |",
    "|---|---|---|",
]
for name, path, line in method_theorems:
    rel = path.relative_to(ROOT).as_posix()
    method_index_lines.append(f"| `{name}` | [`{rel}:{line}`]({rel}#L{line}) | Compiled and audited separately |")
method_index_lines += [
    "",
    "These results may be used to calculate bounds or identify what case data can imply. Their inclusion does not count them as new economic primitives, behavioral assumptions, or novel agent-economics findings.",
    "",
]
(ROOT / "METHODS_INDEX.md").write_text("\n".join(method_index_lines))

index_lines = [
    "# Lean formalization inventory",
    "",
    "> Generated from the theory/case Lean source tree by `generate_project_artifacts.py`. This is a source inventory, not a count of scientific contributions. Do not edit manually.",
    "",
    f"Formal declarations inventoried: **{len(theorems)}**. Declarations include helper lemmas, arithmetic facts, conditional propositions, and case-specific results; they are not equal in scientific status.",
    "",
    "| Theorem | Lean source | Status in this project |",
    "|---|---|---|",
]
for name, path, line in theorems:
    rel = path.relative_to(ROOT).as_posix()
    index_lines.append(f"| `{name}` | [`{rel}:{line}`]({rel}#L{line}) | Compiled; axiom dependencies audited by generated `Audit.lean` |")
index_lines += [
    "",
    "The signatures and proofs are the formal source of truth for the listed claims. Narrative documents may explain scope and empirical relevance, but a claim is not a proved result unless it maps to a declaration here and passes the verification command. Inclusion in this inventory does not make a result a new agent-economics law.",
    "",
]
(ROOT / "THEORY_INDEX.md").write_text("\n".join(index_lines))
print(f"Generated theory index from {len(theorems)} declarations and auxiliary methods index from {len(method_theorems)} declarations.")
