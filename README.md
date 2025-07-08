# PubMed Pharmaceutical/Biotech Paper Search Tool

A Python command-line tool to search PubMed for research papers and identify those with at least one author affiliated with pharmaceutical or biotech companies.

## Features

- Searches PubMed using the full PubMed query syntax
- **Dynamically fetches pharmaceutical/biotech companies from multiple APIs**
  - ClinicalTrials.gov API (trial sponsors)
  - OpenFDA API (drug manufacturers) 
  - Wikidata SPARQL (pharmaceutical company database)
  - Falls back to comprehensive hardcoded list
- **Smart caching system** (updates weekly, configurable)
- Identifies papers with pharmaceutical/biotech company affiliations
- Extracts detailed paper information including:
  - PubMed ID
  - Title
  - Publication date
  - Non-academic authors (those affiliated with pharma/biotech companies)
  - Company affiliations
  - Corresponding author email
- Outputs results as CSV file or console output
- Debug mode for troubleshooting
- **Query validation and comprehensive syntax help**

## Installation

### Prerequisites
- Python 3.8 or higher
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management

### Setup with Poetry

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/pubmed-pharma-search.git
cd pubmed-pharma-search
```

2. **Install dependencies with Poetry:**
```bash
poetry install
```

This will create a virtual environment and install all required dependencies including BioPython and requests.

3. **Activate the Poetry shell (optional):**
```bash
poetry shell
```

### Legacy Installation (pip)

Alternatively, you can still use pip:
```bash
pip install -r requirements.txt
```

## Usage

### Using the Executable Command (Recommended)

After installation with Poetry, you can use the `get-papers-list` command:

```bash
# Basic usage
poetry run get-papers-list "cancer drug discovery"

# Save to file with debug information
poetry run get-papers-list "CRISPR therapeutics" -f results.csv -d

# Advanced query with field tags
poetry run get-papers-list "COVID-19[MeSH] AND vaccine" -f covid_pharma.csv
```

### If Poetry Shell is Active

If you've activated the Poetry shell with `poetry shell`, you can run the command directly:

```bash
get-papers-list "cancer drug discovery"
get-papers-list "CRISPR therapeutics" -f results.csv -d
```

### Legacy Usage (Direct Python Script)

You can still use the original script directly:

```bash
python pubmed_pharma_search.py "your search query"
```

### Command-line Options

- `-h, --help`: Display usage instructions
- `-f, --file FILENAME`: Save results to a CSV file (if not provided, prints to console)
- `-d, --debug`: Print debug information during execution
- `--max-results N`: Maximum number of papers to retrieve (default: 100)
- `--email EMAIL`: Email address for PubMed API (default: user@example.com)
- `--validate-query`: Validate query syntax and show components without executing search
- `--query-help`: Show detailed PubMed query syntax help and exit
- **`--update-companies`**: Force update pharmaceutical/biotech company database from APIs
- **`--show-company-stats`**: Show statistics about the company database and exit
- **`--use-hardcoded-only`**: Use only hardcoded company list (skip API fetching)
- **`--clean-company-cache`**: Clean and rebuild company cache with improved filtering

### Company Database Management

The tool automatically fetches pharmaceutical/biotech companies from multiple APIs and caches them locally for performance. The cache is updated weekly by default.

**View current company database:**
```bash
python pubmed_pharma_search.py --show-company-stats
```

**Force update company database:**
```bash
python pubmed_pharma_search.py --update-companies
```

**Use only hardcoded companies (offline mode):**
```bash
python pubmed_pharma_search.py "your query" --use-hardcoded-only -f results.csv
```

**Clean and rebuild company cache (if data quality issues):**
```bash
python pubmed_pharma_search.py --clean-company-cache
```

### Query Validation and Help

**Validate your query syntax:**
```bash
python pubmed_pharma_search.py 'cancer AND (pfizer[ad] OR novartis[ad])' --validate-query
```

**Get comprehensive query syntax help:**
```bash
python pubmed_pharma_search.py --query-help
```

### Examples

1. **Basic search with console output:**
```bash
python pubmed_pharma_search.py "cancer drug discovery"
```

2. **Search with file output:**
```bash
python pubmed_pharma_search.py "CRISPR therapeutics" -f results.csv
```

3. **Search with debug information:**
```bash
python pubmed_pharma_search.py "COVID-19[MeSH] AND vaccine" -f covid_pharma.csv -d
```

4. **Search with custom parameters:**
```bash
python pubmed_pharma_search.py "immunotherapy" --max-results 50 --email your.email@domain.com -f immuno_results.csv
```

5. **Advanced field-specific searches:**
```bash
# Search for papers with "CRISPR" in title from biotech companies
python pubmed_pharma_search.py "CRISPR[ti] AND biotech*[ad]" -f crispr_biotech.csv

