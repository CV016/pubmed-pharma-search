#!/usr/bin/env python3
"""
PubMed Pharmaceutical/Biotech Paper Search Tool - Core Module

This module provides the main functionality for searching PubMed papers
and identifying those with pharmaceutical or biotech company affiliations.
It includes API-based company data fetching, query validation, and result
processing with comprehensive error handling and type safety.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Union, Any, Iterator, Tuple
from xml.etree import ElementTree as ET

try:
    from Bio import Entrez
    import requests
except ImportError as e:
    print(f"ERROR: Required package not found: {e}")
    print("Please install required packages: poetry install")
    sys.exit(1)

from .models import (
    ApiSource, AuthorInfo, PaperInfo, CompanyCacheData, QueryAnalysis,
    CompanyStats, SearchConfig, ApiError, QueryValidationError, CompanyDataError
)
from .logging_config import get_logger


# Constants
DEFAULT_CACHE_FILE = "pharma_companies_cache.json"
CACHE_EXPIRY_DAYS = 7
API_TIMEOUT = 30
BATCH_SIZE = 10
API_DELAY = 0.5
MAX_RETRIES = 3


class CompanyDataFetcher:
    """Fetches pharmaceutical and biotech company data from various APIs."""
    
    def __init__(self, cache_file: str = DEFAULT_CACHE_FILE, debug: bool = False) -> None:
        """
        Initialize the company data fetcher.
        
        Args:
            cache_file: Path to the cache file for storing company data
            debug: Enable debug mode for verbose logging
        """
        self.cache_file = cache_file
        self.debug = debug
        self.cache_expiry_days = CACHE_EXPIRY_DAYS
        self.logger = get_logger(__name__, debug_mode=debug)
        
    def _debug_print(self, message: str) -> None:
        """
        Print debug message if debug mode is enabled.
        
        Args:
            message: Debug message to print
        """
        self.logger.debug(message)
    
    def _load_cache(self) -> CompanyCacheData:
        """
        Load cached company data from file.
        
        Returns:
            CompanyCacheData object with cached companies and metadata
        """
        if not os.path.exists(self.cache_file):
            return CompanyCacheData(companies=set(), last_updated=None)
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert list back to set for performance
                companies = set(data.get("companies", []))
                last_updated = data.get("last_updated")
                sources_used = [ApiSource(s) for s in data.get("sources_used", [])]
                
                return CompanyCacheData(
                    companies=companies,
                    last_updated=last_updated,
                    sources_used=sources_used
                )
        except (json.JSONDecodeError, ValueError, IOError) as e:
            self.logger.warning(f"Failed to load cache: {e}")
            return CompanyCacheData(companies=set(), last_updated=None)
    
    def _save_cache(self, companies: Set[str], sources_used: List[ApiSource]) -> None:
        """
        Save company data to cache file.
        
        Args:
            companies: Set of company names to cache
            sources_used: List of API sources used to fetch the data
            
        Raises:
            CompanyDataError: If cache file cannot be written
        """
        try:
            cache_data = CompanyCacheData(
                companies=companies,
                last_updated=datetime.now().isoformat(),
                sources_used=sources_used
            )
            
            data = {
                "companies": list(companies),  # Convert set to list for JSON
                "last_updated": cache_data.last_updated,
                "sources_used": [source.value for source in sources_used]
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Cached {len(companies)} companies to {self.cache_file}")
            
        except (IOError, OSError) as e:
            raise CompanyDataError(f"Failed to save cache to {self.cache_file}: {e}") from e
    
    def _is_cache_valid(self, last_updated: Optional[str]) -> bool:
        """
        Check if cache is still valid based on expiry time.
        
        Args:
            last_updated: ISO format timestamp of last cache update
            
        Returns:
            True if cache is valid, False otherwise
        """
        if not last_updated:
            return False
        
        try:
            cache_date = datetime.fromisoformat(last_updated)
            expiry_date = cache_date + timedelta(days=self.cache_expiry_days)
            return datetime.now() < expiry_date
        except ValueError:
            self.logger.warning(f"Invalid timestamp in cache: {last_updated}")
            return False
    
    def fetch_from_clinicaltrials_gov(self) -> Set[str]:
        """
        Fetch pharmaceutical companies from ClinicalTrials.gov API.
        
        Returns:
            Set of company names from clinical trial sponsors
            
        Raises:
            ApiError: If API request fails
        """
        companies = set()
        
        try:
            self.logger.info("Fetching company data from ClinicalTrials.gov API")
            
            # Search for studies with pharmaceutical sponsors
            params = {
                'expr': 'pharmaceutical OR pharma OR biotech OR biotechnology',
                'fields': 'LeadSponsorName,CollaboratorName',
                'min_rnk': 1,
                'max_rnk': 1000,
                'fmt': 'json'
            }
            
            response = requests.get(
                'https://clinicaltrials.gov/api/query/study_fields',
                params=params,
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            studies = data.get('StudyFieldsResponse', {}).get('StudyFields', [])
            
            for study in studies:
                # Extract lead sponsor
                lead_sponsors = study.get('LeadSponsorName', [])
                for sponsor in lead_sponsors:
                    if sponsor and self._is_pharma_biotech_name(sponsor):
                        companies.add(sponsor.lower().strip())
                
                # Extract collaborators
                collaborators = study.get('CollaboratorName', [])
                for collaborator in collaborators:
                    if collaborator and self._is_pharma_biotech_name(collaborator):
                        companies.add(collaborator.lower().strip())
            
            self.logger.info(f"Found {len(companies)} companies from ClinicalTrials.gov")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch data from ClinicalTrials.gov API: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.CLINICAL_TRIALS) from e
        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Failed to parse ClinicalTrials.gov API response: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.CLINICAL_TRIALS) from e
        
        return companies
    
    def fetch_from_openfda(self) -> Set[str]:
        """
        Fetch pharmaceutical companies from OpenFDA API.
        
        Returns:
            Set of company names from drug manufacturers
            
        Raises:
            ApiError: If API request fails
        """
        companies = set()
        
        try:
            self.logger.info("Fetching company data from OpenFDA API")
            
            # Search drug manufacturers
            url = "https://api.fda.gov/drug/label.json"
            params = {
                'search': 'openfda.manufacturer_name:*',
                'count': 'openfda.manufacturer_name.exact',
                'limit': 1000
            }
            
            response = requests.get(url, params=params, timeout=API_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            for result in results:
                manufacturer = result.get('term', '')
                if manufacturer and self._is_pharma_biotech_name(manufacturer):
                    companies.add(manufacturer.lower().strip())
            
            self.logger.info(f"Found {len(companies)} companies from OpenFDA")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch data from OpenFDA API: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.OPENFDA) from e
        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Failed to parse OpenFDA API response: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.OPENFDA) from e
        
        return companies
    
    def fetch_from_wikidata(self) -> Set[str]:
        """
        Fetch pharmaceutical companies from Wikidata SPARQL endpoint.
        
        Returns:
            Set of company names from Wikidata pharmaceutical companies
            
        Raises:
            ApiError: If API request fails
        """
        companies = set()
        
        try:
            self.logger.info("Fetching company data from Wikidata SPARQL endpoint")
            
            # SPARQL query for pharmaceutical companies
            sparql_query = """
            SELECT DISTINCT ?companyLabel WHERE {
              ?company wdt:P31/wdt:P279* wd:Q169336 .  # pharmaceutical company
              ?company rdfs:label ?companyLabel .
              FILTER(LANG(?companyLabel) = "en")
            }
            LIMIT 1000
            """
            
            url = "https://query.wikidata.org/sparql"
            headers = {
                'Accept': 'application/sparql-results+json',
                'User-Agent': 'PubMedPharmaSearch/1.0 (https://github.com/user/repo)'
            }
            
            response = requests.get(
                url,
                params={'query': sparql_query, 'format': 'json'},
                headers=headers,
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            bindings = data.get('results', {}).get('bindings', [])
            
            for binding in bindings:
                company_name = binding.get('companyLabel', {}).get('value', '')
                if company_name:
                    companies.add(company_name.lower().strip())
            
            self.logger.info(f"Found {len(companies)} companies from Wikidata")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch data from Wikidata: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.WIKIDATA) from e
        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Failed to parse Wikidata response: {e}"
            self.logger.error(error_msg)
            raise ApiError(error_msg, ApiSource.WIKIDATA) from e
        
        return companies
    
    def _is_pharma_biotech_name(self, name: str) -> bool:
        """Check if a company name suggests pharmaceutical/biotech focus."""
        if not name or len(name.strip()) < 3:
            return False
            
        name_lower = name.lower().strip()
        
        # Filter out obvious non-pharmaceutical entries
        exclude_patterns = [
            r'^[a-z0-9_\-]{10,}$',  # Random IDs like "ir1_g_341-pflu_misc20815"
            r'^\d+.*alloy.*$',      # Metal alloys like "7178 aluminium alloy"
            r'^[a-z]\d+_\d+',       # Pattern like "r0_171-"
            r'misc\d+',             # Miscellaneous IDs
            r'^test.*',             # Test entries
            r'^example.*',          # Example entries
            r'^sample.*',           # Sample entries
        ]
        
        for pattern in exclude_patterns:
            if re.match(pattern, name_lower):
                return False
        
        # Filter out non-English or corrupted text
        if not re.match(r'^[a-zA-Z0-9\s\-&.,()]+$', name):
            return False
        
        # Keywords that suggest pharma/biotech
        pharma_keywords = [
            'pharmaceutical', 'pharma', 'biotech', 'biotechnology', 'biopharmaceutical',
            'therapeutics', 'medicines', 'drug', 'vaccine', 'biology', 'clinical',
            'research', 'laboratory', 'labs', 'life sciences', 'healthcare',
            'medical', 'therapy', 'treatment', 'diagnostic', 'genomics',
            'bioscience', 'biomedical', 'oncology', 'immunology'
        ]
        
        # Well-known pharma/biotech company patterns
        known_patterns = [
            r'.*pharma.*', r'.*biotech.*', r'.*therapeutics.*', r'.*medicines.*',
            r'.*laboratories.*', r'.*labs.*', r'.*life sciences.*', r'.*biosciences.*'
        ]
        
        # Check keywords
        for keyword in pharma_keywords:
            if keyword in name_lower:
                return True
        
        # Check patterns
        for pattern in known_patterns:
            if re.match(pattern, name_lower):
                return True
        
        # Check if it's a known major pharma company (even without keywords)
        major_pharma = [
            'pfizer', 'roche', 'novartis', 'merck', 'gsk', 'sanofi', 'abbvie',
            'johnson', 'bristol', 'amgen', 'gilead', 'biogen', 'celgene',
            'takeda', 'bayer', 'boehringer', 'lilly', 'astrazeneca', 'regeneron',
            'vertex', 'alexion', 'incyte', 'illumina', 'moderna', 'biontech',
            'genentech', 'genmab', 'seagen', 'bluebird', 'crispr', 'editas',
            'intellia', 'sangamo', 'kite', 'juno', 'novocure', 'neurocrine',
            'sage', 'alkermes', 'acadia', 'arena', 'biomarin', 'ultragenyx',
            'sarepta', 'alnylam', 'ionis'
        ]
        
        for company in major_pharma:
            if company in name_lower:
                return True
        
        # Additional check: company name should have reasonable structure
        words = name_lower.split()
        if len(words) >= 1:
            # At least one word should be substantial (not just initials)
            substantial_words = [w for w in words if len(w) >= 3]
            if not substantial_words:
                return False
        
        return False
    
    def get_hardcoded_companies(self) -> Set[str]:
        """Get the hardcoded fallback list of companies."""
        return {
            # Major Pharmaceutical Companies
            "pfizer", "johnson & johnson", "j&j", "janssen", "roche", "novartis", "merck", "gsk",
            "glaxosmithkline", "sanofi", "bristol myers squibb", "bms", "abbvie", "abbott",
            "amgen", "gilead", "biogen", "celgene", "takeda", "bayer", "boehringer ingelheim",
            "eli lilly", "lilly", "astrazeneca", "regeneron", "vertex", "alexion", "incyte",
            "illumina", "moderna", "biontech", "catalent", "cro", "quintiles", "iqvia",
            
            # Biotech Companies
            "genentech", "genmab", "seattle genetics", "seagen", "bluebird bio", "crispr therapeutics",
            "editas medicine", "intellia therapeutics", "sangamo therapeutics", "zinc finger",
            "CAR-T", "kite pharma", "juno therapeutics", "novocure", "neurocrine biosciences",
            "sage therapeutics", "alkermes", "acadia pharmaceuticals", "arena pharmaceuticals",
            "biomarin", "ultragenyx", "sarepta therapeutics", "alnylam pharmaceuticals",
            "ionis pharmaceuticals", "antisense", "rna therapeutics", "gene therapy",
            
            # Contract Research Organizations
            "covance", "parexel", "psi", "syneos health", "ppd", "icon", "medpace", "wuxi",
            "charles river laboratories", "labcorp", "quest diagnostics",
            
            # Generic terms that often indicate pharma/biotech
            "pharmaceuticals", "pharmaceutical", "pharma", "biotech", "biotechnology",
            "biopharmaceutical", "biopharmaceuticals", "therapeutics", "medicines",
            "drug development", "clinical research", "medical affairs"
        }
    
    def fetch_all_companies(self, force_refresh: bool = False) -> Set[str]:
        """
        Fetch companies from all sources with intelligent caching.
        
        Args:
            force_refresh: If True, ignore cache and fetch fresh data
            
        Returns:
            Set of pharmaceutical/biotech company names
            
        Raises:
            CompanyDataError: If all API sources fail
        """
        # Check cache first
        if not force_refresh:
            cached_data = self._load_cache()
            if cached_data.companies and self._is_cache_valid(cached_data.last_updated):
                self.logger.info(f"Using cached data with {len(cached_data.companies)} companies")
                return cached_data.companies
        
        self.logger.info("Fetching fresh company data from all API sources")
        
        # Start with hardcoded companies as fallback
        all_companies = self.get_hardcoded_companies()
        initial_count = len(all_companies)
        sources_used = [ApiSource.HARDCODED]
        
        # Fetch from APIs with proper error handling
        api_sources = [
            (self.fetch_from_clinicaltrials_gov, ApiSource.CLINICAL_TRIALS),
            (self.fetch_from_openfda, ApiSource.OPENFDA),
            (self.fetch_from_wikidata, ApiSource.WIKIDATA)
        ]
        
        successful_sources = []
        for fetch_func, source in api_sources:
            try:
                companies = fetch_func()
                all_companies.update(companies)
                sources_used.append(source)
                successful_sources.append(fetch_func.__name__)
                self.logger.debug(f"Total companies after {fetch_func.__name__}: {len(all_companies)}")
            except ApiError as e:
                self.logger.warning(f"Failed to fetch from {source.value}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error in {fetch_func.__name__}: {e}")
        
        if not successful_sources:
            self.logger.warning("All API sources failed, using only hardcoded companies")
        
        # Add variations and clean up
        expanded_companies = self._expand_company_names(all_companies)
        
        self.logger.info(f"Expanded from {initial_count} to {len(expanded_companies)} companies")
        
        # Save to cache
        try:
            self._save_cache(expanded_companies, sources_used)
        except CompanyDataError as e:
            self.logger.warning(f"Failed to save cache: {e}")
        
        return expanded_companies
    
    def _expand_company_names(self, companies: Set[str]) -> Set[str]:
        """
        Expand company names with common variations and abbreviations.
        
        Args:
            companies: Original set of company names
            
        Returns:
            Expanded set with variations
        """
        expanded_companies = set()
        for company in companies:
            expanded_companies.add(company.lower())
            # Add common abbreviations and variations
            if "pharmaceuticals" in company:
                expanded_companies.add(company.replace("pharmaceuticals", "pharma").lower())
            if "biotechnology" in company:
                expanded_companies.add(company.replace("biotechnology", "biotech").lower())
            if "laboratories" in company:
                expanded_companies.add(company.replace("laboratories", "labs").lower())
        
        return expanded_companies

    def clean_and_rebuild_cache(self) -> Set[str]:
        """
        Clean the cache and rebuild with improved filtering.
        
        Returns:
            Set of cleaned company names
            
        Raises:
            CompanyDataError: If cache cannot be rebuilt
        """
        self.logger.info("Cleaning and rebuilding company cache with improved filtering")
        
        # Remove old cache file
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                self.logger.info("Removed old cache file")
            except OSError as e:
                raise CompanyDataError(f"Failed to remove old cache file: {e}") from e
        
        # Fetch fresh data with improved filtering
        companies = self.fetch_all_companies(force_refresh=True)
        
        # Additional cleanup pass with stricter filtering
        cleaned_companies = set()
        for company in companies:
            if self._is_valid_company_name(company):
                cleaned_companies.add(company)
        
        self.logger.info(f"Cleaned {len(companies)} down to {len(cleaned_companies)} companies")
        
        return cleaned_companies
    
    def _is_valid_company_name(self, company: str) -> bool:
        """
        Validate if a company name meets quality criteria.
        
        Args:
            company: Company name to validate
            
        Returns:
            True if the company name is valid
        """
        if len(company) < 3:
            return False
            
        # Exclude random IDs and technical terms
        if re.match(r'^[a-z0-9_\-]{8,}$', company):  # No random IDs
            return False
        if re.search(r'\d{4,}', company):  # No long numbers
            return False
            
        # Must have space or pharmaceutical keywords
        has_space = ' ' in company
        has_keywords = any(keyword in company for keyword in 
                          ['pharma', 'biotech', 'therapeutic', 'lab', 'medicine', 'clinical'])
        
        return has_space or has_keywords


class PubMedPharmaSearch:
    """
    Handles PubMed searches for pharmaceutical/biotech company papers.
    
    This class provides comprehensive functionality to search PubMed for research
    papers and identify those with at least one author affiliated with 
    pharmaceutical or biotech companies.
    """
    
    def __init__(
        self, 
        email: str = "user@example.com", 
        debug: bool = False, 
        use_hardcoded_only: bool = False
    ) -> None:
        """
        Initialize the PubMed pharmaceutical search tool.
        
        Args:
            email: Email address for PubMed API requests
            debug: Enable debug mode for verbose logging
            use_hardcoded_only: Use only hardcoded company list (skip API fetching)
            
        Raises:
            CompanyDataError: If company data cannot be loaded
        """
        Entrez.email = email
        self.debug = debug
        self.logger = get_logger(__name__, debug_mode=debug)
        
        # Initialize company data fetcher
        self.company_fetcher = CompanyDataFetcher(debug=debug)
        
        try:
            if use_hardcoded_only:
                self.pharma_biotech_companies = self.company_fetcher.get_hardcoded_companies()
                self.logger.info(f"Using hardcoded company list with {len(self.pharma_biotech_companies)} companies")
            else:
                self.pharma_biotech_companies = self.company_fetcher.fetch_all_companies()
                self.logger.info(f"Loaded {len(self.pharma_biotech_companies)} pharmaceutical/biotech companies")
        except Exception as e:
            raise CompanyDataError(f"Failed to load company data: {e}") from e
    
    def _debug_print(self, message: str) -> None:
        """
        Print debug information if debug mode is enabled.
        
        Args:
            message: Debug message to print
        """
        self.logger.debug(message)
    
    def update_company_database(self) -> None:
        """
        Force update of the company database from APIs.
        
        Raises:
            CompanyDataError: If company database cannot be updated
        """
        self.logger.info("Forcing company database refresh from all API sources")
        try:
            self.pharma_biotech_companies = self.company_fetcher.fetch_all_companies(force_refresh=True)
            self.logger.info(f"Updated company database with {len(self.pharma_biotech_companies)} companies")
        except Exception as e:
            raise CompanyDataError(f"Failed to update company database: {e}") from e
    
    def get_company_stats(self) -> CompanyStats:
        """
        Get comprehensive statistics about the company database.
        
        Returns:
            Dictionary containing company database statistics
        """
        cached_data = self.company_fetcher._load_cache()
        
        return {
            "total_companies": len(self.pharma_biotech_companies),
            "cache_file": self.company_fetcher.cache_file,
            "sample_companies": list(self.pharma_biotech_companies)[:10],
            "sources_used": [source.value for source in cached_data.sources_used] if cached_data.sources_used else [],
            "last_updated": cached_data.last_updated
        }
    
    def validate_query_syntax(self, query: str) -> QueryAnalysis:
        """
        Validate and analyze PubMed query syntax.
        
        Args:
            query: PubMed query string to validate
            
        Returns:
            QueryAnalysis object containing validation results and component breakdown
            
        Raises:
            QueryValidationError: If query contains critical syntax errors
        """
        analysis: QueryAnalysis = {
            'query': query,
            'valid': True,
            'warnings': [],
            'components': {
                'boolean_operators': [],
                'field_tags': [],
                'phrases': [],
                'wildcards': [],
                'date_filters': [],
                'mesh_terms': []
            }
        }
        
        if not query or not query.strip():
            raise QueryValidationError("Query cannot be empty")
        
        # Find Boolean operators
        boolean_ops = re.findall(r'\b(AND|OR|NOT)\b', query, re.IGNORECASE)
        analysis['components']['boolean_operators'] = boolean_ops
        
        # Find field tags
        field_tags = re.findall(r'\[([^\]]+)\]', query)
        analysis['components']['field_tags'] = field_tags
        
        # Check for valid field tags
        valid_tags = {
            'ti', 'title', 'tiab', 'au', 'author', 'ta', 'journal', 'ad', 'affiliation',
            'mh', 'mesh', 'dp', 'pdat', 'edat', 'epdat', 'ppdat', 'pt', 'ptyp',
            'la', 'lang', 'si', 'uid', 'pmid', 'doi', 'isbn', 'issn', 'vol', 'ip',
            'pg', 'vi', 'is', 'aid', 'lid', 'crdt', 'dcom', 'lr', 'mhda', 'pl',
            'sb', 'so', 'stat', 'da', 'own', 'nlm', 'pmc', 'pmcr', 'pubm'
        }
        
        for tag in field_tags:
            if tag.lower() not in valid_tags:
                analysis['warnings'].append(f"Unknown field tag: [{tag}]")
        
        # Find quoted phrases
        phrases = re.findall(r'"([^"]+)"', query)
        analysis['components']['phrases'] = phrases
        
        # Find wildcards
        wildcards = re.findall(r'\w+\*', query)
        analysis['components']['wildcards'] = wildcards
        
        # Find date filters
        date_patterns = [
            r'\d{4}/\d{2}/\d{2}:\d{4}/\d{2}/\d{2}\[dp\]',  # Date range
            r'\d{4}/\d{2}/\d{2}\[dp\]',  # Single date
            r'\d{4}:\d{4}\[dp\]',  # Year range
            r'last \d+ (days?|months?|years?)\[dp\]'  # Relative dates
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            analysis['components']['date_filters'].extend(matches)
        
        # Find MeSH terms
        mesh_terms = re.findall(r'([^"\[\]]+)\[mh\]', query, re.IGNORECASE)
        analysis['components']['mesh_terms'] = mesh_terms
        
        # Check for balanced parentheses
        if query.count('(') != query.count(')'):
            analysis['valid'] = False
            analysis['warnings'].append("Unbalanced parentheses in query")
        
        # Check for balanced quotes
        if query.count('"') % 2 != 0:
            analysis['warnings'].append("Unbalanced quotes in query")
        
        return analysis
    
    def print_query_help(self) -> None:
        """Print comprehensive PubMed query syntax help."""
        help_text = """
