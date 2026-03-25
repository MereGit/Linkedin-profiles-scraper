"""
This module takes care of writing in the csv the links of the persons
that were found in the search/extraction/validation pipeline
"""
from __future__ import annotations

import logging
from pathlib import Path
import csv
from dataclasses import is_dataclass
from typing import Iterable, Mapping, Any, Sequence, Union

logger = logging.getLogger("finder.storage.writers")

from ..models import PersonResult


DEFAULT_COLUMNS = [
    "name",
    "firm",
    "linkedin_url",
    "status",
]


RowLike = Union[PersonResult, Mapping[str, Any]]


def _normalize_row(row: RowLike) -> dict:
    """
    Function that normalizes datastructures/normalized rows used
    in the pipeline for csv writing
    @arg Rowlike: PersonResult dataclass or dict-like row
    @returns a plain dict suitable for csv.DictWriter
    """
    if isinstance(row, PersonResult):
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


# -------------------------------------------------
# Temp CSV helpers for multi-threaded processing
# -------------------------------------------------

def get_temp_csv_path(output_dir: Path, thread_index: int) -> Path:
    """Returns the deterministic temp CSV path for a given thread index."""
    return output_dir / f"temp_thread_{thread_index}.csv"


def discover_temp_csvs(output_dir: Path) -> list[Path]:
    """Finds all existing temp_thread_*.csv files, sorted by index."""
    return sorted(output_dir.glob("temp_thread_*.csv"))


def read_done_persons_from_csv(csv_path: Path) -> tuple[set[tuple[str, str]], set[str]]:
    """
    Reads a CSV and extracts the set of processed (name, firm) pairs and known URLs.
    @arg csv_path: path to any CSV with the default columns
    @returns (persons_set, urls_set). Returns empty sets if file missing/empty.
    """
    persons = set()
    urls = set()
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return persons, urls
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        if not reader.fieldnames or "name" not in reader.fieldnames:
            return persons, urls
        for row in reader:
            persons.add((row["name"], row["firm"]))
            url = row.get("linkedin_url", "")
            if url and url != "N/A":
                urls.add(url)
    return persons, urls


def read_csv_rows(csv_path: Path) -> list[dict]:
    """
    Reads all rows from a CSV as plain dicts.
    @arg csv_path: path to a CSV file
    @returns list of row dicts. Empty list if file missing/empty.
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return []
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            rows.append(dict(row))
    return rows


def merge_temp_csvs(output_dir: Path, final_path: Path, person_order: list[tuple[str, str]]) -> None:
    """
    Merges all temp CSVs and the existing final CSV into a single
    sorted, deduplicated output file.
    @arg output_dir: directory containing temp_thread_*.csv files
    @arg final_path: path to the final Urls.csv
    @arg person_order: ordered list of all (name, firm) tuples from persons.csv (for sorting)
    """
    # Build ordering index
    order_map = {person: i for i, person in enumerate(person_order)}
    fallback_order = len(person_order)

    # Collect all rows: final CSV + temps
    all_rows = read_csv_rows(final_path)
    for temp_path in discover_temp_csvs(output_dir):
        all_rows.extend(read_csv_rows(temp_path))

    # Deduplicate by (name, firm)
    seen = set()
    unique_rows = []
    for row in all_rows:
        key = (row.get("name", ""), row.get("firm", ""))
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    # Sort by original persons.csv order
    unique_rows.sort(key=lambda r: order_map.get((r.get("name", ""), r.get("firm", "")), fallback_order))

    # Overwrite the final CSV
    write_csv(rows=unique_rows, output_path=final_path, columns=DEFAULT_COLUMNS, mode="w")
    logger.info(f"Merged {len(unique_rows)} rows into {final_path}")


def delete_temp_csvs(output_dir: Path) -> None:
    """Discovers and deletes all temp CSV files in the output directory."""
    for temp_path in discover_temp_csvs(output_dir):
        temp_path.unlink()
        logger.info(f"Deleted temp file: {temp_path}")
