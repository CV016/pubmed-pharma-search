"""
Data models and type definitions for the PubMed pharmaceutical search tool.

This module contains all data structures, type aliases, and model classes
used throughout the application for better type safety and organization.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Union, TypedDict


class ApiSource(Enum):
    """Enumeration of available API sources for company data."""
    CLINICAL_TRIALS = "clinicaltrials.gov"
    OPENFDA = "openfda.gov"
    WIKIDATA = "wikidata.org"
    HARDCODED = "hardcoded"


class QueryComponentType(Enum):
    """Types of query components that can be analyzed."""
    BOOLEAN_OPERATORS = "boolean_operators"
    FIELD_TAGS = "field_tags"
    PHRASES = "phrases"
    WILDCARDS = "wildcards"
    DATE_FILTERS = "date_filters"
    MESH_TERMS = "mesh_terms"


@dataclass(frozen=True)
class AuthorInfo:
    """Information about a paper author."""
    name: str
    affiliation: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class PaperInfo:
    """Information about a research paper."""
    pmid: str
    title: str
    publication_date: str
    non_academic_authors: List[str]
    company_affiliations: List[str]
    corresponding_author_email: Optional[str] = None


@dataclass
class CompanyCacheData:
    """Structure for cached company data."""
    companies: Set[str]
    last_updated: Optional[str] = None
    sources_used: List[ApiSource] = None
    
    def __post_init__(self) -> None:
        """Initialize sources_used if not provided."""
        if self.sources_used is None:
            self.sources_used = []


class QueryAnalysis(TypedDict):
    """Type definition for query analysis results."""
    query: str
    valid: bool
    warnings: List[str]
    components: Dict[str, List[str]]


class CompanyStats(TypedDict):
    """Type definition for company database statistics."""
    total_companies: int
    cache_file: str
    sample_companies: List[str]
    sources_used: List[str]
    last_updated: Optional[str]


class SearchConfig(TypedDict, total=False):
    """Configuration for PubMed searches."""
    email: str
    debug: bool
    max_results: int
    use_hardcoded_only: bool


class ApiError(Exception):
    """Base exception for API-related errors."""
    
    def __init__(self, message: str, source: Optional[ApiSource] = None) -> None:
        """
        Initialize API error.
        
        Args:
            message: Error message
            source: API source that caused the error
        """
        super().__init__(message)
        self.source = source


class QueryValidationError(Exception):
    """Exception raised for invalid PubMed queries."""
    pass


class CompanyDataError(Exception):
    """Exception raised for company data processing errors."""
    pass 