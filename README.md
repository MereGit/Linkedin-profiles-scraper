# LinkedIn Profile Finder

Automated pipeline that discovers LinkedIn profiles for key corporate roles at a list of target companies. It combines Google search, URL filtering, and LLM-powered validation to match the right person to the right firm and role, then exports the results to CSV.

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
     |  query_builder  |   Build search string: "Linkedin profile: {firm} {role}"
     +---------+-------+
               |
       +-------v-------+
       |   web_search   |   Google search with rate-limiting & CAPTCHA detection
       +-------+-------+
               |
    +----------v----------+
    | linkedin_validator   |   Filter: keep only linkedin.com/in/ or /pub/ URLs
    +----------+----------+
               |
       +-------v-------+
       |   validation   |   DuckDuckGo snippet lookup + GPT-4o-mini classification
       +-------+-------+
               |
        +------v------+
        |   writers    |   Append validated result to output CSV
        +-------------+
```

For each firm, the pipeline iterates through roles **by priority tier** (Highest > Medium > Lower). It stops as soon as a match is found for a firm, then moves on to the next one.

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
|       +-- Urls.csv               # Pipeline results
|
|-- src/
|   +-- finder/
|       |-- __init__.py            # Package marker
|       |-- main.py                # Orchestrator / entry point
|       |-- models.py              # RoleResult dataclass & ResultStatus enum
|       |-- logger.py              # Centralised logging configuration
|       |
|       |-- search/
|       |   |-- __init__.py
|       |   |-- query_builder.py   # Builds the Google search query string
|       |   +-- web_search.py      # Executes the search with backoff & CAPTCHA handling
|       |
|       |-- extract/
|       |   |-- __init__.py
|       |   |-- linkedin_validator.py  # URL normalisation & LinkedIn profile detection
|       |   +-- validation.py          # LLM-based role/firm match validation
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
- An **OpenAI API key** (used by the LLM validation step via `gpt-4o-mini`)
- Internet access (Google search + DuckDuckGo lookups)

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
| `OPENAI_API_KEY` | Yes | Your OpenAI API key. Used by the validation step (`gpt-4o-mini`). |

Set it before running:

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-..."

# macOS / Linux
export OPENAI_API_KEY="sk-..."
```

---

## Usage

Run the pipeline from the **project root**:

```bash
cd src
python -m finder.main
```

The script will:

1. Load firms from `data/Input/firms.csv`
2. Load role priorities from `data/Input/roles.yaml`
3. For each firm, iterate through roles by priority
4. Google-search each firm+role combination
5. Filter results to LinkedIn profile URLs only
6. Validate each candidate profile with the LLM
7. Write the first match (or an N/A row) to `data/Output/Urls.csv`

---

## Output

Results are appended to `data/Output/Urls.csv` with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `role` | The matched role (or `N/A`) | `CEO` |
| `firm` | The target company | `Acme Corp` |
| `name` | Profile holder's name (from the LinkedIn title) | `John Doe` |
| `linkedin_url` | Full LinkedIn profile URL | `https://www.linkedin.com/in/johndoe` |
| `status` | Validation status code (see below) | `match_` |

---

## Logging

The pipeline uses Python's `logging` module with timestamped, levelled output to the terminal.

**Format:** `[HH:MM:SS] LEVEL | module | message`

### Key log messages

| Level | Source | What it tells you |
|-------|--------|-------------------|
| INFO | `finder.main` | Firm progress (`Processing firm 3/120: "Acme Corp"`) |
| INFO | `finder.main` | Match found and CSV append confirmation |
| WARNING | `finder.main` | No match found for a firm |
| INFO | `finder.search.web_search` | Google search executed and result count |
| WARNING | `finder.search.web_search` | CAPTCHA/block detected |
| ERROR | `finder.search.web_search` | Search exception |
| INFO | `finder.extract.validation` | DuckDuckGo lookup and LLM invocation |
| INFO | `finder.extract.validation` | Raw LLM response (`LLM response: "TRUE"`) |
| WARNING | `finder.extract.validation` | No LinkedIn profile found in DuckDuckGo results |
| DEBUG | `finder.search.query_builder` | Built query string |
| DEBUG | `finder.storage.writers` | Individual row written to CSV |