# Find clinical trials on cancer drugs
python pubmed_pharma_search.py "cancer[mh] AND drug[tiab] AND clinical trial[pt]" -f cancer_trials.csv
```

6. **Date-restricted searches:**
```bash
# Recent papers (last 2 years) on AI in drug discovery
python pubmed_pharma_search.py '"artificial intelligence"[tiab] AND "drug discovery"[tiab] AND last 2 years[dp]' -f recent_ai_drugs.csv

# Papers from 2020-2023 on COVID vaccines from pharma
python pubmed_pharma_search.py 'COVID-19[mh] AND vaccine[ti] AND pharma*[ad] AND 2020:2023[dp]' -f covid_pharma_2020_2023.csv
```

7. **Complex multi-field queries:**
```bash
# Comprehensive search: Cancer immunotherapy from top pharma companies, recent publications
python pubmed_pharma_search.py '(cancer[mh] OR neoplasm*[tiab]) AND immunotherapy[tiab] AND (pfizer[ad] OR roche[ad] OR novartis[ad] OR merck[ad]) AND 2022:2025[dp]' -f comprehensive_cancer_immuno.csv
```

## PubMed Query Syntax - ALL FEATURES SUPPORTED

This tool supports the **complete PubMed query syntax** with all advanced features:

### 🔹 Boolean Operators
- `AND`, `OR`, `NOT` (case-insensitive, but uppercase recommended)
- Use parentheses to group terms: `(term1 OR term2) AND term3`

Examples:
```
cancer AND chemotherapy
(aspirin OR ibuprofen) AND headache
diabetes NOT "type 1"
```

### 🔹 Field Tags
Target specific parts of articles with bracketed tags:

| Field | Tag | Description | Example |
|-------|-----|-------------|---------|
| Title | `[ti]` or `[Title]` | Article title only | `"gene therapy"[ti]` |
| Title/Abstract | `[tiab]` | Title and abstract | `"CRISPR"[tiab]` |
| Author | `[au]` or `[Author]` | Author names | `"Smith JA"[au]` |
| Journal | `[ta]` or `[Journal]` | Journal title | `"Nature"[ta]` |
| Affiliation | `[ad]` or `[Affiliation]` | Author institution | `"Pfizer"[ad]` |
| MeSH Terms | `[mh]` or `[MeSH]` | Medical Subject Headings | `"COVID-19"[mh]` |
| Publication Date | `[dp]` or `[Date]` | Publication date | `2023[dp]` |
| Publication Type | `[pt]` | Article type | `"Clinical Trial"[pt]` |

### 🔹 Date Filtering
```
2023/05/12[dp]                    # Exact date
2020/01/01:2023/12/31[dp]         # Date range
2018:2023[dp]                     # Year range
last 6 months[dp]                 # Relative date
last 30 days[dp]                  # Last 30 days
```

### 🔹 Phrases and Wildcards
```
"stem cell therapy"               # Exact phrase
therap*                          # Wildcard (therapy, therapies, therapeutic, etc.)
```

### 🔹 MeSH Terms (Medical Subject Headings)
```
"Neoplasms"[mh]                  # Standard MeSH term
"Drug Therapy"[mh:noexp]         # Don't include subheadings
```

### 🔹 Publication Types
```
"Clinical Trial"[pt]             # Clinical trials
"Review"[pt]                     # Review articles
"Meta-Analysis"[pt]              # Meta-analyses
"Case Reports"[pt]               # Case reports
```

### 🔹 Complex Query Examples

**COVID-19 vaccine trials from pharma companies:**
```bash
python pubmed_pharma_search.py '("COVID-19"[mh] OR "SARS-CoV-2"[mh]) AND vaccine[ti] AND (pfizer[ad] OR moderna[ad]) AND "clinical trial"[pt]' -f covid_trials.csv
```

**Recent AI in drug discovery:**
```bash
python pubmed_pharma_search.py '("artificial intelligence"[tiab] OR "machine learning"[tiab]) AND "drug discovery"[tiab] AND 2020:2025[dp]' -f ai_drugs.csv
```

**Cancer immunotherapy with pharma involvement:**
```bash
python pubmed_pharma_search.py '(cancer[mh] OR tumor[tiab]) AND immunotherapy[tiab] AND (pharma*[ad] OR biotech*[ad])' -f immuno_pharma.csv
```

**Targeted searches with affiliations:**
```bash
python pubmed_pharma_search.py 'alzheimer*[tiab] AND therap*[tiab] AND pharma*[ad]' -f alzheimer_pharma.csv
```

## Output Format

The tool generates a CSV file with the following columns:

1. **PubmedID**: Unique identifier for the paper
2. **Title**: Title of the paper
3. **Publication Date**: Date the paper was published
4. **Non-academic Author(s)**: Names of authors affiliated with pharmaceutical/biotech companies
5. **Company Affiliation(s)**: Names of the pharmaceutical/biotech companies
6. **Corresponding Author Email**: Email address of the corresponding author (if available)

## Company Database

The tool uses a **dynamic, API-powered company database** that fetches pharmaceutical and biotech companies from multiple authoritative sources:

### 🔗 **Data Sources**

1. **ClinicalTrials.gov API**
   - Trial sponsors and collaborators
   - Real-time data from active clinical trials
   - Comprehensive pharmaceutical industry participants

2. **OpenFDA API** 
   - Drug manufacturer information
   - FDA-registered pharmaceutical companies
   - Official regulatory data

3. **Wikidata SPARQL**
   - Structured pharmaceutical company database
   - International company coverage
   - Regularly updated by community

4. **Hardcoded Fallback**
   - Major pharmaceutical companies (Pfizer, J&J, Roche, Novartis, etc.)
   - Biotech companies (Genentech, Moderna, BioNTech, etc.)
   - Contract Research Organizations (CROs)
   - Generic terms indicating pharma/biotech affiliations

### 📈 **Advantages of API-Based Approach**

- **Up-to-date**: Automatically includes new companies and acquisitions
- **Comprehensive**: Covers thousands of companies vs. ~100 hardcoded
- **Accurate**: Uses authoritative government and industry databases  
- **Efficient**: Smart caching minimizes API calls
- **Reliable**: Falls back to hardcoded list if APIs are unavailable

### ⚙️ **Caching System**

- Companies are cached locally in `pharma_companies_cache.json`
- Cache expires after 7 days (configurable)
- First run downloads fresh data, subsequent runs use cache
- Use `--update-companies` to force refresh

## Rate Limiting

The tool is designed to be respectful to the PubMed API:
- Processes papers in batches of 10
- Includes delays between API calls
- Uses appropriate API parameters

## Requirements

- Python 3.6+
- BioPython library for PubMed API access
- Internet connection for API access

## Troubleshooting

1. **Import errors**: Make sure you have installed the required packages with `pip install -r requirements.txt`
2. **No results found**: Try broadening your search query or check if it's a valid PubMed query
3. **API errors**: Ensure you have a stable internet connection and try again later if the PubMed servers are busy
4. **Use debug mode**: Add the `-d` flag to see detailed information about what the tool is doing

## License

This tool is provided as-is for educational and research purposes. 