COMPLETE PUBMED QUERY SYNTAX GUIDE

1. BOOLEAN OPERATORS (case-insensitive but uppercase recommended):
   AND  - Both terms must be present
   OR   - Either term can be present  
   NOT  - Exclude the following term
   
   Examples:
   cancer AND chemotherapy
   (aspirin OR ibuprofen) AND headache
   diabetes NOT "type 1"

2. FIELD TAGS - Target specific parts of articles:
   [ti] or [Title]        - Article title only
   [tiab]                 - Title and abstract
   [au] or [Author]       - Author names
   [ta] or [Journal]      - Journal title
   [ad] or [Affiliation]  - Author affiliation
   [mh] or [MeSH]         - Medical Subject Headings
   [dp] or [Date]         - Publication date
   [pt] or [Publication Type] - Article type (review, clinical trial, etc.)
   [la] or [Language]     - Publication language
   [so] or [Source]       - Journal citation info
   
   Examples:
   "gene therapy"[ti]                    - "gene therapy" in title
   smith ja[au]                          - Author named "Smith JA"
   nature[ta]                            - Published in Nature journal
   pfizer[ad]                            - Author affiliated with Pfizer
   COVID-19[mh]                          - MeSH term for COVID-19

3. DATE FILTERING:
   YYYY/MM/DD[dp]                        - Exact date
   YYYY/MM/DD:YYYY/MM/DD[dp]             - Date range
   YYYY:YYYY[dp]                         - Year range
   last N days[dp]                       - Last N days
   last N months[dp]                     - Last N months
   
   Examples:
   2023/05/12[dp]                        - May 12, 2023
   2020/01/01:2023/12/31[dp]             - 2020 to 2023
   2018:2023[dp]                         - Years 2018-2023
   last 6 months[dp]                     - Last 6 months