To enable DEBUG-level output, change the setup call in `main.py`:

```python
setup_logger(level=logging.DEBUG)
```

### Example terminal output

```
[14:32:01] INFO | finder.main | Loaded 50 firms and 3 priority tiers
[14:32:01] INFO | finder.main | Processing firm 1/50: "Acme Corp"
[14:32:01] INFO | finder.main | Searching: firm="Acme Corp" role="HR_Director"
[14:32:05] INFO | finder.search.web_search | Executing Google search: "Linkedin profile: Acme Corp HR_Director"
[14:32:07] INFO | finder.search.web_search | Search returned 10 results
[14:32:07] INFO | finder.main | Google returned 10 results, 2 are LinkedIn profiles
[14:32:07] INFO | finder.extract.validation | DuckDuckGo lookup for: https://www.linkedin.com/in/janedoe
[14:32:08] INFO | finder.extract.validation | LLM validation for https://www.linkedin.com/in/janedoe | firm="Acme Corp" role="HR_Director"
[14:32:09] INFO | finder.extract.validation | LLM response: "TRUE"
[14:32:09] INFO | finder.extract.validation | Validation result: Perfect match (status=TRUE)
[14:32:09] INFO | finder.main | MATCH for "Acme Corp": role="HR_Director" url=https://www.linkedin.com/in/janedoe status=TRUE
[14:32:09] INFO | finder.main | Appended result to CSV: "Acme Corp" — HR_Director
```

---

## Validation Statuses

The LLM classifies each candidate profile into one of these statuses:

| LLM Response | `ResultStatus` Enum | CSV Value | Meaning |
|-------------|---------------------|-----------|---------|
| `TRUE` | `TOTAL_MATCH` | `match_` | Role and firm both confirmed |
| `MISSING_FIRM` | `MISSING_FIRM` | `miss_firm` | Role matches but firm not mentioned |
| `DIFFERENT_FIRM` | `DIFFERENT_FIRM` | `diff_firm` | Role matches but firm is different |
| `WRONG_ROLE` | `WRONG_ROLE` | `wr_role` | Firm matches but role does not |
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

### Rate Limiting

`web_search.py` introduces a random 3-8 second delay before each Google search to mimic human behaviour. If a CAPTCHA/block is detected in the response, it waits an additional 60 seconds before continuing.

### URL Filtering

`linkedin_validator.py` applies a two-stage filter:

1. **Normalisation** -- strips query params, fragments, trailing slashes, and forces HTTPS
2. **Classification** -- accepts only URLs with paths starting with `/in/` or `/pub/`, and rejects known non-profile paths (`/company/`, `/jobs/`, `/school/`, etc.)

### LLM Validation

`validation.py` uses DuckDuckGo to retrieve the title and snippet for a candidate LinkedIn URL, then sends them to `gpt-4o-mini` via LangChain with a strict prompt that constrains the model to respond with exactly one of five classification labels.

---

## Limitations and Caveats

- **Google rate limiting** -- running against a large number of firms may trigger CAPTCHAs. The built-in backoff helps but is not foolproof.
- **DuckDuckGo availability** -- snippet retrieval depends on DuckDuckGo indexing the LinkedIn URL. Recently created profiles may not be found.
- **LLM accuracy** -- `gpt-4o-mini` may occasionally misclassify roles, especially with non-English job titles or abbreviated role names.
- **No proxy support** -- all requests go through your machine's default network. For large-scale runs, consider adding proxy rotation.
- **Single-threaded** -- firms are processed sequentially. Parallelism is not implemented.

---

## License

This project is not currently published under a specific license. All rights reserved by the author.
