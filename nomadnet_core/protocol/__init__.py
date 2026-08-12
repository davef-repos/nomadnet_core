"""
Protocol layer for nomadnet-core.

Provides UI-agnostic implementations of:
- page_fetcher: Page/file fetching from NomadNet nodes
- micron_parser (planned): Pure micron/markup parsing
"""

from .page_fetcher import PageFetcher
