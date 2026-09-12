#!/usr/bin/env python3
"""Validate the public CareCarta MRF catalog contract."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SCHEMAS = {
    "facilities.csv": [
        "facility_id",
        "hospital_name",
        "address_line1",
        "city",
        "state",
        "postal_code",
        "phone",
        "ccn",
        "bed_count",
        "latitude",
        "longitude",
        "hospital_website",
    ],
    "mrf_files.csv": [
        "mrf_id",
        "facility_id",
        "is_current",
        "mrf_url",
        "mrf_page_url",
        "cms_hpt_txt_url",
        "file_name",
        "file_format",
        "file_type",
        "file_size_bytes",
        "is_converted_copy",
    ],
    "coverage.csv": [
        "jurisdiction",
        "jurisdiction_type",
        "facility_count",
        "mrf_file_count",
    ],
}

REQUIRED_FACILITY_FIELDS = {"facility_id", "hospital_name", "state"}
REQUIRED_MRF_FIELDS = {
    "mrf_id",
    "facility_id",
    "is_current",
    "mrf_url",
    "file_name",
    "file_type",
    "is_converted_copy",
}
BOOLEAN_FIELDS = {"is_current", "is_converted_copy"}
TERRITORIES = {"AS", "GU", "MP", "PR", "VI"}


def read_csv(name: str, errors: list[str]) -> list[dict[str, str]]:
    path = DATA / name
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SCHEMAS[name]:
            errors.append(
                f"{name}: schema mismatch; expected {SCHEMAS[name]}, found {reader.fieldnames}"
            )
        rows = list(reader)
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            errors.append(f"{name}:{row_number}: row has more fields than the header")
    return rows


def is_catalog_url(value: str, *, allow_bare_domain: bool = False) -> bool:
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        return False
    if value.startswith("blob:https://") or value.startswith("blob:http://"):
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme in {"http", "https"} and bool(parsed.netloc):
        return True
    return allow_bare_domain and not parsed.scheme and "." in parsed.path.split("/")[0]


def require_unique_sorted(
    rows: list[dict[str, str]], field: str, filename: str, errors: list[str]
) -> None:
    values = [row[field] for row in rows]
    if len(values) != len(set(values)):
        errors.append(f"{filename}: {field} values are not unique")
    if values != sorted(values):
        errors.append(f"{filename}: rows are not sorted by {field}")


def validate() -> list[str]:
    errors: list[str] = []
    facilities = read_csv("facilities.csv", errors)
    mrf_files = read_csv("mrf_files.csv", errors)
    coverage = read_csv("coverage.csv", errors)

    require_unique_sorted(facilities, "facility_id", "facilities.csv", errors)
    require_unique_sorted(mrf_files, "mrf_id", "mrf_files.csv", errors)
    require_unique_sorted(coverage, "jurisdiction", "coverage.csv", errors)

    facility_ids = {row["facility_id"] for row in facilities}
    facilities_by_id = {row["facility_id"]: row for row in facilities}

    for row_number, row in enumerate(facilities, start=2):
        for field in REQUIRED_FACILITY_FIELDS:
            if not row[field]:
                errors.append(f"facilities.csv:{row_number}: {field} is required")
        if row["facility_id"] and not row["facility_id"].startswith("cc:"):
            errors.append(f"facilities.csv:{row_number}: invalid facility_id")
        if row["bed_count"]:
            try:
                int(row["bed_count"])
            except ValueError:
                errors.append(f"facilities.csv:{row_number}: bed_count is not an integer")
        for field in ("latitude", "longitude"):
            if row[field]:
                try:
                    float(row[field].rstrip(","))
                except ValueError:
                    errors.append(f"facilities.csv:{row_number}: {field} is not numeric")
        if row["hospital_website"] and not is_catalog_url(row["hospital_website"]):
            errors.append(f"facilities.csv:{row_number}: invalid hospital_website")

    for row_number, row in enumerate(mrf_files, start=2):
        for field in REQUIRED_MRF_FIELDS:
            if not row[field]:
                errors.append(f"mrf_files.csv:{row_number}: {field} is required")
        if row["mrf_id"] and not row["mrf_id"].startswith("cc:"):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_id")
        if row["facility_id"] not in facility_ids:
            errors.append(f"mrf_files.csv:{row_number}: unknown facility_id")
        for field in BOOLEAN_FIELDS:
            if row[field] not in {"true", "false"}:
                errors.append(f"mrf_files.csv:{row_number}: {field} must be true or false")
        if not is_catalog_url(row["mrf_url"]):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_url")
        if row["mrf_page_url"] and not is_catalog_url(
            row["mrf_page_url"], allow_bare_domain=True
        ):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_page_url")
        if row["cms_hpt_txt_url"] and not is_catalog_url(row["cms_hpt_txt_url"]):
            errors.append(f"mrf_files.csv:{row_number}: invalid cms_hpt_txt_url")
        if row["file_size_bytes"] and not row["file_size_bytes"].isdigit():
            errors.append(f"mrf_files.csv:{row_number}: file_size_bytes is not an integer")

    facility_counts = Counter(row["state"] for row in facilities)
    mrf_counts = Counter(
        facilities_by_id[row["facility_id"]]["state"]
        for row in mrf_files
        if row["facility_id"] in facilities_by_id
    )
    coverage_by_jurisdiction = {row["jurisdiction"]: row for row in coverage}

    if set(coverage_by_jurisdiction) != set(facility_counts):
        errors.append("coverage.csv: jurisdictions do not match facilities.csv")
    for jurisdiction, facility_count in facility_counts.items():
        row = coverage_by_jurisdiction.get(jurisdiction)
        if not row:
            continue
        expected_type = (
            "district"
            if jurisdiction == "DC"
            else "territory"
            if jurisdiction in TERRITORIES
            else "state"
        )
        if row["jurisdiction_type"] != expected_type:
            errors.append(f"coverage.csv: invalid jurisdiction_type for {jurisdiction}")
        if row["facility_count"] != str(facility_count):
            errors.append(f"coverage.csv: facility_count mismatch for {jurisdiction}")
        if row["mrf_file_count"] != str(mrf_counts[jurisdiction]):
            errors.append(f"coverage.csv: mrf_file_count mismatch for {jurisdiction}")

    metadata = json.loads((DATA / "metadata.json").read_text(encoding="utf-8"))
    expected_metadata = {
        "facility_count": len(facilities),
        "mrf_file_count": len(mrf_files),
        "jurisdiction_count": len(coverage),
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            errors.append(
                f"metadata.json: {field} is {metadata.get(field)!r}; expected {expected}"
            )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(f"Catalog validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors[:100]:
            print(f"- {error}", file=sys.stderr)
        if len(errors) > 100:
            print(f"- ...and {len(errors) - 100} more", file=sys.stderr)
        return 1
    print("Catalog validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
