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
        "cms_hpt_txt_url",
        "type_2_npi",
    ],
    "mrf_files.csv": [
        "mrf_id",
        "facility_id",
        "is_current",
        "mrf_url",
        "mrf_page_url",
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
        "cms_hpt_txt_facility_count",
        "mrf_file_count",
    ],
    "hospitals.csv": [
        "ccn",
        "hospital_name",
        "city",
        "state",
        "postal_code",
        "provider_type",
        "bed_count",
        "basis",
    ],
    "facility_registry_map.csv": [
        "facility_id",
        "ccn",
        "match_basis",
    ],
}

# hospitals.csv lists the hospitals the price transparency rule applies to, and
# facility_registry_map.csv says which observed facility belongs to which of them. They are
# optional until the first registry snapshot is published, but neither is meaningful alone.
REGISTRY_BASES = {"cms_pos", "manual_supplement"}
REQUIRED_HOSPITAL_FIELDS = {"hospital_name", "state", "provider_type", "basis"}

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


def npi_is_valid(value: str) -> bool:
    """An NPI is ten digits whose last is a Luhn check over the number prefixed with 80840."""
    if len(value) != 10 or not value.isdigit():
        return False
    total = 0
    for index, digit in enumerate(int(d) for d in reversed("80840" + value)):
        if index % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def ccn_missing_leading_zero(value: str) -> bool:
    """A CCN is six characters. A five-digit one has lost the zero of its state code (060116 as
    60116), which silently breaks every join on CCN."""
    return len(value) == 5 and value.isdigit()


def require_unique_sorted(
    rows: list[dict[str, str]], field: str, filename: str, errors: list[str]
) -> None:
    values = [row[field] for row in rows]
    if len(values) != len(set(values)):
        errors.append(f"{filename}: {field} values are not unique")
    if values != sorted(values):
        errors.append(f"{filename}: rows are not sorted by {field}")


