# CareCarta MRF Catalog

The CareCarta MRF Catalog is a public index of hospital machine-readable files (MRFs) published under federal hospital price-transparency requirements.

The catalog helps researchers, developers, and the public find hospital-hosted MRFs without downloading the underlying price files into this repository. Because hospitals can replace or move their files, catalog URLs represent what was available when the snapshot was created.

## Catalog contents

| File | Contents | Rows in current snapshot |
| --- | --- | ---: |
| `data/facilities.csv` | One row per hospital facility | 7,177 |
| `data/mrf_files.csv` | One row per MRF for facilities with no `cms-hpt.txt` | 1,802 |
| `data/hospitals.csv` | One row per hospital the federal rule applies to | 5,966 |
| `data/facility_display_names.csv` | Reader-friendly facility labels, keyed to `facilities.csv` | 7,177 |
| `data/hospital_display_names.csv` | Reader-friendly hospital labels, keyed to `hospitals.csv` | 5,966 |
| `data/facility_registry_map.csv` | Which facility belongs to which hospital | 5,757 |
| `data/coverage.csv` | Coverage totals by jurisdiction | 56 |
| `data/metadata.json` | Snapshot date, schema version, and record totals | — |

All CSV files are UTF-8 encoded, include a header row, and use standard CSV quoting. Empty fields mean the value was unavailable in the catalog snapshot. Identifier and postal-code fields should be read as strings so leading zeros are preserved.

## Using the data

A facility's price file is found one of two ways:

- **It has a `cms_hpt_txt_url`** (5,239 facilities). Fetch that `cms-hpt.txt` and read the
  facility's `mrf-url` from it. The catalog does not store that MRF URL, because hospitals move
  their files and the TXT is where they declare the current one.
- **It has no `cms_hpt_txt_url`**. Its MRF is in `mrf_files.csv`, joined on `facility_id`:

```text
facilities.facility_id = mrf_files.facility_id
```

A facility never has both. Use `mrf_id` as the unique key for an MRF record and `facility_id` as
the unique key for a hospital facility.

## Display names

The two display-name files provide presentation labels without changing the source
`hospital_name` values used for discovery, matching, and audit evidence. Join
`facility_display_names.csv.key` to `facilities.csv.facility_id`, or
`hospital_display_names.csv.key` to `hospitals.csv.ccn`. Each file repeats the original
`hospital_name` so a catalog refresh that changes a source name is flagged for review.
`display_name` may be the same for more than one record; the stable key identifies the record.
Some labels expand source abbreviations, so they should not be used as identity evidence.

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
| `cms_hpt_txt_url` | URL | Confirmed URL of the facility's CMS-required `cms-hpt.txt` discovery document, which declares its MRF. The same document may list several facilities. |
| `type_2_npi` | String | The facility's organizational (Type 2) National Provider Identifier, from the CMS Hospital Enrollments file matched on `ccn`. Blank when the facility has no CCN, its CCN is not enrolled, or several facilities share its CCN. `metadata.json` names the release used. An MRF declares its hospital's Type 2 NPI, so this ties a price file to its facility. |

## `mrf_files.csv`

One row represents one MRF for a facility that has no `cms_hpt_txt_url`, so a stored URL is the
only way to find its file. The underlying MRF itself is not stored in this repository.

| Column | Type | Description |
| --- | --- | --- |
| `mrf_id` | String | Stable CareCarta identifier for the MRF record. |
| `facility_id` | String | Foreign key referencing `facilities.csv`. |
| `is_current` | Boolean | Whether the MRF was considered current in this catalog snapshot. |
| `mrf_url` | URL | Previously observed MRF endpoint. |
| `mrf_page_url` | URL | Previously observed page linking to the MRF, when available. |
| `file_name` | String | Published or observed file name. |
| `file_format` | String | File extension or machine-readable format, such as `csv`, `json`, or `zip`. |
| `file_type` | String | General CareCarta classification of the file, such as `spreadsheet`, `structured`, or `compressed`. |
| `file_size_bytes` | Integer | Observed file size in bytes, when available. |
| `is_converted_copy` | Boolean | Whether the cataloged file was identified as a converted copy rather than the original published representation. |

## `hospitals.csv`

One row represents one hospital the federal price transparency rule applies to.

