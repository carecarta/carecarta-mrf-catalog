# CareCarta MRF Catalog

The CareCarta MRF Catalog is a public index of hospital machine-readable files (MRFs) published under federal hospital price-transparency requirements.

The catalog helps researchers, developers, and the public find hospital-hosted MRFs without downloading the underlying price files into this repository. Because hospitals can replace or move their files, catalog URLs represent what was available when the snapshot was created.

## Catalog contents

| File | Contents | Rows in current snapshot |
| --- | --- | ---: |
| `data/facilities.csv` | One row per hospital facility | 7,177 |
| `data/mrf_files.csv` | One row per observed MRF file | 7,041 |
| `data/coverage.csv` | Coverage totals by jurisdiction | 56 |
| `data/metadata.json` | Snapshot date, schema version, and record totals | — |

All CSV files are UTF-8 encoded, include a header row, and use standard CSV quoting. Empty fields mean the value was unavailable in the catalog snapshot. Identifier and postal-code fields should be read as strings so leading zeros are preserved.

## Using the data

Join `mrf_files.csv` to `facilities.csv` using `facility_id`:

```text
facilities.facility_id = mrf_files.facility_id
```

A facility can have multiple MRF records. Use `mrf_id` as the unique key for an individual MRF record and `facility_id` as the unique key for a hospital facility.

## `facilities.csv`

One row represents one hospital facility.

| Column | Type | Description |
| --- | --- | --- |
| `facility_id` | String | Stable CareCarta identifier for the facility. |
| `hospital_name` | String | Published name of the hospital or facility. |
| `address_line1` | String | Primary street address. |
| `city` | String | City in which the facility is located. |
| `state` | String | Two-letter state, district, or territory code. |
| `postal_code` | String | ZIP or postal code. Read as text to preserve leading zeros. |
| `phone` | String | Published facility telephone number, when available. |
| `ccn` | String | CMS Certification Number, when available. Read as text to preserve leading zeros. |
| `bed_count` | Integer | Published number of facility beds, when available. |
| `latitude` | Decimal | Facility latitude in decimal degrees. |
| `longitude` | Decimal | Facility longitude in decimal degrees. |
| `hospital_website` | URL | Main public website for the hospital or facility. |

## `mrf_files.csv`

One row represents one MRF associated with a facility. The underlying MRF itself is not stored in this repository.

| Column | Type | Description |
| --- | --- | --- |
| `mrf_id` | String | Stable CareCarta identifier for the MRF record. |
| `facility_id` | String | Foreign key referencing `facilities.csv`. |
| `is_current` | Boolean | Whether the MRF was considered current in this catalog snapshot. |
| `mrf_url` | URL | Direct MRF URL declared by the matched `cms-hpt.txt` entry when `cms_hpt_txt_url` is populated. Otherwise, the catalog retains the previously observed endpoint while discovery remains unresolved. |
| `mrf_page_url` | URL | Source-page URL declared by the matched `cms-hpt.txt` entry when available. Otherwise, the catalog retains the previously observed page. |
| `cms_hpt_txt_url` | URL | Confirmed URL of the CMS-required `cms-hpt.txt` discovery document associated with the MRF. The same document may contain entries for multiple facilities and MRF records. |
| `file_name` | String | Published or observed file name. |
| `file_format` | String | File extension or machine-readable format, such as `csv`, `json`, or `zip`. |
| `file_type` | String | General CareCarta classification of the file, such as `spreadsheet`, `structured`, or `compressed`. |
| `file_size_bytes` | Integer | Observed file size in bytes, when available. |
| `is_converted_copy` | Boolean | Whether the cataloged file was identified as a converted copy rather than the original published representation. |

## `coverage.csv`

One row summarizes catalog coverage for a state, the District of Columbia, or a listed U.S. territory.

| Column | Type | Description |
| --- | --- | --- |
| `jurisdiction` | String | Two-letter jurisdiction code. |
| `jurisdiction_type` | String | One of `state`, `district`, or `territory`. |
| `facility_count` | Integer | Number of facilities represented in the jurisdiction. |
| `mrf_file_count` | Integer | Number of MRF records represented in the jurisdiction. This can exceed `facility_count` because a facility may have multiple files. |

## Snapshot metadata

`data/metadata.json` records the catalog schema version, publisher, snapshot timestamp, and total counts. The timestamp applies to the catalog release as a whole.

## Validation

Pull requests are checked for schema consistency, unique identifiers, valid facility references, URL syntax, deterministic ordering, coverage totals, and agreement with `metadata.json`.

An empty optional field means the catalog does not contain a confirmed value for that record. It does not establish that the corresponding hospital resource does not exist.

## Canonical endpoint policy

The catalog uses the publication path defined by the federal Hospital Price Transparency requirements. When a `cms-hpt.txt` document and its hospital-location entry can be matched confidently, the entry's `mrf-url` and `source-page-url` determine the catalog's endpoint fields.

`cms_hpt_txt_url` is the canonical discovery endpoint. `mrf_url` and `mrf_page_url` preserve the endpoints that document declared when this catalog snapshot was observed; they are useful direct links, but are not a claim that the hospital has not changed them since. Consumers that need the current declared MRF should fetch and parse `cms_hpt.txt` again rather than treating the catalog's stored MRF URL as permanently authoritative.

Alternative observations may assist discovery, but they do not replace the URLs declared through a confirmed `cms-hpt.txt` entry. If the required discovery document is unavailable, malformed, ambiguous, or cannot be matched confidently, the catalog does not infer replacement endpoint values.

When a declared MRF URL replaces a previously observed URL, URL-derived file metadata is refreshed where the format is unambiguous, and the prior file size is cleared until the declared file is measured directly.

## Releases

Each release replaces the CSV artifacts with a new CareCarta catalog snapshot. Collection and normalization are maintained separately from this public data repository.

Catalog updates include only confirmed mappings. Missing or ambiguous information does not replace an existing canonical value.