4. PHRASES AND WILDCARDS:
   "exact phrase"                        - Search for exact phrase
   word*                                 - Wildcard (word, words, wordy, etc.)
   
   Examples:
   "stem cell therapy"                   - Exact phrase
   therap*                               - therapy, therapies, therapeutic, etc.

5. MESH TERMS (Medical Subject Headings):
   term[mh]                              - Standard MeSH term
   term[mh:noexp]                        - Don't include subheadings
   
   Examples:
   "Neoplasms"[mh]                       - Cancer MeSH term
   "Drug Therapy"[mh]                    - Drug treatment MeSH

6. PUBLICATION TYPES:
   "Clinical Trial"[pt]                  - Clinical trials
   "Review"[pt]                          - Review articles
   "Meta-Analysis"[pt]                   - Meta-analyses
   "Case Reports"[pt]                    - Case reports
   
7. COMPLEX QUERY CONSTRUCTION:
   Use parentheses to group terms and control logic order
   Combine multiple field tags and operators
   
   Example Complex Queries:
   
   a) COVID-19 vaccine trials from pharma companies:
   ("COVID-19"[mh] OR "SARS-CoV-2"[mh]) AND vaccine[ti] AND (pfizer[ad] OR moderna[ad] OR "johnson & johnson"[ad]) AND "clinical trial"[pt]
   
   b) Recent AI in drug discovery:
   ("artificial intelligence"[tiab] OR "machine learning"[tiab]) AND "drug discovery"[tiab] AND 2020:2025[dp]
   
   c) Cancer immunotherapy with pharma involvement:
   (cancer[mh] OR tumor[tiab]) AND immunotherapy[tiab] AND (pharma*[ad] OR biotech*[ad]) AND last 5 years[dp]

