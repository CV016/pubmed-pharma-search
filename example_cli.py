#!/usr/bin/env python3
"""
Example standalone CLI script using the pubmed_pharma_search module.

This script demonstrates how to use the pubmed_pharma_search module
from external code. Install the module first with:
pip install pubmed-pharma-search

Then run this script:
python example_cli.py "your PubMed query here"
"""

import argparse
import sys
from typing import Optional

try:
    from pubmed_pharma_search import (
        PubMedPharmaSearch,
        ApiError,
        CompanyDataError,
        QueryValidationError,
        get_logger
    )
except ImportError:
    print("ERROR: pubmed_pharma_search module not found.")
    print("Install it with: pip install pubmed-pharma-search")
    sys.exit(1)


def main() -> None:
    """
    Example main function showing how to use the pubmed_pharma_search module.
    """
    parser = argparse.ArgumentParser(
        description='Example usage of pubmed_pharma_search module'
    )
    parser.add_argument('query', help='PubMed search query')
    parser.add_argument('-f', '--file', help='Output CSV file')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
    parser.add_argument('--max-results', type=int, default=50, help='Max results')
    
    args = parser.parse_args()
    
    # Set up logging
    logger = get_logger(__name__, debug_mode=args.debug)
    
    try:
        # Initialize the search tool
        logger.info("Initializing PubMed pharmaceutical search")
        searcher = PubMedPharmaSearch(
            email="your.email@example.com",  # Replace with your email
            debug=args.debug
        )
        
        # Validate query (optional)
        logger.info("Validating query syntax")
        analysis = searcher.validate_query_syntax(args.query)
        if not analysis['valid']:
            print(f"WARNING: Query may have syntax issues: {analysis['warnings']}")
        
        # Search PubMed
        logger.info(f"Searching PubMed: {args.query}")
        pmids = searcher.search_pubmed(args.query, args.max_results)
        
        if not pmids:
            print("No papers found for your query.")
            return
        
        print(f"Found {len(pmids)} papers, analyzing for pharma/biotech affiliations...")
        
        # Fetch paper details and filter for pharma/biotech
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
        
        print(f"\nSummary: Found {len(papers)} papers with pharmaceutical/biotech affiliations")
        
        # Show company stats
        stats = searcher.get_company_stats()
        print(f"Company database contains {stats['total_companies']} companies")
        
    except (CompanyDataError, QueryValidationError, ApiError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main() 