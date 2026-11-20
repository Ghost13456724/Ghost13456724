"""Loading, saving and looking things up in the canon files."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("NOVELBOT_DATA", os.path.join(ROOT, "data"))


def _path(name, data_dir=None):
    return os.path.join(data_dir or DATA, name)


def load(name, data_dir=None):
    with open(_path(name, data_dir), encoding="utf-8") as f:
        return json.load(f)


def save(name, obj, data_dir=None):
    path = _path(name, data_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def resolve(canon, name):
    """Return the canonical character name for a name or alias, or None."""
    if not name:
        return None
    want = name.strip().lower()
    for key, char in canon["characters"].items():
        if key.lower() == want:
            return key
        if want in (a.lower() for a in char.get("aliases", [])):
            return key
    # Fall back to a partial match, but only when it points at one character.
    hits = [k for k, c in canon["characters"].items()
            if any(want in n.lower() for n in [k] + c.get("aliases", []))]
    return hits[0] if len(hits) == 1 else None


def get(canon, name):
    key = resolve(canon, name)
    if key is None:
        raise KeyError(f"unknown character: {name}")
    return key, canon["characters"][key]
