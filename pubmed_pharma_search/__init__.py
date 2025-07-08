"""
PubMed Pharmaceutical/Biotech Paper Search Tool

A Python tool to search PubMed for research papers and identify those with
at least one author affiliated with pharmaceutical or biotech companies.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core import PubMedPharmaSearch, CompanyDataFetcher

__all__ = ["PubMedPharmaSearch", "CompanyDataFetcher"] 