def validate_registry(facility_ids: set[str]) -> list[str]:
    """Check the hospital registry and its mapping to observed facilities.

    The registry and the catalog are refreshed on different schedules by different processes, so
    the mapping between them is the part most likely to rot. Both files are checked only when
    present, which lets this validation merge before the first registry snapshot does.
    """
    errors: list[str] = []
    has_hospitals = (DATA / "hospitals.csv").exists()
    has_map = (DATA / "facility_registry_map.csv").exists()
    if not has_hospitals and not has_map:
        return errors
    if not has_hospitals:
        return ["facility_registry_map.csv: present without hospitals.csv"]

    hospitals = read_csv("hospitals.csv", errors)
    keys = []
    seen: set[tuple[str, ...]] = set()
    for row_number, row in enumerate(hospitals, start=2):
        for field in REQUIRED_HOSPITAL_FIELDS:
            if not row[field]:
                errors.append(f"hospitals.csv:{row_number}: {field} is required")
        if row["basis"] not in REGISTRY_BASES:
            errors.append(
                f"hospitals.csv:{row_number}: basis must be one of {sorted(REGISTRY_BASES)}"
            )
        # A hospital derived from CMS data is identified by its certification number. One added by
        # hand may have none, because a hospital can hold a state licence without billing Medicare.
        if row["basis"] == "cms_pos" and not row["ccn"]:
            errors.append(f"hospitals.csv:{row_number}: ccn is required for cms_pos rows")
        if row["bed_count"]:
            try:
                int(row["bed_count"])
            except ValueError:
                errors.append(f"hospitals.csv:{row_number}: bed_count is not an integer")
        identity = (
            ("ccn", row["ccn"])
            if row["ccn"]
            else ("name", row["hospital_name"], row["state"], row["postal_code"])
        )
        if identity in seen:
            errors.append(f"hospitals.csv:{row_number}: duplicate hospital {identity}")
        seen.add(identity)
        keys.append((row["basis"], row["ccn"], row["hospital_name"], row["state"]))
    if keys != sorted(keys):
        errors.append("hospitals.csv: rows are not sorted by basis, ccn, hospital_name, state")

    known_ccns = {row["ccn"] for row in hospitals if row["ccn"]}
    if not has_map:
        return errors

    mapping = read_csv("facility_registry_map.csv", errors)
    facility_column = [row["facility_id"] for row in mapping]
    if len(facility_column) != len(set(facility_column)):
        errors.append("facility_registry_map.csv: facility_id values are not unique")
    # Grouped by hospital rather than by facility, so one hospital's locations read together.
    order = [(row["ccn"], row["facility_id"]) for row in mapping]
    if order != sorted(order):
        errors.append("facility_registry_map.csv: rows are not sorted by ccn, facility_id")
    for row_number, row in enumerate(mapping, start=2):
        name = "facility_registry_map.csv"
        if row["match_basis"] != "CCN":
            errors.append(f"{name}:{row_number}: match_basis must be CCN")
        if row["facility_id"] not in facility_ids:
            errors.append(f"{name}:{row_number}: facility_id is not in facilities.csv")
        if row["ccn"] not in known_ccns:
            errors.append(f"{name}:{row_number}: ccn is not in hospitals.csv")
    return errors


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
        if row["cms_hpt_txt_url"] and not is_catalog_url(row["cms_hpt_txt_url"]):
            errors.append(f"facilities.csv:{row_number}: invalid cms_hpt_txt_url")
        if ccn_missing_leading_zero(row["ccn"]):
            errors.append(f"facilities.csv:{row_number}: ccn {row['ccn']} is missing its leading zero")
        if row["type_2_npi"] and not npi_is_valid(row["type_2_npi"]):
            errors.append(f"facilities.csv:{row_number}: invalid type_2_npi")

    # A facility that publishes a cms-hpt.txt declares its MRF there. A stored copy of that URL
    # goes stale when the hospital moves the file, so such a facility carries no MRF row.
    txt_facilities = {row["facility_id"] for row in facilities if row["cms_hpt_txt_url"]}

    for row_number, row in enumerate(mrf_files, start=2):
        for field in REQUIRED_MRF_FIELDS:
            if not row[field]:
                errors.append(f"mrf_files.csv:{row_number}: {field} is required")
        if row["mrf_id"] and not row["mrf_id"].startswith("cc:"):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_id")
        if row["facility_id"] not in facility_ids:
            errors.append(f"mrf_files.csv:{row_number}: unknown facility_id")
        if row["facility_id"] in txt_facilities:
            errors.append(
                f"mrf_files.csv:{row_number}: facility has a cms_hpt_txt_url, so its MRF is "
                "declared there and must not be stored"
            )
        for field in BOOLEAN_FIELDS:
            if row[field] not in {"true", "false"}:
                errors.append(f"mrf_files.csv:{row_number}: {field} must be true or false")
        if not is_catalog_url(row["mrf_url"]):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_url")
        if row["mrf_page_url"] and not is_catalog_url(
            row["mrf_page_url"], allow_bare_domain=True
        ):
            errors.append(f"mrf_files.csv:{row_number}: invalid mrf_page_url")
        if row["file_size_bytes"] and not row["file_size_bytes"].isdigit():
            errors.append(f"mrf_files.csv:{row_number}: file_size_bytes is not an integer")

    facility_counts = Counter(row["state"] for row in facilities)
    txt_counts = Counter(row["state"] for row in facilities if row["cms_hpt_txt_url"])
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
        if row["cms_hpt_txt_facility_count"] != str(txt_counts[jurisdiction]):
            errors.append(f"coverage.csv: cms_hpt_txt_facility_count mismatch for {jurisdiction}")
        if row["mrf_file_count"] != str(mrf_counts[jurisdiction]):
            errors.append(f"coverage.csv: mrf_file_count mismatch for {jurisdiction}")

    errors.extend(validate_registry(facility_ids))

    metadata = json.loads((DATA / "metadata.json").read_text(encoding="utf-8"))
    expected_metadata = {
        "facility_count": len(facilities),
        "mrf_file_count": len(mrf_files),
        "cms_hpt_txt_facility_count": len(txt_facilities),
        "jurisdiction_count": len(coverage),
        "schema_version": "3.1.0",
        "type_2_npi_count": sum(1 for row in facilities if row["type_2_npi"]),
    }
    if (DATA / "hospitals.csv").exists():
        hospitals = read_csv("hospitals.csv", [])
        expected_metadata["hospital_count"] = len(hospitals)
    if not metadata.get("type_2_npi_source"):
        errors.append("metadata.json: type_2_npi_source must name the NPI source and release")
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
