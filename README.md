# LinkedIn Profile Finder

Automated pipeline that discovers LinkedIn profiles for key corporate roles at a list of target companies. It combines DuckDuckGo search, URL filtering, and LLM-powered validation to match the right person to the right firm and role, then exports the results to CSV.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Input Files](#input-files)
  - [Roles Priority](#roles-priority)
  - [Environment Variables](#environment-variables)
- [Usage](#usage)
  - [Multi-Threading](#multi-threading)
  - [Resume and Fault Tolerance](#resume-and-fault-tolerance)
- [Output](#output)
- [Logging](#logging)
- [Validation Statuses](#validation-statuses)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Limitations and Caveats](#limitations-and-caveats)
- [License](#license)

---

## How It Works

```
firms.csv          roles.yaml
    |                   |
    +-------+  +--------+
            |  |
     +------v--v------+
     |     main.py     |   Split firms across N threads, detect/resume from temp CSVs
     +------+--+------+
            |  |
   +--------+  +--------+   (one per thread)
   |                     |
   v                     v
+--+--+  +------+  +--+--+
| T-1 |  | T-2  |  | T-N |  Each thread processes its chunk independently:
+--+--+  +--+---+  +--+--+
   |        |         |
   v        v         v
+--+--------+---------+--+
|      query_builder      |   Build search string: "site:it.linkedin.com/in/ {firm} {role}"
+------------+------------+
             |
  +----------v----------+
  |     validation       |   DuckDuckGo search + LinkedIn URL filtering + GPT-5-mini classification
  +----------+----------+
             |
  +----------v----------+
  |   writers (append)   |   Each thread writes to its own temp_thread_{i}.csv
  +----------+----------+
             |
  +----------v----------+     (after all threads join)
  |   merge_temp_csvs    |   Merge all temps + existing Urls.csv, sort by firms.csv order
  +----------+----------+
             |
  +----------v----------+
  |   delete_temp_csvs   |   Auto-cleanup temp files
  +---------------------+
```

For each firm, the pipeline iterates through roles **by priority tier** (Highest > Medium > Lower). It stops as soon as up to 2 matches are found for a firm, then moves on to the next one. Firms are split across multiple threads for parallel processing, each writing to its own temporary CSV. After all threads finish, results are merged into a single output file sorted by the original `firms.csv` order.

---

## Project Structure

```
Linkedin-profiles-scraper/
|
|-- config/
|   +-- Settings.yaml              # Reserved for future configuration
|
|-- data/
|   |-- Input/
|   |   |-- firms.csv              # List of target companies (one "firms" column)
|   |   +-- roles.yaml             # Prioritised list of roles to search for
|   +-- Output/
|       |-- Urls.csv               # Final merged pipeline results
|       +-- temp_thread_*.csv      # Per-thread temp files (created at runtime, auto-deleted after merge)
|
|-- src/
|   +-- finder/
|       |-- __init__.py            # Package marker
|       |-- main.py                # Multi-threaded orchestrator / entry point
|       |-- models.py              # RoleResult dataclass & ResultStatus enum
|       |-- logger.py              # Centralised logging configuration (includes thread name)
|       |
|       |-- search/
|       |   |-- __init__.py
|       |   +-- query_builder.py   # Builds the search query string
|       |
|       |-- extract/
|       |   |-- __init__.py
|       |   |-- linkedin_validator.py  # URL normalisation & LinkedIn profile detection
|       |   +-- validation.py          # DuckDuckGo search, LinkedIn filtering & LLM-based validation
|       |
|       +-- storage/
|           |-- __init__.py
|           +-- writers.py         # CSV writer + temp CSV lifecycle helpers (discover, merge, cleanup)
|
|-- requirements.txt
|-- pyproject.toml
+-- .gitignore
```

---

## Prerequisites

- **Python 3.10+**
- An **OpenAI API key** (used by the LLM validation step via `gpt-5-mini`)
- Internet access (DuckDuckGo search)

---

## Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd Linkedin-profiles-scraper

# 2. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

### Input Files

#### `data/Input/firms.csv`

A CSV file with a header row containing a `firms` column. Each subsequent row is a company name to search for.

```csv
firms
Acme Corp
Contoso Ltd
Fabrikam Inc
```

#### `data/Input/roles.yaml`

A YAML file defining three priority tiers of roles. The pipeline tries **Highest priority** roles first, then **Medium**, then **Lower**, stopping at the first match per firm.

```yaml
Highest priority:
  - HR_Director
  - Chief Human Resources Officer (CHRO)

Medium priority:
  - CEO
  - Managing Director

Lower priority:
  - Chief Technology Officer (CTO)
  - Chief Digital Officer (CDO)
```

### Roles Priority

The default `roles.yaml` ships with these tiers:

| Tier | Roles |
|------|-------|
| **Highest** | HR Director, Direttore Risorse Umane, CHRO, Head of People, Head of People Operations |
| **Medium** | CEO, Chief Executive Officer, Amministratore Delegato, Managing Director, Direttore Generale |
| **Lower** | TISO, CTO, CINO, CPO, Chief Talent Officer, CDO, Chief Transformation Officer, CSO |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key. Used by the validation step (`gpt-5-mini`). |

Set it before running:

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-..."

# macOS / Linux
export OPENAI_API_KEY="sk-..."
```

---

## Usage

Run the pipeline from the **`src` directory**:

```bash
cd src

# Single-threaded (default)
python -m finder.main

# Multi-threaded (e.g. 4 threads)
python -m finder.main 4
```

The script will:

1. Load firms from `data/Input/firms.csv` and role priorities from `data/Input/roles.yaml`
2. Check `data/Output/Urls.csv` and any existing temp CSVs for already-processed firms
3. Split the remaining firms across `N` threads (default 1)
4. Each thread processes its chunk in parallel: build query, search DuckDuckGo, filter LinkedIn URLs, validate with the LLM, and append results to its own `temp_thread_{i}.csv`
5. After all threads complete, merge all temp CSVs into `Urls.csv` sorted by the original `firms.csv` order, then delete the temp files

### Multi-Threading

The optional first argument sets the number of threads:

```bash
python -m finder.main 3    # splits firms across 3 threads
```

Each thread writes to its own temporary CSV (`temp_thread_0.csv`, `temp_thread_1.csv`, ...) in `data/Output/`. This eliminates write contention between threads. Cross-thread URL deduplication is still enforced via a shared lock on the `known_urls` set.

After all threads finish, the temp CSVs are merged into the final `Urls.csv`, sorted to match the original order of firms in `firms.csv`, and the temp files are automatically deleted.

If there are fewer firms than threads, only as many threads as needed are spawned.

### Resume and Fault Tolerance

The pipeline is designed to be **safely restartable**:

- **Interrupted run, same thread count:** On restart, each thread detects which firms it already completed by reading its own temp CSV, and resumes from where it left off.
- **Interrupted run, different thread count:** If temp CSVs from a previous run exist but the thread count has changed (e.g. 3 temp files exist but you now run with 2 threads), the pipeline merges the old temp results into `Urls.csv`, deletes the stale temp files, and re-splits the remaining firms across the new thread count.
- **Thread crash:** If a single thread encounters a fatal error, its temp CSV retains all results written up to that point. Other threads continue unaffected. On the next run, the crashed thread's remaining firms are picked up.
- **Per-firm errors:** If processing a single firm fails (e.g. network timeout), the error is logged and the thread moves on to the next firm.

---

## Output

Results are written to `data/Output/Urls.csv`, sorted by the original `firms.csv` order, with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `role` | The matched role (or `N/A`) | `CEO` |
| `firm` | The target company | `Acme Corp` |
| `name` | Profile title (from the DuckDuckGo result) | `John Doe` |
| `linkedin_url` | Full LinkedIn profile URL | `https://www.linkedin.com/in/johndoe` |
| `status` | Validation status code (see below) | `match_` |

---

## Logging

The pipeline uses Python's `logging` module with timestamped, levelled output to the terminal. Every log line includes the **thread name** so you can trace which thread produced each message.

**Format:** `[HH:MM:SS] LEVEL | ThreadName | module | message`

### Key log messages

| Level | Source | What it tells you |
|-------|--------|-------------------|
| INFO | `finder.main` | Firm progress (`Processing firm 3/40: "Acme Corp"`) |
| INFO | `finder.main` | Match found and temp CSV append confirmation |
| INFO | `finder.main` | Merge and cleanup status after all threads complete |
| WARNING | `finder.main` | No match found for a firm, thread count mismatch detected |
| INFO | `finder.extract.validation` | DuckDuckGo search and LLM invocation |
| WARNING | `finder.extract.validation` | No LinkedIn profile found in DuckDuckGo results |
| DEBUG | `finder.search.query_builder` | Built query string |
| DEBUG | `finder.storage.writers` | Individual row written to CSV, temp file merge/delete operations |

To enable DEBUG-level output, change the setup call in `main.py`:

```python
setup_logger(level=logging.DEBUG)
```

### Example terminal output (multi-threaded)

```
[14:32:01] INFO | MainThread | finder.main | Using 2 threads for processing
[14:32:01] INFO | MainThread | finder.main | Loaded 50 total firms (10 already in Urls.csv)
[14:32:01] INFO | MainThread | finder.main | No temp CSVs found — fresh run
[14:32:01] INFO | MainThread | finder.main | 40 firms pending processing
[14:32:01] INFO | Thread-1 | finder.main | Processing firm 1/20: "Acme Corp"
[14:32:01] INFO | Thread-2 | finder.main | Processing firm 1/20: "Contoso Ltd"
[14:32:01] INFO | Thread-1 | finder.main | Searching: firm="Acme Corp" role="HR_Director"
[14:32:05] INFO | Thread-1 | finder.extract.validation | LLM validation for https://www.linkedin.com/in/janedoe | firm="Acme Corp" role="HR_Director"
[14:32:06] INFO | Thread-1 | finder.extract.validation | Validation result: Perfect match (status=TRUE)
[14:32:06] INFO | Thread-1 | finder.main | MATCH for "Acme Corp": role="HR_Director" url=https://www.linkedin.com/in/janedoe status=TRUE
[14:32:06] INFO | Thread-1 | finder.main | Appended result to temp CSV: "Acme Corp" — HR_Director
...
[14:35:22] INFO | MainThread | finder.storage.writers | Merged 50 rows into data/Output/Urls.csv
[14:35:22] INFO | MainThread | finder.storage.writers | Deleted temp file: data/Output/temp_thread_0.csv
[14:35:22] INFO | MainThread | finder.storage.writers | Deleted temp file: data/Output/temp_thread_1.csv
[14:35:22] INFO | MainThread | finder.main | All threads completed. Results merged and temp files cleaned up.
```

---

## Validation Statuses

The LLM classifies each candidate profile into one of these statuses:

| LLM Response | `ResultStatus` Enum | CSV Value | Meaning |
|-------------|---------------------|-----------|---------|
| `TRUE` | `TOTAL_MATCH` | `match_` | Role and firm both confirmed |
| `MISSING_FIRM` | `MISSING_FIRM` | `miss_firm` | Role matches but firm not mentioned |
| `FALSE` | `NOT_MATCH` | `Not matched` | Neither role nor firm found |

When no profile is found at all for a firm, the pipeline writes a row with `status = Not matched` and all fields set to `N/A`.

---

## Architecture Deep Dive

### Data Model

The core data structure is the `RoleResult` frozen dataclass defined in `models.py`:

```python
@dataclass(frozen=True, slots=True)
class RoleResult:
    role: str
    firm: str
    linkedin_url: Optional[str] = None
    status: ResultStatus = ResultStatus.NOT_MATCH
    name: Optional[str] = None
```

Being frozen, instances are updated via `dataclasses.replace()` to create new copies with modified fields.

### URL Filtering

`linkedin_validator.py` applies a two-stage filter:

1. **Normalisation** -- strips query params, fragments, trailing slashes, and forces HTTPS
2. **Classification** -- accepts only URLs with paths starting with `/in/` or `/pub/`, and rejects known non-profile paths (`/company/`, `/jobs/`, `/school/`, etc.)

### Search & LLM Validation

`validation.py` combines search and validation in a single step:

1. Searches DuckDuckGo (region `it-it`, max 25 results) using the query built by `query_builder`
2. Iterates through results and filters for LinkedIn profile URLs using `linkedin_validator`
3. For the first matching LinkedIn URL, extracts the title and snippet from the DuckDuckGo result
4. Sends them to `gpt-5-mini` via LangChain with a strict prompt that constrains the model to respond with exactly one of three classification labels (`TRUE`, `MISSING_FIRM`, `FALSE`)

### Temp CSV Lifecycle

The `writers.py` module manages the full lifecycle of per-thread temporary CSV files:

1. **`get_temp_csv_path`** -- deterministic naming (`temp_thread_0.csv`, `temp_thread_1.csv`, ...) so the next run can find and resume from them
2. **`discover_temp_csvs`** -- glob-based discovery of existing temp files to detect previous interrupted runs
3. **`read_done_firms_from_csv`** / **`read_csv_rows`** -- read back firms and URLs from any CSV (temp or final) for resume and merge logic
4. **`merge_temp_csvs`** -- collects rows from all temp CSVs + the existing `Urls.csv`, deduplicates by `(firm, linkedin_url)`, sorts by original `firms.csv` order, and overwrites the final output
5. **`delete_temp_csvs`** -- cleanup after a successful merge

---

## Limitations and Caveats

- **DuckDuckGo availability** -- search and snippet retrieval depend on DuckDuckGo indexing the LinkedIn URL. Recently created profiles may not be found.
- **DuckDuckGo rate limiting** -- running against a large number of firms may trigger rate limits or temporary blocks from DuckDuckGo.
- **LLM accuracy** -- `gpt-5-mini` may occasionally misclassify roles, especially with non-English job titles or abbreviated role names.
- **No proxy support** -- all requests go through your machine's default network. For large-scale runs, consider adding proxy rotation.
- **DuckDuckGo/OpenAI rate limiting with threads** -- running multiple threads increases the request rate to both DuckDuckGo and the OpenAI API. If you hit rate limits, reduce the thread count.
- **GIL** -- Python's GIL does not limit this workload because it is I/O-bound (network requests). Threads release the GIL during HTTP calls, achieving real parallelism.

---

## License

This project is not currently published under a specific license. All rights reserved by the author.
