# LinkedIn Profile Finder

Automated pipeline that discovers LinkedIn profiles for specific people at target companies. It combines DuckDuckGo search, URL filtering, and LLM-powered validation to match the right person to the right firm, then exports the results to CSV.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Input Files](#input-files)
  - [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Output](#output)
- [Multi-threading](#multi-threading)
- [Logging](#logging)
- [Validation Statuses](#validation-statuses)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Limitations and Caveats](#limitations-and-caveats)
- [License](#license)

---

## How It Works

```
persons.csv
    |
    v
+----------------+
| query_builder  |   Build search string: "site:it.linkedin.com/in/ {name} {firm}"
+-------+--------+
        |
+-------v-----------+
|     validation     |   DuckDuckGo search + LinkedIn URL filtering + GPT-5-mini classification
+-------+-----------+
        |
+-------v------+
|   writers     |   Append validated result to output CSV
+--------------+
```

For each (name, firm) pair in the input, the pipeline searches DuckDuckGo, filters for LinkedIn profile URLs, validates the match with an LLM, and writes the result to CSV.

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
|   |   +-- persons.csv            # List of (name, firm) pairs to search for
|   +-- Output/
|       +-- Urls.csv               # Pipeline results
|
|-- src/
|   +-- finder/
|       |-- __init__.py            # Package marker
|       |-- main.py                # Orchestrator / entry point
|       |-- models.py              # PersonResult dataclass & ResultStatus enum
|       |-- logger.py              # Centralised logging configuration
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
|           +-- writers.py         # Generic CSV writer with append/overwrite support
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

#### `data/Input/persons.csv`

A CSV file with two columns: `name` (the person to search for) and `firm` (the company they work at).

```csv
name,firm
Marco Rossi,Lavazza
Giulia Bianchi,TIM
Luigi Verdi,Pirelli
```

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
python -m finder.main
```

The script will:

1. Load person+firm pairs from `data/Input/persons.csv`
2. For each pair, build a query and search DuckDuckGo
3. Filter results to LinkedIn profile URLs only
4. Validate each candidate profile with the LLM
5. Write the match (or an N/A row) to `data/Output/Urls.csv`

To run with multiple threads:

```bash
python -m finder.main 4   # uses 4 threads
```

---

## Output

Results are written to `data/Output/Urls.csv` with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `name` | The person searched for (from input) | `Marco Rossi` |
| `firm` | The target company | `Lavazza` |
| `linkedin_url` | Full LinkedIn profile URL (or `N/A`) | `https://it.linkedin.com/in/marco-rossi` |
| `status` | Validation status code (see below) | `match_` |

---

## Multi-threading

The pipeline supports multi-threaded processing to speed up large runs:

```bash
python -m finder.main 4   # split work across 4 threads
```

- Each thread writes to its own temporary CSV (`temp_thread_0.csv`, etc.)
- At the end, all temp files are merged into the final `Urls.csv`, sorted by input order, and deduplicated
- **Resume support**: if the process is interrupted and restarted with the same thread count, it picks up where it left off
- **Thread count mismatch**: if restarted with a different thread count, partial results are merged into `Urls.csv` first, then processing restarts with remaining persons
- A shared lock prevents duplicate URLs across threads

---

## Logging

The pipeline uses Python's `logging` module with timestamped, levelled output to the terminal.

**Format:** `[HH:MM:SS] LEVEL | ThreadName | module | message`

### Key log messages

| Level | Source | What it tells you |
|-------|--------|-------------------|
| INFO | `finder.main` | Person progress (`Processing person 3/120: "Marco Rossi" at "Lavazza"`) |
| INFO | `finder.main` | Match found and CSV append confirmation |
| WARNING | `finder.main` | No match found for a person |
| INFO | `finder.extract.validation` | DuckDuckGo search and LLM invocation |
| WARNING | `finder.extract.validation` | No LinkedIn profile found in DuckDuckGo results |
| DEBUG | `finder.search.query_builder` | Built query string |
| DEBUG | `finder.storage.writers` | Individual row written to CSV |

To enable DEBUG-level output, change the setup call in `main.py`:

```python
setup_logger(level=logging.DEBUG)
```

### Example terminal output

```
[14:32:01] INFO | Thread-1 | finder.main | Loaded 50 total persons (0 already in Urls.csv)
[14:32:01] INFO | Thread-1 | finder.main | Processing person 1/50: "Marco Rossi" at "Lavazza"
[14:32:01] INFO | Thread-1 | finder.main | Searching: person="Marco Rossi" firm="Lavazza"
[14:32:05] INFO | Thread-1 | finder.extract.validation | LLM validation for https://it.linkedin.com/in/marco-rossi | person="Marco Rossi" firm="Lavazza"
[14:32:09] INFO | Thread-1 | finder.extract.validation | Validation result: Perfect match (status=TRUE)
[14:32:09] INFO | Thread-1 | finder.main | MATCH for "Marco Rossi" at "Lavazza": url=https://it.linkedin.com/in/marco-rossi status=TRUE
[14:32:09] INFO | Thread-1 | finder.main | Appended result to temp CSV: "Marco Rossi" at "Lavazza"
```

---

## Validation Statuses

The LLM classifies each candidate profile into one of these statuses:

| LLM Response | `ResultStatus` Enum | CSV Value | Meaning |
|-------------|---------------------|-----------|---------|
| `TRUE` | `TOTAL_MATCH` | `match_` | Person and firm both confirmed |
| `FALSE` | `NOT_MATCH` | `Not matched` | Person or firm not found |

When no profile is found at all for a person, the pipeline writes a row with `status = Not matched` and `linkedin_url = N/A`.

---

## Architecture Deep Dive

### Data Model

The core data structure is the `PersonResult` frozen dataclass defined in `models.py`:

```python
@dataclass(frozen=True, slots=True)
class PersonResult:
    name: str
    firm: str
    linkedin_url: Optional[str] = None
    status: ResultStatus = ResultStatus.NOT_MATCH
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
4. Sends them to `gpt-5-mini` via LangChain with a strict prompt that constrains the model to respond with exactly `TRUE` or `FALSE`

---

## Limitations and Caveats

- **DuckDuckGo availability** -- search and snippet retrieval depend on DuckDuckGo indexing the LinkedIn URL. Recently created profiles may not be found.
- **DuckDuckGo rate limiting** -- running against a large number of persons may trigger rate limits or temporary blocks from DuckDuckGo.
- **LLM accuracy** -- `gpt-5-mini` may occasionally misclassify, especially with common names or non-standard name spellings.
- **No proxy support** -- all requests go through your machine's default network. For large-scale runs, consider adding proxy rotation.

---

## License

This project is not currently published under a specific license. All rights reserved by the author.