This file answers a different question from `facilities.csv`. `facilities.csv` records places where
a price file was seen, which includes locations that are not hospitals in their own right, such as
an outpatient department operating under a hospital's licence. `hospitals.csv` is the list of
hospitals that must publish a file, so it is the list to measure compliance against.

It is built from the CMS Provider of Services file, keeping the hospitals 45 CFR 180.30 applies to
and removing those the rule deems compliant: hospitals run by the Department of Veterans Affairs or
the Department of Defense, hospitals run by an Indian Health Program, and hospitals treating only
people in the custody of penal authorities.

The rule applies to hospitals licensed by a state, which is not the same group as hospitals
certified to bill Medicare. A hospital holding a state licence that does not bill Medicare does not
appear in the CMS file and is added by hand instead. Treat this list as a solid floor rather than
the final word.

| Column | Type | Description |
| --- | --- | --- |
| `ccn` | String | CMS Certification Number. Present for every row taken from CMS data. Read as text to preserve leading zeros. |
| `hospital_name` | String | Published name of the hospital. |
| `city` | String | City in which the hospital is located. |
| `state` | String | Two-letter state, district, or territory code. |
| `postal_code` | String | ZIP or postal code. Read as text to preserve leading zeros. |
| `provider_type` | String | Kind of hospital, such as `short_term_acute`, `critical_access`, `psychiatric`, `rehabilitation`, `long_term_care`, `childrens`, or `rural_emergency`. |
| `bed_count` | Integer | Certified beds, when available. |
| `basis` | String | Where the row came from: `cms_pos` for CMS data, or `manual_supplement` for one added by hand. |

## `facility_registry_map.csv`

One row links a facility in `facilities.csv` to the hospital in `hospitals.csv` it belongs to.

Several facilities can point at one hospital, because a hospital may run several locations under a
single licence. A facility appears here only when the two records share a CMS Certification Number,
so a facility with no confident match is simply absent rather than guessed at.

| Column | Type | Description |
| --- | --- | --- |
| `facility_id` | String | Foreign key referencing `facilities.csv`. |
| `ccn` | String | Foreign key referencing `hospitals.csv`. |
| `match_basis` | String | How the link was made. Always `CCN` today. |

## `coverage.csv`

One row summarizes catalog coverage for a state, the District of Columbia, or a listed U.S. territory.

| Column | Type | Description |
| --- | --- | --- |
| `jurisdiction` | String | Two-letter jurisdiction code. |
| `jurisdiction_type` | String | One of `state`, `district`, or `territory`. |
| `facility_count` | Integer | Number of facilities represented in the jurisdiction. |
| `cms_hpt_txt_facility_count` | Integer | Facilities whose MRF is found through a `cms-hpt.txt`. |
| `mrf_file_count` | Integer | MRF records stored in `mrf_files.csv` for facilities without a `cms-hpt.txt`. |

## Snapshot metadata

`data/metadata.json` records the catalog schema version, publisher, snapshot timestamp, and total counts. The timestamp applies to the catalog release as a whole.

## Validation

Pull requests are checked for schema consistency, unique identifiers, valid facility references, URL syntax, deterministic ordering, coverage totals, and agreement with `metadata.json`.

An empty optional field means the catalog does not contain a confirmed value for that record. It does not establish that the corresponding hospital resource does not exist.

## Canonical endpoint policy

The catalog uses the publication path defined by the federal Hospital Price Transparency requirements. When a `cms-hpt.txt` document and its hospital-location entry can be matched confidently, the entry's `mrf-url` and `source-page-url` determine the catalog's endpoint fields.

`cms_hpt_txt_url` is the canonical discovery endpoint, and for a facility that has one it is the
only endpoint the catalog records. Its MRF and source page are read from that document when
needed. Storing a copy would invite someone to use it after the hospital had moved the file.

`mrf_files.csv` holds a stored endpoint only for facilities with no known `cms-hpt.txt`.

Schema 3.0.0 made this change. Earlier releases also stored the TXT-declared MRF for facilities
with a `cms_hpt_txt_url`, and kept `cms_hpt_txt_url` on `mrf_files.csv`.

## Releases

Each release replaces the CSV artifacts with a new CareCarta catalog snapshot. Collection and normalization are maintained separately from this public data repository.

Catalog updates include only confirmed mappings. Missing or ambiguous information does not replace an existing canonical value.
