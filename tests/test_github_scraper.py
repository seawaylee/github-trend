import pytest
from unittest.mock import Mock
from src.github_scraper import GitHubScraper, TrendingProject


def test_parse_stars():
    """Test parsing star count from various formats"""
    scraper = GitHubScraper()

    assert scraper._parse_stars("1,234") == 1234
    assert scraper._parse_stars("12,345") == 12345
    assert scraper._parse_stars("123") == 123
    assert scraper._parse_stars("1.2k") == 1200
    assert scraper._parse_stars("12.3k") == 12300


def test_parse_stars_growth():
    """Test parsing stars growth"""
    scraper = GitHubScraper()

    assert scraper._parse_stars_growth("123 stars today") == 123
    assert scraper._parse_stars_growth("1,234 stars today") == 1234
    assert scraper._parse_stars_growth("12 stars this week") == 12


def test_fetch_trending_uses_configured_timeout():
    """GitHub scraper should respect configured request timeout."""
    scraper = GitHubScraper(request_timeout=75)
    response = Mock()
    response.raise_for_status.return_value = None
    response.text = "<html></html>"
    scraper.session.get = Mock(return_value=response)

    scraper.fetch_trending("daily")

    scraper.session.get.assert_called_once_with(
        "https://github.com/trending?since=daily",
        timeout=75,
    )