8. TIPS FOR EFFECTIVE SEARCHING:
   - Use quotes for exact phrases
   - Combine broad and specific terms
   - Use field tags to focus searches
   - Include date ranges for recent research
   - Use wildcards for variant spellings
   - Check MeSH database for standard terms
   - Start broad, then narrow with additional terms

9. SPECIAL CHARACTERS:
   - Use quotes around phrases with spaces
   - Escape special characters if needed
   - Be careful with punctuation in company names

10. EXAMPLE COMMANDS:
    python pubmed_pharma_search.py "cancer drug discovery"
    python pubmed_pharma_search.py "CRISPR therapeutics" -f results.csv -d
    python pubmed_pharma_search.py "COVID-19[MeSH] AND vaccine" -f covid_pharma.csv
    python pubmed_pharma_search.py "(cancer[ti] OR tumor[ti]) AND drug discovery[tiab]" -f cancer_drugs.csv

For more information, visit: https://pubmed.ncbi.nlm.nih.gov/help/
        """
        print(help_text)
    
    def _is_pharma_biotech_affiliation(self, affiliation: str) -> Optional[str]:
        """Check if an affiliation contains pharmaceutical or biotech company."""
        if not affiliation:
            return None
            
        affiliation_lower = affiliation.lower()
        
        # Check against known companies
        best_match = None
        longest_match_len = 0
        
        for company in self.pharma_biotech_companies:
            if company in affiliation_lower:
                # Find the longest matching company name for better accuracy
                if len(company) > longest_match_len:
                    longest_match_len = len(company)
                    
                    # Extract a cleaner company name from the affiliation
                    words = affiliation.split()
                    company_words = []
                    
                    # Find the position of the matched company term
                    for i, word in enumerate(words):
                        word_clean = re.sub(r'[^\w\s]', '', word.lower())
                        if company.lower() in word_clean or word_clean in company.lower():
                            # Include surrounding words that might be part of the company name
                            start_idx = max(0, i-1)
                            end_idx = min(len(words), i+4)
                            potential_company = words[start_idx:end_idx]
                            
                            # Clean up the extracted company name
                            company_name = " ".join(potential_company)
                            # Remove common institutional suffixes/prefixes that aren't part of company name
                            company_name = re.sub(r'^(Department of|School of|Division of|Faculty of|Institute of|Center for|Centre for)', '', company_name, flags=re.IGNORECASE)
                            company_name = re.sub(r'(University|College|Hospital|Medical Center|Research Center).*$', '', company_name, flags=re.IGNORECASE)
                            company_name = company_name.strip(" .,;:-")
                            
                            if company_name:
                                best_match = company_name
                            break
                    
                    # If we couldn't extract a good company name, use the original match
                    if not best_match:
                        # Capitalize the company name properly
                        best_match = ' '.join(word.capitalize() for word in company.split())
        
        return best_match
    
    def search_pubmed(self, query: str, max_results: int = 100) -> List[str]:
        """Search PubMed and return list of PMIDs."""
        self._debug_print(f"Searching PubMed with query: {query}")
        
        try:
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="relevance"
            )
            search_results = Entrez.read(handle)
            handle.close()
            
            pmids = search_results["IdList"]
            self._debug_print(f"Found {len(pmids)} papers")
            return pmids
            
        except Exception as e:
            print(f"Error searching PubMed: {e}")
            return []
    
    def fetch_paper_details(self, pmids: List[str]) -> List[Dict]:
        """Fetch detailed information for a list of PMIDs."""
        if not pmids:
            return []
        
        self._debug_print(f"Fetching details for {len(pmids)} papers")
        papers = []
        
        # Process PMIDs in batches to avoid overwhelming the API
        batch_size = BATCH_SIZE
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            self._debug_print(f"Processing batch {i//batch_size + 1}/{(len(pmids)-1)//batch_size + 1}")
            
            try:
                # Fetch paper details
                handle = Entrez.efetch(
                    db="pubmed",
                    id=",".join(batch_pmids),
                    rettype="medline",
                    retmode="xml"
                )
                
                records = Entrez.read(handle)
                handle.close()
                
                for record in records['PubmedArticle']:
                    paper_info = self._parse_paper_record(record)
                    if paper_info and paper_info['non_academic_authors']:
                        papers.append(paper_info)
                
                # Be respectful to the API
                time.sleep(API_DELAY)
                
            except Exception as e:
                self._debug_print(f"Error fetching batch: {e}")
                continue
        
        return papers
    
    def _parse_paper_record(self, record) -> Optional[Dict]:
        """Parse a PubMed record and extract relevant information."""
        try:
            medline_citation = record['MedlineCitation']
            article = medline_citation['Article']
            
            # Extract basic information
            pmid = str(medline_citation['PMID'])
            title = str(article.get('ArticleTitle', ''))
            
            # Extract publication date
            pub_date = self._extract_publication_date(article)
            
            # Extract author information
            authors_info = self._extract_author_info(article)
            
            # Check if any authors are from pharma/biotech companies
            non_academic_authors = []
            company_affiliations = []
            
            for author_info in authors_info:
                if author_info['affiliation']:
                    company = self._is_pharma_biotech_affiliation(author_info['affiliation'])
                    if company:
                        # Clean up author name
                        author_name = author_info['name'].strip()
                        if author_name and author_name not in non_academic_authors:
                            non_academic_authors.append(author_name)
                        
                        # Clean up company name and avoid duplicates
                        company_clean = company.strip()
                        if company_clean and company_clean not in company_affiliations:
                            company_affiliations.append(company_clean)
            
            # Only return papers with pharma/biotech authors
            if not non_academic_authors:
                return None
            
            # Extract corresponding author email
            corresponding_email = self._extract_corresponding_author_email(authors_info)
            
            # Clean up the title
            title_clean = title.strip().replace('\n', ' ').replace('\r', ' ')
            title_clean = ' '.join(title_clean.split())  # Remove extra whitespace
            
            return {
                'pmid': pmid,
                'title': title_clean,
                'publication_date': pub_date,
                'non_academic_authors': "; ".join(non_academic_authors),
                'company_affiliations': "; ".join(company_affiliations),
                'corresponding_author_email': corresponding_email.strip() if corresponding_email else ''
            }
            
        except Exception as e:
            self._debug_print(f"Error parsing record: {e}")
            return None
    
    def _extract_publication_date(self, article) -> str:
        """Extract publication date from article."""
        try:
            # Try journal publication date first
            if 'Journal' in article and 'JournalIssue' in article['Journal']:
                journal_issue = article['Journal']['JournalIssue']
                if 'PubDate' in journal_issue:
                    pub_date = journal_issue['PubDate']
                    year = pub_date.get('Year', '')
                    month = pub_date.get('Month', '')
                    day = pub_date.get('Day', '')
                    
                    if year:
                        date_str = year
                        if month:
                            date_str += f"-{month}"
                            if day:
                                date_str += f"-{day}"
                        return date_str
            
            # Fallback to article date
            if 'ArticleDate' in article and article['ArticleDate']:
                article_date = article['ArticleDate'][0]
                year = article_date.get('Year', '')
                month = article_date.get('Month', '')
                day = article_date.get('Day', '')
                
                if year:
                    date_str = year
                    if month:
                        date_str += f"-{month.zfill(2)}"
                        if day:
                            date_str += f"-{day.zfill(2)}"
                    return date_str
            
            return "Unknown"
            
        except Exception as e:
            self._debug_print(f"Error extracting publication date: {e}")
            return "Unknown"
    
    def _extract_author_info(self, article) -> List[Dict]:
        """Extract author information including names and affiliations."""
        authors_info = []
        
        try:
            if 'AuthorList' not in article:
                return authors_info
            
            for author in article['AuthorList']:
                name = ""
                affiliation = ""
                
                # Extract author name with proper formatting
                if 'LastName' in author and 'ForeName' in author:
                    first_name = str(author['ForeName']).strip()
                    last_name = str(author['LastName']).strip()
                    name = f"{first_name} {last_name}"
                elif 'LastName' in author:
                    name = str(author['LastName']).strip()
                elif 'CollectiveName' in author:
                    name = str(author['CollectiveName']).strip()
                
                # Extract affiliation with cleaning
                if 'AffiliationInfo' in author:
                    affiliations = []
                    for aff_info in author['AffiliationInfo']:
                        if 'Affiliation' in aff_info:
                            aff_text = str(aff_info['Affiliation']).strip()
                            # Clean up affiliation text
                            aff_text = aff_text.replace('\n', ' ').replace('\r', ' ')
                            aff_text = ' '.join(aff_text.split())  # Remove extra whitespace
                            if aff_text:
                                affiliations.append(aff_text)
                    affiliation = "; ".join(affiliations)
                
                # Only add authors with names
                if name:
                    authors_info.append({
                        'name': name,
                        'affiliation': affiliation
                    })
            
        except Exception as e:
            self._debug_print(f"Error extracting author info: {e}")
        
        return authors_info
    
    def _extract_corresponding_author_email(self, authors_info: List[Dict]) -> Optional[str]:
        """Extract corresponding author email from affiliations."""
        for author_info in authors_info:
            affiliation = author_info.get('affiliation', '')
            if affiliation:
                # Look for email patterns
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                emails = re.findall(email_pattern, affiliation)
                if emails:
                    return emails[0]
        return None
    
    def save_to_csv(self, papers: List[Dict], filename: str):
        """Save papers to CSV file with proper formatting."""
        self._debug_print(f"Saving {len(papers)} papers to {filename}")
        
        fieldnames = [
            'PubmedID', 'Title', 'Publication Date', 
            'Non-academic Author(s)', 'Company Affiliation(s)', 
            'Corresponding Author Email'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for paper in papers:
                # Clean and format the data
                title = paper['title'].strip().replace('\n', ' ').replace('\r', ' ')
                # Remove extra whitespace
                title = ' '.join(title.split())
                
                non_academic_authors = paper['non_academic_authors'].strip()
                company_affiliations = paper['company_affiliations'].strip()
                corresponding_email = paper['corresponding_author_email'].strip()
                
                writer.writerow({
                    'PubmedID': paper['pmid'],
                    'Title': title,
                    'Publication Date': paper['publication_date'],
                    'Non-academic Author(s)': non_academic_authors,
                    'Company Affiliation(s)': company_affiliations,
                    'Corresponding Author Email': corresponding_email
                })
    
    def print_to_console(self, papers: List[Dict]):
        """Print papers to console in CSV format with proper formatting."""
        if not papers:
            print("No papers found with pharmaceutical/biotech company affiliations.")
            return
        
        fieldnames = [
            'PubmedID', 'Title', 'Publication Date', 
            'Non-academic Author(s)', 'Company Affiliation(s)', 
            'Corresponding Author Email'
        ]
        
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        for paper in papers:
            # Clean and format the data
            title = paper['title'].strip().replace('\n', ' ').replace('\r', ' ')
            # Remove extra whitespace
            title = ' '.join(title.split())
            
            non_academic_authors = paper['non_academic_authors'].strip()
            company_affiliations = paper['company_affiliations'].strip()
            corresponding_email = paper['corresponding_author_email'].strip()
            
            writer.writerow({
                'PubmedID': paper['pmid'],
                'Title': title,
                'Publication Date': paper['publication_date'],
                'Non-academic Author(s)': non_academic_authors,
                'Company Affiliation(s)': company_affiliations,
                'Corresponding Author Email': corresponding_email
            })


def main():
    """Main function to handle command-line interface."""
    parser = argparse.ArgumentParser(
        description="Search PubMed for papers with pharmaceutical/biotech company affiliations using full PubMed query syntax",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PUBMED QUERY SYNTAX - ALL FEATURES SUPPORTED:

🔹 Boolean Operators:
  cancer AND chemotherapy
  (aspirin OR ibuprofen) AND headache
  diabetes NOT "type 1"

🔹 Field Tags:
  [ti] or [Title]        - Title only
  [tiab]                 - Title/Abstract
  [au]                   - Author
  [ta]                   - Journal Title
  [ad]                   - Affiliation
  [mh]                   - MeSH terms
  [dp]                   - Publication Date
  [pt]                   - Publication Type

🔹 Date Filtering:
  2023/05/12[dp]         - Exact date
  2018/01:2019/12[dp]    - Date range
  last 6 months[dp]      - Relative date

🔹 Phrase & Wildcards:
  "stem cell therapy"    - Exact phrase
  therap*                - Wildcard (therapy, therapies, etc.)

🔹 Advanced Examples:
  python pubmed_pharma_search.py "cancer drug discovery"
  
  python pubmed_pharma_search.py "CRISPR therapeutics" -f results.csv -d
  
  python pubmed_pharma_search.py "COVID-19[MeSH] AND vaccine" -f covid_pharma.csv
  
  python pubmed_pharma_search.py "(cancer[ti] OR tumor[ti]) AND drug discovery[tiab]" -f cancer_drugs.csv
  
  python pubmed_pharma_search.py "immunotherapy[mh] AND (pfizer[ad] OR moderna[ad])" -f immuno_pharma.csv
  
  python pubmed_pharma_search.py '"artificial intelligence"[tiab] AND "drug discovery"[tiab] AND 2020:2025[dp]' -f ai_drugs.csv
  
  python pubmed_pharma_search.py "(COVID-19[mh] OR SARS-CoV-2[mh]) AND vaccine[ti] AND clinical trial[pt]" -f covid_trials.csv
  
  python pubmed_pharma_search.py "alzheimer*[tiab] AND therap*[tiab] AND pharma*[ad]" -f alzheimer_pharma.csv

🔹 Complex Query Example:
  '("COVID-19"[mh] OR "COVID-19 vaccine"[tiab]) AND (pfizer[ad] OR moderna[ad]) AND "clinical trial"[pt] AND 2023:2025[dp]'
        """
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        help='PubMed search query (supports full PubMed syntax)'
    )
    
    parser.add_argument(
        '-f', '--file',
        help='Filename to save results (if not provided, prints to console)'
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Print debug information during execution'
    )
    
    parser.add_argument(
        '--max-results',
        type=int,
        default=100,
        help='Maximum number of papers to retrieve (default: 100)'
    )
    
    parser.add_argument(
        '--email',
        default='user@example.com',
        help='Email address for PubMed API (default: user@example.com)'
    )
    
    parser.add_argument(
        '--validate-query',
        action='store_true',
        help='Validate the query syntax and show query breakdown without executing search'
    )
    
    parser.add_argument(
        '--query-help',
        action='store_true',
        help='Show detailed PubMed query syntax help and exit'
    )
    
    parser.add_argument(
        '--update-companies',
        action='store_true',
        help='Force update of pharmaceutical/biotech company database from APIs'
    )
    
    parser.add_argument(
        '--show-company-stats',
        action='store_true',
        help='Show statistics about the company database and exit'
    )
    
    parser.add_argument(
        '--use-hardcoded-only',
        action='store_true',
        help='Use only hardcoded company list (skip API fetching)'
    )
    
    parser.add_argument(
        '--clean-company-cache',
        action='store_true',
        help='Clean and rebuild company cache with improved filtering'
    )
    
    args = parser.parse_args()
    
    # Handle special help option
    if args.query_help:
        searcher = PubMedPharmaSearch(debug=False)
        searcher.print_query_help()
        return
    
    # Handle company database options
    if args.show_company_stats:
        searcher = PubMedPharmaSearch(email=args.email, debug=args.debug, 
                                    use_hardcoded_only=args.use_hardcoded_only)
        stats = searcher.get_company_stats()
        print("\nPHARMACEUTICAL/BIOTECH COMPANY DATABASE STATISTICS")
        print("="*60)
        print(f"Total companies in database: {stats['total_companies']:,}")
        print(f"Cache file location: {stats['cache_file']}")
        print(f"Data sources: {'Hardcoded only' if args.use_hardcoded_only else 'APIs + Hardcoded fallback'}")
        print(f"\nSample companies (first 10):")
        for i, company in enumerate(stats['sample_companies'][:10], 1):
            print(f"  {i:2d}. {company}")
        print(f"\n Use --update-companies to refresh from APIs")
        return
    
    if args.update_companies:
        searcher = PubMedPharmaSearch(email=args.email, debug=args.debug, 
                                    use_hardcoded_only=args.use_hardcoded_only)
        print(" Updating pharmaceutical/biotech company database...")
        searcher.update_company_database()
        stats = searcher.get_company_stats()
        print(f" Updated! Now tracking {stats['total_companies']:,} companies")
        return
    
    if args.clean_company_cache:
        searcher = PubMedPharmaSearch(email=args.email, debug=args.debug, 
                                    use_hardcoded_only=args.use_hardcoded_only)
        print(" Cleaning and rebuilding company cache...")
        searcher.company_fetcher.clean_and_rebuild_cache()
        print(" Cache rebuilt!")
        return
    
    # Check if query is provided when needed
    if not args.query and not args.query_help and not args.show_company_stats and not args.update_companies and not args.clean_company_cache:
        parser.error("Query is required unless using --query-help, --show-company-stats, --update-companies, or --clean-company-cache")
    
    # Initialize the search tool
    searcher = PubMedPharmaSearch(email=args.email, debug=args.debug, 
                                use_hardcoded_only=args.use_hardcoded_only)
    
    # Handle query validation
    if args.validate_query:
        if not args.query:
            parser.error("Query is required for validation")
        try:
            analysis = searcher.validate_query_syntax(args.query)
            print(f"\n QUERY ANALYSIS FOR: {args.query}\n")
            print(f"Valid syntax: {'YES' if analysis['valid'] else ' NO'}")
            
            if analysis['warnings']:
                print(f"\n Warnings:")
                for warning in analysis['warnings']:
                    print(f"  - {warning}")
            
            print(f"\n Query Components:")
            components = analysis['components']
            
            if components['boolean_operators']:
                print(f"  Boolean operators: {', '.join(components['boolean_operators'])}")
            
            if components['field_tags']:
                print(f"  Field tags: {', '.join([f'[{tag}]' for tag in components['field_tags']])}")
            
            if components['phrases']:
                phrases_str = ', '.join(['"' + phrase + '"' for phrase in components['phrases']])
                print(f"  Quoted phrases: {phrases_str}")
            
            if components['wildcards']:
                print(f"  Wildcards: {', '.join(components['wildcards'])}")
            
            if components['date_filters']:
                print(f"  Date filters: {', '.join(components['date_filters'])}")
            
            if components['mesh_terms']:
                print(f"  MeSH terms: {', '.join(components['mesh_terms'])}")
            
            if not any(components.values()):
                print("  Simple keyword search (no advanced syntax detected)")
            
            print(f"\n This query will be processed by PubMed's search engine.")
        except QueryValidationError as e:
            print(f"\n Query validation failed: {e}")
            sys.exit(1)
        return
    
    try:
        # Search PubMed
        pmids = searcher.search_pubmed(args.query, args.max_results)
        
        if not pmids:
            print("No papers found for the given query.")
            return
        
        # Fetch paper details
        papers = searcher.fetch_paper_details(pmids)
        
        if not papers:
            print("No papers found with pharmaceutical/biotech company affiliations.")
            return
        
        # Output results
        if args.file:
            searcher.save_to_csv(papers, args.file)
            print(f"Results saved to {args.file}")
            print(f"Found {len(papers)} papers with pharmaceutical/biotech affiliations.")
        else:
            searcher.print_to_console(papers)
            if args.debug:
                print(f"\nFound {len(papers)} papers with pharmaceutical/biotech affiliations.", file=sys.stderr)
        
    except KeyboardInterrupt:
        print("\nSearch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 