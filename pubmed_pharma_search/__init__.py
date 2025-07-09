"""
PubMed Pharmaceutical/Biotech Paper Search Tool

A professional Python module for searching PubMed papers and identifying those with
pharmaceutical or biotech company affiliations. Provides comprehensive
API-based company data fetching, query validation, and result processing
with full type safety and error handling.

This module can be used programmatically or via the command-line interface.
"""

from .core import PubMedPharmaSearch, CompanyDataFetcher
from .models import (
    ApiSource, AuthorInfo, PaperInfo, CompanyCacheData, QueryAnalysis,
    CompanyStats, SearchConfig, ApiError, QueryValidationError, CompanyDataError
)
from .logging_config import get_logger

__version__ = "1.0.0"
__author__ = "PubMed Pharmaceutical Search Project"

__all__ = [
    "PubMedPharmaSearch",
    "CompanyDataFetcher", 
    "ApiSource",
    "AuthorInfo",
    "PaperInfo",
    "CompanyCacheData",
    "QueryAnalysis",
    "CompanyStats",
    "SearchConfig",
    "ApiError",
    "QueryValidationError", 
    "CompanyDataError",
    "get_logger"
] 