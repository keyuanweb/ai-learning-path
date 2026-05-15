#!/usr/bin/env python3
"""
Convert unlabeled Markdown ``` fences that look like flow/ASCII diagrams
into ```mermaid blocks. Skips labeled code fences (python, bash, ...).

Used for vllm-omni-learning-path and llm-learning-path batch conversion.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_LANGS = frozenset(
    {
        "mermaid",
        "python",
        "py",
        "bash",
        "sh",
        "shell",
        "json",
        "yaml",
        "yml",
        "toml",
        "text",
        "rust",
        "go",
        "typescript",
        "ts",
        "javascript",
        "js",
        "sql",
        "html",
        "xml",
        "diff",
        "dockerfile",
        "makefile",
        "c",
        "cpp",
        "java",
        "kotlin",
        "swift",
        "ruby",
        "php",
        "r",
        "tex",
        "latex",
        "markdown",
        "md",
    }
)

# Lines that are only tree/connector noise
_NOISE = re.compile(r"^[\s│├└┌┐┘┬┴─┼▶\d\.]*$")


def _strip_tree_prefix(line: str) -> str:
    s = line.rstrip()
    s = re.sub(r"^[│\s]*", "", s)
    s = re.sub(r"^[├└][──]*(?:[→>])?\s*", "", s)
    s = re.sub(r"^\d+\.\s*", "", s)
    return s.strip()


def _should_convert(body: str) -> bool:
    raw = body.strip()
    if not raw:
        return False
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return False
    first = lines[0].lstrip()
    if first.startswith(
        ("import ", "from ", "def ", "class ", "$ ", ">>> ", "curl ", "wget ", "pip ")
    ):
        return False
    if first.startswith("#!"):
        return False
    joined = "\n".join(lines)
    if any(
        ln.lstrip().startswith(("import ", "from ", "def ", "class ", "@"))
        for ln in lines[:20]
    ):
        return False
    # ASCII 表格示意（多列 ┼/│），用 Markdown 表呈现更合适，不自动转 Mermaid
    if joined.count("┼") >= 1 and lines[0].count("│") >= 2:
        return False
    # Heuristic: flow-like content
    if any(c in joined for c in "├└│┌▼→▶↓↑"):
        return True
    if "──→" in joined or "->" in joined:
        return True
    if "→" in joined and len(lines) >= 2:
        return True
    # Numbered pipeline in omni style
    if sum(1 for ln in lines if re.match(r"^\s*\d+\.", ln)) >= 2 and (
        "│" in joined or "→" in joined or "├" in joined
    ):
        return True
    # Timeline style: year at line start
    if re.search(r"^\s*\d{4}\s", joined, re.MULTILINE) and "→" in joined:
        return True
    # Stage / pipeline prose with tree markers
    if "├──" in joined and ("Stage" in joined or "→" in joined or "─" in joined):
        return True
    return False


def _body_to_mermaid(body: str) -> str:
    lines = [ln.rstrip() for ln in body.splitlines()]
    cleaned: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        if _NOISE.fullmatch(ln):
            continue
        lab = _strip_tree_prefix(ln)
        if not lab or lab == "│":
            continue
        lab = lab.replace('"', "'").replace("\n", " ")
        cleaned.append(lab)
    if not cleaned:
        return "flowchart TD\n  empty[\"（空流程）\"]"
    # Prefer LR for single-line chains with many arrows; else TD
    use_lr = (
        len(cleaned) >= 3
        and all(len(x) < 120 for x in cleaned)
        and sum(1 for x in cleaned if "→" in x or "->" in x) >= max(1, len(cleaned) // 3)
    )
    kind = "flowchart LR" if use_lr else "flowchart TD"
    out = [kind]
    for i, lab in enumerate(cleaned):
        out.append(f'  n{i}["{lab}"]')
    for i in range(len(cleaned) - 1):
        out.append(f"  n{i} --> n{i + 1}")
    return "\n".join(out)


def process_markdown(text: str) -> tuple[str, int]:
    """Return (new_text, num_replacements)."""
    out: list[str] = []
    i = 0
    replaced = 0
    while i < len(text):
        j = text.find("```", i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        nl = text.find("\n", j + 3)
        if nl == -1:
            out.append(text[j:])
            break
        lang = text[j + 3 : nl].strip().lower()
        end = text.find("\n```", nl)
        if end == -1:
            out.append(text[j:])
            break
        body = text[nl + 1 : end]
        if lang == "" and _should_convert(body):
            m = _body_to_mermaid(body)
            out.append("```mermaid\n" + m + "\n```")
            replaced += 1
        else:
            out.append(text[j : end + 4])
        i = end + 4
    return "".join(out), replaced


def main() -> None:
    roots = [Path(p) for p in sys.argv[1:]]
    total_files = 0
    total_repl = 0
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            if "code/" in str(path):
                continue
            old = path.read_text(encoding="utf-8")
            new, n = process_markdown(old)
            if n:
                path.write_text(new, encoding="utf-8")
                print(f"{path}: {n} block(s)")
                total_files += 1
                total_repl += n
    print(f"Done. {total_files} files, {total_repl} replacements.")


if __name__ == "__main__":
    main()
