import re
from pathlib import Path

def tokenize_name(p: Path):
    name = " ".join(p.parts).lower()
    tokens = re.findall(r"[a-z0-9]+", name)
    return set(tokens)
