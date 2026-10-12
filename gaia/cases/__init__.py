"""
Gaia — the shipped cases (Step 7): JSON documents in ``gaia/cases/data``.

    load_case("forest")            -> gaia.ecosystem_io.Case
    load_case("my_case.json")      -> the same, from a file
    load_case("forest").build_ecosystem(total_units=2000)

``gaia run <case | file.json>`` runs one. The modules ``forest``,
``costa_brava``, ``posidonia`` and ``amazon_forest`` are compatibility
wrappers kept for one release (deprecated, removed in Gaia 0.11).
"""

import functools
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from gaia.ecosystem_io import Case, case_from_dict, read_json

DATA_DIR: Path = Path(__file__).resolve().parent / "data"
CASE_NAMES: Tuple[str, ...] = ("forest", "costa_brava", "posidonia", "amazon_forest")
CASE_ALIASES: Dict[str, str] = {
    "costa-brava": "costa_brava",
    "amazon": "amazon_forest",
    "amazon-forest": "amazon_forest",
}


def resolve_case_name(name: str) -> Optional[str]:
    """The shipped case called ``name`` (or one of its aliases), or None."""
    name = CASE_ALIASES.get(name, name)
    return name if name in CASE_NAMES else None


def case_data_path(name: str) -> Path:
    """Path of a shipped case document.

    Raises:
        ValueError: If ``name`` is not a shipped case.
    """
    resolved = resolve_case_name(name)
    if resolved is None:
        raise ValueError(f"unknown case {name!r} (cases: {', '.join(CASE_NAMES)})")
    return DATA_DIR / f"{resolved}.json"


@functools.lru_cache(maxsize=None)
def _load_shipped(name: str) -> Case:
    path = case_data_path(name)
    data = read_json(path)
    try:
        return case_from_dict(data, origin=name)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None


def load_case(name_or_path: Union[str, Path]) -> Case:
    """A shipped case by name, or the case document at a path.

    A name is tried first, so a file must be given as a path ending in
    ".json" or containing a directory part when it shadows a case name.

    Raises:
        ValueError: Unknown case, unreadable or invalid document (naming
            the JSON path of the problem).
    """
    if isinstance(name_or_path, str):
        resolved = resolve_case_name(name_or_path)
        if resolved is not None:
            return _load_shipped(resolved)
    path = Path(name_or_path)
    if not path.is_file():
        raise ValueError(
            f"unknown case {str(name_or_path)!r}: not a shipped case "
            f"({', '.join(CASE_NAMES)}) and no such file"
        )
    from gaia.ecosystem_io import load_case_file

    return load_case_file(path)
