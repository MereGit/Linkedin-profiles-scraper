"""
This module takes care of writing in the csv the links of the roles
that were found in the search/extraction/validation pipeline
"""
from __future__ import annotations

import logging
from pathlib import Path
import csv
from dataclasses import is_dataclass
from typing import Iterable, Mapping, Any, Sequence, Union

logger = logging.getLogger("finder.storage.writers")

from ..models import RoleResult


DEFAULT_COLUMNS = [
    "role",
    "firm",
    "name",
    "linkedin_url",
    "status",
]


RowLike = Union[RoleResult, Mapping[str, Any]]


def _normalize_row(row: RowLike) -> dict:
    """
    Function that normalizes datastructures/normalized rows used
    in the pipeline for csv writing
    @arg Rowlike: RoleResult dataclass or dict-like row
    @returns a plain dict suitable for csv.DictWriter
    """
    if isinstance(row, RoleResult):
        return row.to_row()

    if isinstance(row, Mapping):
        # Make a shallow copy and normalize None -> ""
        d = dict(row)
        for k, v in d.items():
            if v is None:
                d[k] = ""
        return d

    # Support other dataclasses if you add them later
    if is_dataclass(row):
        d = dict(row.__dict__)
        for k, v in d.items():
            if v is None:
                d[k] = ""
        return d

    raise TypeError(f"Unsupported row type: {type(row)}")


def _ensure_parent_dir(path: Path) -> None:
    """
    Function that ensures the existence of the path used to
    store the csv
    @arg path: path of the csv
    @executes the creation of the parent folders if they
    don't exist
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(
    rows: Iterable[RowLike],
    output_path: Path,
    columns: Sequence[str] = DEFAULT_COLUMNS,
    mode: str = "w",  # "w" overwrite, "a" append
) -> None:
    """
    Generic CSV writer.
    @arg rows: rowlike object to be appended
    @arg output_path: path for the destination csv
    @arg columns: columns for the csv
    @arg mode:"w" - overwrite and write header
              "a" - append; writes header only if file doesn't exist
    @returns a csv, either it appends the objects to an existing
    one or it creates a new one.
    """
    _ensure_parent_dir(output_path)

    file_exists = output_path.exists()
    write_header = (mode == "w") or (mode == "a" and not file_exists)

    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns))
        if write_header:
            writer.writeheader()

        for row in rows:
            d = _normalize_row(row)
            # Only keep declared columns (avoids random keys breaking your file)
            filtered = {c: d.get(c, "") for c in columns}
            writer.writerow(filtered)
            logger.debug(f"Wrote row: {filtered}")


def write_urls_csv(rows: Iterable[RowLike], output_path: Path) -> None:
    """Convenience wrapper for default output schema."""
    write_csv(rows=rows, output_path=output_path, columns=DEFAULT_COLUMNS, mode="w")


def append_urls_csv(rows: Iterable[RowLike], output_path: Path) -> None:
    """Convenience wrapper for appending."""
    write_csv(rows=rows, output_path=output_path, columns=DEFAULT_COLUMNS, mode="a")