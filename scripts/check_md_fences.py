#!/usr/bin/env python3
from pathlib import Path

roots = [
    Path("README.md"),
    Path("vllm-omni-learning-path"),
    Path("llm-learning-path"),
    Path("openclaw-learning-path"),
    Path("claude-code-learning-path"),
    Path("hermes-learning-path"),
    Path("ray-learning-path/05-AI库总览/01-生态全景.md"),
]
bad = []
for r in roots:
    paths = [r] if r.is_file() else sorted(r.rglob("*.md")) if r.is_dir() else []
    for f in paths:
        if "code/" in str(f):
            continue
        t = f.read_text(encoding="utf-8")
        if t.count("```") % 2:
            bad.append((str(f), "unbalanced ``` count"))
print("issues:", len(bad))
for x in bad[:20]:
    print(x)
