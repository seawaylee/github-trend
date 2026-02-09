"""GitHub trending scraper module"""
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional
import logging
import time


logger = logging.getLogger(__name__)


@dataclass
class TrendingProject:
    """Trending project data"""
    repo_name: str
    description: str
    language: str
    url: str
    stars: int
    stars_growth: int
    ranking: int


class GitHubScraper:
    """GitHub trending page scraper"""

    BASE_URL = "https://github.com/trending"

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize scraper

        Args:
            github_token: Optional GitHub token for API calls
        """
        self.github_token = github_token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def fetch_trending(self, since: str = "daily") -> List[TrendingProject]:
        """
        Fetch trending repositories

        Args:
            since: Time range - 'daily' or 'weekly'

        Returns:
            List of trending projects
        """
        url = f"{self.BASE_URL}?since={since}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            projects = []

            # Find all repository articles
            articles = soup.find_all('article', class_='Box-row')

            for idx, article in enumerate(articles, 1):
                try:
                    project = self._parse_article(article, idx)
                    if project:
                        projects.append(project)
                except Exception as e:
                    logger.warning(f"Failed to parse article {idx}: {e}")
                    continue

            logger.info(f"Scraped {len(projects)} {since} trending projects")
            return projects

        except requests.RequestException as e:
            logger.error(f"Failed to fetch trending page: {e}")
            return []

    def _parse_article(self, article: BeautifulSoup, ranking: int) -> Optional[TrendingProject]:
        """Parse a single trending article"""

        # Extract repository name and URL
        h2 = article.find('h2', class_='h3')
        if not h2:
            return None

        link = h2.find('a')
        if not link:
            return None

        repo_name = link['href'].strip('/')
        url = f"https://github.com{link['href']}"

        # Extract description
        description_elem = article.find('p', class_='col-9')
        description = description_elem.get_text(strip=True) if description_elem else ""

        # Extract language
        language_elem = article.find('span', itemprop='programmingLanguage')
        language = language_elem.get_text(strip=True) if language_elem else "Unknown"

        # Extract stars and stars growth
        stars_elem = article.find('svg', class_='octicon-star')
        stars = 0
        if stars_elem and stars_elem.parent:
            stars_text = stars_elem.parent.get_text(strip=True)
            stars = self._parse_stars(stars_text)

        # Extract stars growth
        growth_elem = article.find('span', class_='d-inline-block float-sm-right')
        stars_growth = 0
        if growth_elem:
            growth_text = growth_elem.get_text(strip=True)
            stars_growth = self._parse_stars_growth(growth_text)

        return TrendingProject(
            repo_name=repo_name,
            description=description,
            language=language,
            url=url,
            stars=stars,
            stars_growth=stars_growth,
            ranking=ranking
        )

    def _parse_stars(self, text: str) -> int:
        """Parse star count from text like '1,234' or '1.2k'"""
        text = text.strip().replace(',', '')

        if 'k' in text.lower():
            # Handle '1.2k' format
            num = float(text.lower().replace('k', ''))
            return int(num * 1000)

        try:
            return int(text)
        except ValueError:
            return 0

    def _parse_stars_growth(self, text: str) -> int:
        """Parse stars growth from text like '123 stars today'"""
        # Extract just the number part
        import re
        match = re.search(r'([\d,]+)\s*stars?', text)
        if match:
            return self._parse_stars(match.group(1))
        return 0
