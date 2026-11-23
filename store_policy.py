"""The store's own policy (STORE_POLICY.md, approved by the PM) split into sections. The AI agent reads the
section for a topic with its store_policy tool and answers from it; nothing here invents policy."""
from __future__ import annotations

import re
from pathlib import Path


POLICY_PATH = Path(__file__).parent / "STORE_POLICY.md"


TOPICS = {"delivery_damage": ["P1"], "installation": ["P2"], "returns": ["P3"], "refunds": ["P4"],
          "cancellation": ["P5"], "order_limits": ["P6"], "payment": ["P7"], "warranty": ["P8", "P2"],
          "delivery_area": ["P9"], "contact": ["P10"]}


def sections() -> dict[str, tuple[str, str]]:
    """{'P1': ('Damaged in delivery', text), ...}, with markdown and the review markers removed."""
    out, cur, title, buf = {}, None, "", []
    for line in POLICY_PATH.read_text().splitlines():
        m = re.match(r"###\s+(P\d+)\.\s+(.*)", line)
        if m:
            if cur:
                out[cur] = (title, _clean("\n".join(buf)))
            cur, title, buf = m.group(1), m.group(2).strip(), []
        elif line.startswith("---") and cur:
            out[cur] = (title, _clean("\n".join(buf)))
            cur = None
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = (title, _clean("\n".join(buf)))
    return out


def _clean(text: str) -> str:
    text = re.sub(r"\*\(Demo:.*?\)\*", "", text)             # internal notes stay out of answers
    text = re.sub(r"\*\(When .*?\)\*", "", text)
    text = text.replace("⚙", "").replace("**", "").replace("*", "")
    text = re.sub(r"^\s*-\s+", "", text, flags=re.M)
    return re.sub(r"[ \t]+", " ", text).strip()


