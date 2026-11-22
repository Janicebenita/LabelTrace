"""Evidence registry and untrusted-text defenses.

Every tool result registers evidence items (real record ids/hashes). The model may only cite
registry ids, and any 12+ hex identifier it writes must be a prefix of an id actually returned
by a tool; anything else is replaced and reported.
"""
import re

HEX = re.compile(r"\b[0-9a-f]{12,64}\b")
INJECTION = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)|disregard\s+.{0,40}(instruction|rule|polic)"
    r"|system\s+prompt|you\s+are\s+now|new\s+instructions|<\s*/?\s*(system|assistant|tool)"
    r"|\b(mark|set|declare|report)\b.{0,40}\bREADY\b|\b(release|approve)\s+(this|the|every|all)\s+(label|revision)", re.I)

def clip(text, limit=400):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…[truncated]"

class EvidenceRegistry:
    def __init__(self):
        self.items, self._index, self.seen = {}, {}, set()

    def note(self, text):
        self.seen.update(HEX.findall(str(text)))

    def add(self, kind, record_id, summary, tool):
        key = (kind, record_id)
        if key in self._index:
            return self._index[key]
        eid = f"E{len(self.items) + 1}"
        self._index[key] = eid
        self.items[eid] = {"id": eid, "kind": kind, "record_id": str(record_id), "summary": clip(summary, 220), "tool": tool}
        self.note(record_id)
        self.note(summary)
        return eid

    def scrub_ids(self, text):
        """Replace hex identifiers that no tool returned. Returns (text, replaced_count)."""
        count = 0
        def fix(match):
            nonlocal count
            token = match.group(0)
            if any(seen.startswith(token) or token.startswith(seen) for seen in self.seen):
                return token
            count += 1
            return "[unverified-id]"
        return HEX.sub(fix, text), count

def sanitize(value, flags):
    """Clip long strings and flag instruction-like text inside data fields."""
    if isinstance(value, str):
        if INJECTION.search(value):
            flags.append(clip(value, 80))
        return clip(value)
    if isinstance(value, list):
        return [sanitize(v, flags) for v in value]
    if isinstance(value, dict):
        return {k: sanitize(v, flags) for k, v in value.items()}
    return value
