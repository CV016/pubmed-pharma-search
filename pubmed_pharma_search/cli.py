#!/usr/bin/env python3
"""
Command-line interface for the PubMed Pharmaceutical Search Tool.

This script provides a command-line interface that uses the pubmed_pharma_search
module to search PubMed for papers with pharmaceutical/biotech company affiliations.
"""

import argparse
import sys
from typing import NoReturn, Optional

from pubmed_pharma_search import (
    PubMedPharmaSearch,
    ApiError,
    CompanyDataError,
    QueryValidationError,
    get_logger
)


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='Search PubMed for papers with pharmaceutical/biotech company affiliations using full PubMed query syntax',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PUBMED QUERY SYNTAX - ALL FEATURES SUPPORTED:
Boolean Operators:
  cancer AND chemotherapy
  (aspirin OR ibuprofen) AND headache
  diabetes NOT "type 1"

Field Tags:
  [ti] or [Title]        - Title only
  [tiab]                 - Title/Abstract
  [au]                   - Author
  [ta]                   - Journal Title
  [ad]                   - Affiliation
  [mh]                   - MeSH terms
  [dp]                   - Publication Date
  [pt]                   - Publication Type

Date Filtering:
  2023/05/12[dp]         - Exact date
  2018/01:2019/12[dp]    - Date range
  last 6 months[dp]      - Relative date

Phrase & Wildcards:
  "stem cell therapy"    - Exact phrase
  therap*                - Wildcard (therapy, therapies, etc.)

Advanced Examples:
  pubmed-pharma-search "cancer drug discovery"
  pubmed-pharma-search "CRISPR therapeutics" -f results.csv -d
  pubmed-pharma-search "COVID-19[MeSH] AND vaccine" -f covid_pharma.csv
  pubmed-pharma-search "(cancer[ti] OR tumor[ti]) AND drug discovery[tiab]" -f cancer_drugs.csv
  pubmed-pharma-search "immunotherapy[mh] AND (pfizer[ad] OR moderna[ad])" -f immuno_pharma.csv
  pubmed-pharma-search '"artificial intelligence"[tiab] AND "drug discovery"[tiab] AND 2020:2025[dp]' -f ai_drugs.csv

Complex Query Example:
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
    
    return parser


def handle_company_stats(searcher: PubMedPharmaSearch) -> None:
    """
    Display company database statistics.
    
    Args:
        searcher: PubMedPharmaSearch instance
    """
    stats = searcher.get_company_stats()
    
    print("PHARMACEUTICAL/BIOTECH COMPANY DATABASE STATISTICS")
    print("=" * 60)
    print(f"Total companies in database: {stats['total_companies']}")
    print(f"Cache file location: {stats['cache_file']}")
    print(f"Data sources: {', '.join(stats['sources_used']) if stats['sources_used'] else 'Unknown'}")
    if stats['last_updated']:
        print(f"Last updated: {stats['last_updated']}")
    
    print("Sample companies (first 10):")
    for i, company in enumerate(stats['sample_companies'], 1):
        print(f"   {i:2d}. {company}")
    
    print("Use --update-companies to refresh from APIs")


def handle_query_validation(searcher: PubMedPharmaSearch, query: str) -> None:
    """
    Validate and display query analysis.
    
    Args:
        searcher: PubMedPharmaSearch instance
        query: Query string to validate
        
    Raises:
        QueryValidationError: If query validation fails
    """
    try:
        analysis = searcher.validate_query_syntax(query)
        
        print(f"\nQUERY ANALYSIS FOR: {query}\n")
        print(f"Query Status: {'VALID' if analysis['valid'] else 'INVALID'}")
        
        if analysis['warnings']:
            print(f"\nWarnings ({len(analysis['warnings'])}):")
            for warning in analysis['warnings']:
                print(f"  - {warning}")
        
        print(f"\nQuery Components:")
        for component, items in analysis['components'].items():
            if items:
                print(f"  {component.replace('_', ' ').title()}: {items}")
        
        if not any(analysis['components'].values()):
            print("  No specific components detected (simple search)")
        
        print(f"\nThis query will be processed by PubMed's search engine.")
        
    except QueryValidationError as e:
        print(f"\nQuery validation failed: {e}")
        sys.exit(1)


def error_exit(message: str, exit_code: int = 1) -> NoReturn:
    """
    Print an error message and exit with the specified code.
    
    Args:
        message: Error message to display
        exit_code: Exit code (default: 1)
    """
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(exit_code)


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set up logging
    logger = get_logger(__name__, debug_mode=args.debug)
    
    try:
        # Handle help options
        if args.query_help:
            searcher = PubMedPharmaSearch(debug=args.debug)
            searcher.print_query_help()
            return
        
        # Initialize searcher
        logger.info("Initializing PubMed pharmaceutical search tool")
        searcher = PubMedPharmaSearch(
            email=args.email,
            debug=args.debug,
            use_hardcoded_only=args.use_hardcoded_only
        )
        
        # Handle various operations
        if args.clean_company_cache:
            logger.info("Cleaning and rebuilding company cache")
            cleaned_companies = searcher.company_fetcher.clean_and_rebuild_cache()
            print(f"Cache rebuilt with {len(cleaned_companies)} companies")
            return
        
        if args.update_companies:
            logger.info("Updating pharmaceutical/biotech company database")
            searcher.update_company_database()
            stats = searcher.get_company_stats()
            print(f"Updated! Now tracking {stats['total_companies']} companies")
            return
        
        if args.show_company_stats:
            handle_company_stats(searcher)
            return
        
        if args.validate_query:
            if not args.query:
                error_exit("Query is required for validation")
            handle_query_validation(searcher, args.query)
            return
        
        # Main search operation
        if not args.query:
            error_exit("Query is required for search. Use --help for more information.")
        
        logger.info(f"Starting PubMed search with query: {args.query}")
        
        # Search PubMed
        pmids = searcher.search_pubmed(args.query, args.max_results)
        if not pmids:
            print("No papers found for the given query.")
            return
        
        # Fetch paper details
        papers = searcher.fetch_paper_details(pmids)
        if not papers:
            print("No papers with pharmaceutical/biotech affiliations found.")
            return
        
        # Output results
        if args.file:
            searcher.save_to_csv(papers, args.file)
            print(f"Results saved to {args.file}")
        else:
            searcher.print_to_console(papers)
        
        print(f"Found {len(papers)} papers with pharmaceutical/biotech affiliations.")
        
    except (CompanyDataError, QueryValidationError, ApiError) as e:
        error_exit(str(e))
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.debug:
            raise
        error_exit(f"Unexpected error occurred: {e}")


if __name__ == "__main__":
    main() 