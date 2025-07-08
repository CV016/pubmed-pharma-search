#!/usr/bin/env python3
"""
Main entry point for the PubMed Pharmaceutical Search Tool.

This module provides the command-line interface for the get-papers-list command.
"""

import sys
from .core import main as core_main


def main():
    """Main entry point for the get-papers-list command."""
    try:
        core_main()
    except KeyboardInterrupt:
        print("\nSearch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 