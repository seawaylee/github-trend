# GitHub AI Trend Tracker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated system to track GitHub AI trending projects daily and generate weekly reports via WeCom.

**Architecture:** Lightweight Python scripts with SQLite storage, LLM-based AI filtering, scheduled via launchd on macOS. Daily task (10:00) pushes top 5 AI projects; weekly task (Friday 16:00) generates comprehensive trend report.

**Tech Stack:** Python 3.9+, requests, beautifulsoup4, openai (compatible API), sqlite3, pyyaml

---

## Task 1: Project Setup and Dependencies

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/requirements.txt`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/README.md`

**Step 1: Create requirements.txt**

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
openai>=1.12.0
pyyaml>=6.0.1
python-dateutil>=2.8.2
```

**Step 2: Create README.md**

```markdown
# GitHub AI Trend Tracker

自动追踪GitHub AI相关开源项目趋势，推送到企业微信。

## 功能

- 每日10:00推送Top 5 AI趋势项目
- 每周五16:00推送本周AI趋势总结

## 快速开始

```bash
# 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑config.yaml填入配置

# 初始化数据库
python main.py --init-db

# 测试运行
python main.py --dry-run
python weekly.py --dry-run

# 安装定时任务
./setup.sh install
```

## 配置说明

参考 `config/config.example.yaml`
```

**Step 3: Create directory structure**

```bash
mkdir -p config data logs src tests
```

**Step 4: Commit**

```bash
git add requirements.txt README.md
git commit -m "chore: add project dependencies and README"
```

---

## Task 2: Configuration Management

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/config/config.example.yaml`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/config_loader.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_config_loader.py`

**Step 1: Write the failing test**

Create `tests/test_config_loader.py`:

```python
import pytest
import tempfile
import os
from pathlib import Path
from src.config_loader import load_config, ConfigError


def test_load_valid_config():
    """Test loading valid configuration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("""
ai:
  base_url: "http://127.0.0.1:8045"
  api_key: "sk-test"
  model: "gemini-3-pro-high"
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/test"
tasks:
  daily_limit: 5
  weekly_limit: 25
  daily_hour: 10
  weekly_day: 5
  weekly_hour: 16
logging:
  level: "INFO"
  file: "logs/app.log"
""")
        config = load_config(str(config_file))
        assert config['ai']['model'] == 'gemini-3-pro-high'
        assert config['tasks']['daily_limit'] == 5


def test_missing_config_file():
    """Test error when config file doesn't exist"""
    with pytest.raises(ConfigError):
        load_config("/nonexistent/config.yaml")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_loader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.config_loader'"

**Step 3: Create config example file**

Create `config/config.example.yaml`:

```yaml
# GitHub设置
github:
  token: ""  # 可选，提高API限流额度

# LLM服务配置
ai:
  base_url: "http://127.0.0.1:8045"
  api_key: "sk-f750eba34c6145fc857feaf7f3851f5b"
  model: "gemini-3-pro-high"

# 企业微信配置
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=29f45d56-3f1a-45af-a146-02507f6465b7"

# 任务配置
tasks:
  daily_limit: 5          # 每日推送项目数量
  weekly_limit: 25        # 周报项目数量
  daily_hour: 10          # 每日推送时间
  weekly_day: 5           # 周五
  weekly_hour: 16         # 下午4点

# 日志配置
logging:
  level: "INFO"
  file: "logs/app.log"
  max_bytes: 10485760     # 10MB
  backup_count: 5
```

**Step 4: Write minimal implementation**

Create `src/config_loader.py`:

```python
"""Configuration loader module"""
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigError(Exception):
    """Configuration related errors"""
    pass


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary

    Raises:
        ConfigError: If config file doesn't exist or is invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Validate required fields
        required_sections = ['ai', 'wecom', 'tasks', 'logging']
        for section in required_sections:
            if section not in config:
                raise ConfigError(f"Missing required section: {section}")

        return config
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML format: {e}")
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_config_loader.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add config/config.example.yaml src/config_loader.py tests/test_config_loader.py
git commit -m "feat: add configuration loader with validation"
```

---

## Task 3: Database Schema and Operations

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/database.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_database.py`

**Step 1: Write the failing test**

Create `tests/test_database.py`:

```python
import pytest
import tempfile
from pathlib import Path
from datetime import date
from src.database import Database, Project, TrendRecord


def test_init_db_creates_tables():
    """Test database initialization creates tables"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        db.init_db()

        # Verify tables exist
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert 'projects' in tables
        assert 'trend_records' in tables
        assert 'weekly_reports' in tables


def test_save_and_get_project():
    """Test saving and retrieving project"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        db.init_db()

        project = Project(
            repo_name="test/repo",
            description="Test description",
            language="Python",
            url="https://github.com/test/repo"
        )

        project_id = db.save_project(project)
        assert project_id > 0

        retrieved = db.get_project_by_name("test/repo")
        assert retrieved.repo_name == "test/repo"
        assert retrieved.description == "Test description"


def test_save_trend_record():
    """Test saving trend record"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        db.init_db()

        project = Project(
            repo_name="test/repo",
            description="Test",
            language="Python",
            url="https://github.com/test/repo"
        )
        project_id = db.save_project(project)

        record = TrendRecord(
            project_id=project_id,
            date=date.today(),
            stars=1000,
            stars_growth=100,
            trend_type="daily",
            ranking=1,
            ai_relevance_reason="Uses ML algorithms"
        )

        record_id = db.save_trend_record(record)
        assert record_id > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.database'"

**Step 3: Write minimal implementation**

Create `src/database.py`:

```python
"""Database operations module"""
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional, List
from pathlib import Path


@dataclass
class Project:
    """Project data class"""
    repo_name: str
    description: str
    language: str
    url: str
    id: Optional[int] = None
    first_seen: Optional[date] = None


@dataclass
class TrendRecord:
    """Trend record data class"""
    project_id: int
    date: date
    stars: int
    stars_growth: int
    trend_type: str  # 'daily' or 'weekly'
    ranking: int
    ai_relevance_reason: str
    id: Optional[int] = None


class Database:
    """Database manager"""

    def __init__(self, db_path: str = "data/trends.db"):
        """Initialize database connection"""
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def init_db(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()

        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT UNIQUE NOT NULL,
                description TEXT,
                language TEXT,
                url TEXT NOT NULL,
                first_seen DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trend records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trend_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                date DATE NOT NULL,
                stars INTEGER,
                stars_growth INTEGER,
                trend_type TEXT NOT NULL,
                ranking INTEGER,
                ai_relevance_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(project_id, date, trend_type)
            )
        """)

        # Weekly reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start DATE NOT NULL,
                week_end DATE NOT NULL,
                summary TEXT,
                tech_trends TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def save_project(self, project: Project) -> int:
        """Save project to database"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO projects (repo_name, description, language, url, first_seen)
                VALUES (?, ?, ?, ?, ?)
            """, (
                project.repo_name,
                project.description,
                project.language,
                project.url,
                project.first_seen or date.today()
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Project already exists, return existing ID
            cursor.execute("SELECT id FROM projects WHERE repo_name = ?", (project.repo_name,))
            return cursor.fetchone()[0]

    def get_project_by_name(self, repo_name: str) -> Optional[Project]:
        """Get project by repository name"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE repo_name = ?", (repo_name,))
        row = cursor.fetchone()

        if not row:
            return None

        return Project(
            id=row['id'],
            repo_name=row['repo_name'],
            description=row['description'],
            language=row['language'],
            url=row['url'],
            first_seen=date.fromisoformat(row['first_seen']) if row['first_seen'] else None
        )

    def save_trend_record(self, record: TrendRecord) -> int:
        """Save trend record to database"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO trend_records
                (project_id, date, stars, stars_growth, trend_type, ranking, ai_relevance_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.project_id,
                record.date.isoformat(),
                record.stars,
                record.stars_growth,
                record.trend_type,
                record.ranking,
                record.ai_relevance_reason
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Record already exists for this project/date/type
            cursor.execute("""
                SELECT id FROM trend_records
                WHERE project_id = ? AND date = ? AND trend_type = ?
            """, (record.project_id, record.date.isoformat(), record.trend_type))
            return cursor.fetchone()[0]

    def get_weekly_trends(self, start_date: date, end_date: date) -> List[dict]:
        """Get all AI trend records for a week"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.*, tr.stars, tr.stars_growth, tr.date, tr.ai_relevance_reason, tr.ranking
            FROM projects p
            JOIN trend_records tr ON p.id = tr.project_id
            WHERE tr.date >= ? AND tr.date <= ?
            ORDER BY tr.stars_growth DESC, tr.stars DESC
        """, (start_date.isoformat(), end_date.isoformat()))

        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        self.conn.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add database schema and operations"
```

---

## Task 4: GitHub Trending Scraper

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/github_scraper.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_github_scraper.py`

**Step 1: Write the failing test**

Create `tests/test_github_scraper.py`:

```python
import pytest
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_scraper.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/github_scraper.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_github_scraper.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/github_scraper.py tests/test_github_scraper.py
git commit -m "feat: add GitHub trending scraper"
```

---

## Task 5: AI Project Filter with LLM

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/ai_filter.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_ai_filter.py`

**Step 1: Write the failing test**

Create `tests/test_ai_filter.py`:

```python
import pytest
from unittest.mock import Mock, patch
from src.ai_filter import AIFilter, FilterResult
from src.github_scraper import TrendingProject


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    with patch('src.ai_filter.OpenAI') as mock:
        client = Mock()
        mock.return_value = client

        # Mock response
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = '{"is_ai_related": true, "reason": "Uses machine learning"}'

        client.chat.completions.create.return_value = response

        yield client


def test_filter_ai_projects(mock_openai_client):
    """Test filtering AI-related projects"""
    filter = AIFilter(
        base_url="http://localhost:8045",
        api_key="sk-test",
        model="gemini-3-pro-high"
    )

    project = TrendingProject(
        repo_name="test/ml-project",
        description="A machine learning framework for deep learning",
        language="Python",
        url="https://github.com/test/ml-project",
        stars=1000,
        stars_growth=100,
        ranking=1
    )

    result = filter.is_ai_related(project)

    assert result.is_ai_related is True
    assert "machine learning" in result.reason.lower()


def test_keyword_fallback():
    """Test keyword-based fallback when LLM fails"""
    filter = AIFilter(
        base_url="http://localhost:8045",
        api_key="sk-test",
        model="gemini-3-pro-high"
    )

    # Test AI-related keywords
    assert filter._keyword_fallback("machine learning framework") is True
    assert filter._keyword_fallback("LLM application") is True
    assert filter._keyword_fallback("GPT-based chatbot") is True
    assert filter._keyword_fallback("deep neural network") is True

    # Test non-AI projects
    assert filter._keyword_fallback("web development framework") is False
    assert filter._keyword_fallback("database management") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_filter.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/ai_filter.py`:

```python
"""AI project filter using LLM"""
import json
import logging
from dataclasses import dataclass
from typing import List
from openai import OpenAI
from src.github_scraper import TrendingProject


logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """AI filter result"""
    is_ai_related: bool
    reason: str


class AIFilter:
    """Filter AI-related projects using LLM"""

    AI_KEYWORDS = [
        'ai', 'ml', 'machine learning', 'deep learning', 'neural network',
        'llm', 'gpt', 'transformer', 'bert', 'chatbot', 'computer vision',
        'nlp', 'natural language', 'opencv', 'tensorflow', 'pytorch',
        'stable diffusion', 'gan', 'generative', 'diffusion model',
        'embedding', 'vector database', 'rag', 'agent', 'langchain'
    ]

    def __init__(self, base_url: str, api_key: str, model: str):
        """
        Initialize AI filter

        Args:
            base_url: OpenAI-compatible API base URL
            api_key: API key
            model: Model name
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def is_ai_related(self, project: TrendingProject) -> FilterResult:
        """
        Determine if project is AI-related

        Args:
            project: Project to check

        Returns:
            FilterResult with is_ai_related flag and reason
        """
        try:
            prompt = f"""判断以下GitHub项目是否与AI相关（机器学习、深度学习、LLM、计算机视觉、NLP、AI工具等）。

项目名：{project.repo_name}
描述：{project.description}
语言：{project.language}

请返回JSON格式：{{"is_ai_related": true/false, "reason": "判断理由"}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个AI项目识别专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            return FilterResult(
                is_ai_related=result.get('is_ai_related', False),
                reason=result.get('reason', '')
            )

        except Exception as e:
            logger.warning(f"LLM filter failed for {project.repo_name}, using keyword fallback: {e}")
            # Fallback to keyword matching
            is_ai = self._keyword_fallback(project.description + " " + project.repo_name)
            return FilterResult(
                is_ai_related=is_ai,
                reason="Keyword-based detection (LLM unavailable)"
            )

    def _keyword_fallback(self, text: str) -> bool:
        """Fallback keyword-based detection"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.AI_KEYWORDS)

    def batch_filter(self, projects: List[TrendingProject]) -> List[tuple[TrendingProject, FilterResult]]:
        """
        Filter multiple projects

        Args:
            projects: List of projects to filter

        Returns:
            List of (project, result) tuples for AI-related projects
        """
        results = []

        for project in projects:
            result = self.is_ai_related(project)
            if result.is_ai_related:
                results.append((project, result))
                logger.info(f"✓ AI project: {project.repo_name} - {result.reason}")
            else:
                logger.debug(f"✗ Not AI: {project.repo_name}")

        return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_filter.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/ai_filter.py tests/test_ai_filter.py
git commit -m "feat: add AI project filter with LLM and keyword fallback"
```

---

## Task 6: WeCom Message Notifier

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/wecom_notifier.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_wecom_notifier.py`

**Step 1: Write the failing test**

Create `tests/test_wecom_notifier.py`:

```python
import pytest
from unittest.mock import Mock, patch
from src.wecom_notifier import WeComNotifier
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult
from datetime import date


@pytest.fixture
def mock_requests():
    """Mock requests library"""
    with patch('src.wecom_notifier.requests') as mock:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock.post.return_value = response
        yield mock


def test_format_daily_message():
    """Test formatting daily message"""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/ml-lib",
                description="Machine learning library",
                language="Python",
                url="https://github.com/test/ml-lib",
                stars=1000,
                stars_growth=100,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="Uses ML algorithms")
        )
    ]

    message = notifier._format_daily_message(projects_with_reasons, date(2026, 2, 9))

    assert "GitHub AI趋势" in message
    assert "2026-02-09" in message
    assert "test/ml-lib" in message
    assert "⭐ 1,000" in message
    assert "+100" in message


def test_send_notification(mock_requests):
    """Test sending notification"""
    notifier = WeComNotifier("https://test.webhook.url")

    success = notifier.send_markdown("Test message")

    assert success is True
    mock_requests.post.assert_called_once()

    call_args = mock_requests.post.call_args
    assert call_args[0][0] == "https://test.webhook.url"
    assert call_args[1]['json']['msgtype'] == 'markdown'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_wecom_notifier.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/wecom_notifier.py`:

```python
"""WeCom (Enterprise WeChat) notifier module"""
import requests
import logging
from typing import List
from datetime import date
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult


logger = logging.getLogger(__name__)


class WeComNotifier:
    """WeCom webhook notifier"""

    def __init__(self, webhook_url: str):
        """
        Initialize notifier

        Args:
            webhook_url: WeCom webhook URL
        """
        self.webhook_url = webhook_url

    def send_markdown(self, content: str) -> bool:
        """
        Send markdown message to WeCom

        Args:
            content: Markdown content

        Returns:
            True if successful
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get('errcode') == 0:
                logger.info("Message sent successfully to WeCom")
                return True
            else:
                logger.error(f"WeCom API error: {result}")
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to send WeCom message: {e}")
            return False

    def send_daily_report(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date
    ) -> bool:
        """
        Send daily AI trends report

        Args:
            projects_with_reasons: List of (project, filter_result) tuples
            report_date: Date of the report

        Returns:
            True if successful
        """
        message = self._format_daily_message(projects_with_reasons, report_date)
        return self.send_markdown(message)

    def _format_daily_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date
    ) -> str:
        """Format daily message in markdown"""

        lines = [
            "🔥 **今日GitHub AI趋势 Top 5**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n"
        ]

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        for idx, (project, result) in enumerate(projects_with_reasons[:5]):
            emoji = emojis[idx] if idx < len(emojis) else f"{idx+1}."

            # Format stars with comma
            stars_str = f"{project.stars:,}"
            growth_str = f"+{project.stars_growth}" if project.stars_growth > 0 else ""

            lines.extend([
                f"\n{emoji} **{project.repo_name}** ⭐ {stars_str} ({growth_str})",
                f"🏷 {project.language}",
                f"📝 {project.description[:100]}..." if len(project.description) > 100 else f"📝 {project.description}",
                f"💡 AI亮点：{result.reason}",
                f"🔗 [查看项目]({project.url})\n"
            ])

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")

        return "\n".join(lines)

    def send_weekly_report(self, report_content: str) -> bool:
        """
        Send weekly report

        Args:
            report_content: Formatted weekly report markdown

        Returns:
            True if successful
        """
        return self.send_markdown(report_content)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_wecom_notifier.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/wecom_notifier.py tests/test_wecom_notifier.py
git commit -m "feat: add WeCom notification with markdown formatting"
```

---

## Task 7: Weekly Report Generator

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/src/weekly_reporter.py`
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/tests/test_weekly_reporter.py`

**Step 1: Write the failing test**

Create `tests/test_weekly_reporter.py`:

```python
import pytest
from unittest.mock import Mock, patch
from datetime import date
from src.weekly_reporter import WeeklyReporter


@pytest.fixture
def mock_database():
    """Mock database"""
    db = Mock()
    db.get_weekly_trends.return_value = [
        {
            'repo_name': 'test/ml-lib',
            'description': 'ML library',
            'language': 'Python',
            'url': 'https://github.com/test/ml-lib',
            'stars': 1000,
            'stars_growth': 500,
            'ai_relevance_reason': 'Machine learning framework'
        },
        {
            'repo_name': 'test/ai-tool',
            'description': 'AI tool',
            'language': 'TypeScript',
            'url': 'https://github.com/test/ai-tool',
            'stars': 800,
            'stars_growth': 300,
            'ai_relevance_reason': 'LLM application'
        }
    ]
    return db


@pytest.fixture
def mock_llm_client():
    """Mock LLM client"""
    with patch('src.weekly_reporter.OpenAI') as mock:
        client = Mock()
        mock.return_value = client

        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = """本周AI领域呈现以下趋势：
1. LLM应用工具持续火热
2. 机器学习框架优化成为焦点"""

        client.chat.completions.create.return_value = response
        yield client


def test_generate_weekly_report(mock_database, mock_llm_client):
    """Test generating weekly report"""
    reporter = WeeklyReporter(
        database=mock_database,
        ai_base_url="http://localhost:8045",
        ai_api_key="sk-test",
        ai_model="gemini-3-pro-high"
    )

    report = reporter.generate_report(
        week_start=date(2026, 2, 3),
        week_end=date(2026, 2, 7)
    )

    assert "本周AI趋势周报" in report
    assert "2026-02-03" in report
    assert "test/ml-lib" in report
    assert "热门项目" in report
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_weekly_reporter.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/weekly_reporter.py`:

```python
"""Weekly report generator"""
import logging
from datetime import date
from typing import List, Dict
from collections import Counter
from openai import OpenAI
from src.database import Database


logger = logging.getLogger(__name__)


class WeeklyReporter:
    """Generate weekly AI trends report"""

    def __init__(
        self,
        database: Database,
        ai_base_url: str,
        ai_api_key: str,
        ai_model: str
    ):
        """
        Initialize weekly reporter

        Args:
            database: Database instance
            ai_base_url: LLM API base URL
            ai_api_key: LLM API key
            ai_model: LLM model name
        """
        self.db = database
        self.llm = OpenAI(base_url=ai_base_url, api_key=ai_api_key)
        self.model = ai_model

    def generate_report(
        self,
        week_start: date,
        week_end: date,
        max_projects: int = 25
    ) -> str:
        """
        Generate weekly report

        Args:
            week_start: Start date (Monday)
            week_end: End date (Friday)
            max_projects: Maximum projects to include

        Returns:
            Formatted markdown report
        """
        # Fetch weekly trends
        trends = self.db.get_weekly_trends(week_start, week_end)

        if not trends:
            return self._format_empty_report(week_start, week_end)

        # Deduplicate (keep highest stars for each project)
        unique_projects = self._deduplicate_projects(trends)

        # Limit to max_projects
        top_projects = unique_projects[:max_projects]

        # Generate LLM analysis
        tech_trends = self._analyze_trends(top_projects)

        # Format report
        report = self._format_report(
            week_start,
            week_end,
            top_projects,
            tech_trends
        )

        return report

    def _deduplicate_projects(self, trends: List[Dict]) -> List[Dict]:
        """Deduplicate projects, keeping highest stars"""
        projects_map = {}

        for trend in trends:
            repo_name = trend['repo_name']
            if repo_name not in projects_map or trend['stars'] > projects_map[repo_name]['stars']:
                projects_map[repo_name] = trend

        # Sort by stars_growth and stars
        unique = list(projects_map.values())
        unique.sort(key=lambda x: (x['stars_growth'], x['stars']), reverse=True)

        return unique

    def _analyze_trends(self, projects: List[Dict]) -> str:
        """Use LLM to analyze technology trends"""

        # Prepare project summary
        summary = []
        for p in projects[:10]:  # Analyze top 10
            summary.append(f"- {p['repo_name']}: {p['description']} ({p['language']})")

        prompt = f"""分析以下本周GitHub AI趋势项目，总结技术趋势和热点方向（2-3条要点）：

{chr(10).join(summary)}

请返回简洁的趋势分析（每条1句话）。"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是AI技术趋势分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"LLM trend analysis failed: {e}")
            return "本周AI项目持续活跃，涵盖多个技术方向。"

    def _categorize_projects(self, projects: List[Dict]) -> Dict[str, int]:
        """Categorize projects by technology area"""
        categories = {
            'LLM/NLP': 0,
            '计算机视觉': 0,
            'AI工具/框架': 0,
            '多模态应用': 0,
            '其他': 0
        }

        for p in projects:
            reason = p.get('ai_relevance_reason', '').lower()
            desc = p.get('description', '').lower()
            text = reason + ' ' + desc

            if any(kw in text for kw in ['llm', 'nlp', 'language', 'gpt', 'chatbot', 'embedding']):
                categories['LLM/NLP'] += 1
            elif any(kw in text for kw in ['vision', 'image', 'video', 'opencv', 'detection']):
                categories['计算机视觉'] += 1
            elif any(kw in text for kw in ['framework', 'tool', 'library', 'platform']):
                categories['AI工具/框架'] += 1
            elif any(kw in text for kw in ['multimodal', 'multi-modal', 'audio', 'speech']):
                categories['多模态应用'] += 1
            else:
                categories['其他'] += 1

        return categories

    def _format_report(
        self,
        week_start: date,
        week_end: date,
        projects: List[Dict],
        tech_trends: str
    ) -> str:
        """Format weekly report"""

        total_stars = sum(p['stars_growth'] for p in projects)
        categories = self._categorize_projects(projects)

        lines = [
            "📊 **本周AI趋势周报**",
            f"\n📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}",
            "\n## 📈 本周概览",
            f"- 发现 **{len(projects)}** 个AI相关项目",
            f"- 总计新增 **{total_stars:,}** stars",
            "\n## 🏆 热门项目 Top 10\n"
        ]

        # Top 10 projects
        for idx, p in enumerate(projects[:10], 1):
            lines.extend([
                f"{idx}. **{p['repo_name']}** ⭐ {p['stars']:,} (+{p['stars_growth']})",
                f"   📝 {p['description'][:80]}..." if len(p['description']) > 80 else f"   📝 {p['description']}",
                f"   🔗 [查看项目]({p['url']})\n"
            ])

        # Tech trends
        lines.extend([
            "\n## 🔥 技术趋势分析",
            tech_trends,
            "\n## 📊 分类统计"
        ])

        for category, count in categories.items():
            if count > 0:
                emoji = self._get_category_emoji(category)
                lines.append(f"- {emoji} {category}: {count}个")

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")

        return "\n".join(lines)

    def _format_empty_report(self, week_start: date, week_end: date) -> str:
        """Format empty report when no data"""
        return f"""📊 **本周AI趋势周报**

📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}

⚠️ 本周暂无AI趋势数据

---
⏰ 由GitHub-Trend-Bot自动推送"""

    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for category"""
        emoji_map = {
            'LLM/NLP': '🤖',
            '计算机视觉': '👁',
            'AI工具/框架': '🛠',
            '多模态应用': '🎨',
            '其他': '📦'
        }
        return emoji_map.get(category, '📦')
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_weekly_reporter.py -v`
Expected: PASS (1 test)

**Step 5: Commit**

```bash
git add src/weekly_reporter.py tests/test_weekly_reporter.py
git commit -m "feat: add weekly report generator with LLM analysis"
```

---

## Task 8: Main Daily Script

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/main.py`

**Step 1: Write main.py**

Create `main.py`:

```python
#!/usr/bin/env python3
"""Main script for daily GitHub AI trends"""
import sys
import argparse
import logging
from datetime import date
from pathlib import Path

from src.config_loader import load_config, ConfigError
from src.database import Database
from src.github_scraper import GitHubScraper
from src.ai_filter import AIFilter
from src.wecom_notifier import WeComNotifier


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_file = log_config.get('file', 'logs/app.log')
    log_level = log_config.get('level', 'INFO')

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def init_database(db_path: str = "data/trends.db"):
    """Initialize database schema"""
    db = Database(db_path)
    db.init_db()
    print(f"✓ Database initialized at {db_path}")
    db.close()


def show_stats(db_path: str = "data/trends.db"):
    """Show database statistics"""
    db = Database(db_path)
    cursor = db.conn.cursor()

    # Count projects
    cursor.execute("SELECT COUNT(*) FROM projects")
    project_count = cursor.fetchone()[0]

    # Count trend records
    cursor.execute("SELECT COUNT(*) FROM trend_records")
    record_count = cursor.fetchone()[0]

    # Recent records
    cursor.execute("""
        SELECT date, COUNT(*) as count
        FROM trend_records
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
    """)
    recent = cursor.fetchall()

    print(f"\n📊 Database Statistics")
    print(f"Total projects: {project_count}")
    print(f"Total trend records: {record_count}")
    print(f"\nRecent activity:")
    for row in recent:
        print(f"  {row[0]}: {row[1]} projects")

    db.close()


def run_daily_task(config: dict, dry_run: bool = False):
    """Run daily trending task"""
    logger = logging.getLogger(__name__)
    logger.info("Starting daily task")

    # Initialize components
    db = Database()
    scraper = GitHubScraper(config['github'].get('token'))
    ai_filter = AIFilter(
        base_url=config['ai']['base_url'],
        api_key=config['ai']['api_key'],
        model=config['ai']['model']
    )
    notifier = WeComNotifier(config['wecom']['webhook_url'])

    try:
        # Fetch trending projects
        logger.info("Fetching daily trending...")
        daily_projects = scraper.fetch_trending('daily')

        logger.info("Fetching weekly trending...")
        weekly_projects = scraper.fetch_trending('weekly')

        all_projects = daily_projects + weekly_projects
        logger.info(f"Total projects fetched: {len(all_projects)}")

        # Filter AI projects
        logger.info("Filtering AI-related projects...")
        ai_projects = ai_filter.batch_filter(all_projects)
        logger.info(f"Found {len(ai_projects)} AI-related projects")

        if not ai_projects:
            logger.warning("No AI projects found today")
            if not dry_run:
                notifier.send_markdown("⚠️ 今日未发现AI相关趋势项目")
            return

        # Save to database
        today = date.today()
        for project, filter_result in ai_projects:
            # Save project
            from src.database import Project, TrendRecord

            db_project = Project(
                repo_name=project.repo_name,
                description=project.description,
                language=project.language,
                url=project.url
            )
            project_id = db.save_project(db_project)

            # Save trend record
            record = TrendRecord(
                project_id=project_id,
                date=today,
                stars=project.stars,
                stars_growth=project.stars_growth,
                trend_type='daily',
                ranking=project.ranking,
                ai_relevance_reason=filter_result.reason
            )
            db.save_trend_record(record)

        # Get top N projects
        daily_limit = config['tasks']['daily_limit']
        top_projects = ai_projects[:daily_limit]

        logger.info(f"Sending top {len(top_projects)} projects to WeCom")

        if dry_run:
            print("\n🔍 DRY RUN - Would send the following message:\n")
            message = notifier._format_daily_message(top_projects, today)
            print(message)
        else:
            success = notifier.send_daily_report(top_projects, today)
            if success:
                logger.info("✓ Daily report sent successfully")
            else:
                logger.error("✗ Failed to send daily report")

    except Exception as e:
        logger.error(f"Daily task failed: {e}", exc_info=True)
        if not dry_run:
            notifier.send_markdown(f"⚠️ 每日任务执行失败：{str(e)}")
        raise

    finally:
        db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='GitHub AI Trend Tracker - Daily Task')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending notifications')

    args = parser.parse_args()

    # Handle database init
    if args.init_db:
        init_database()
        return 0

    # Handle stats
    if args.stats:
        show_stats()
        return 0

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"❌ Config error: {e}", file=sys.stderr)
        return 1

    # Setup logging
    setup_logging(config)

    # Run daily task
    try:
        run_daily_task(config, dry_run=args.dry_run)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Test main.py**

Run: `python main.py --help`
Expected: Show help message

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main daily task script"
```

---

## Task 9: Weekly Report Script

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/weekly.py`

**Step 1: Write weekly.py**

Create `weekly.py`:

```python
#!/usr/bin/env python3
"""Weekly report script"""
import sys
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from src.config_loader import load_config, ConfigError
from src.database import Database
from src.weekly_reporter import WeeklyReporter
from src.wecom_notifier import WeComNotifier


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_file = log_config.get('file', 'logs/app.log').replace('app.log', 'weekly.log')
    log_level = log_config.get('level', 'INFO')

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def get_week_range(target_date: date = None) -> tuple[date, date]:
    """
    Get week range (Monday to Friday)

    Args:
        target_date: Target date (default: today)

    Returns:
        (week_start, week_end) tuple
    """
    if target_date is None:
        target_date = date.today()

    # Get Monday of the week
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)

    # Get Friday of the week
    week_end = week_start + timedelta(days=4)

    return week_start, week_end


def run_weekly_task(config: dict, dry_run: bool = False, week_start: date = None):
    """Run weekly report task"""
    logger = logging.getLogger(__name__)
    logger.info("Starting weekly report task")

    # Get week range
    if week_start:
        week_end = week_start + timedelta(days=4)
    else:
        week_start, week_end = get_week_range()

    logger.info(f"Generating report for {week_start} to {week_end}")

    # Initialize components
    db = Database()
    reporter = WeeklyReporter(
        database=db,
        ai_base_url=config['ai']['base_url'],
        ai_api_key=config['ai']['api_key'],
        ai_model=config['ai']['model']
    )
    notifier = WeComNotifier(config['wecom']['webhook_url'])

    try:
        # Generate report
        max_projects = config['tasks']['weekly_limit']
        report = reporter.generate_report(week_start, week_end, max_projects)

        logger.info("Weekly report generated")

        if dry_run:
            print("\n🔍 DRY RUN - Would send the following report:\n")
            print(report)
        else:
            success = notifier.send_weekly_report(report)
            if success:
                logger.info("✓ Weekly report sent successfully")
            else:
                logger.error("✗ Failed to send weekly report")

    except Exception as e:
        logger.error(f"Weekly task failed: {e}", exc_info=True)
        if not dry_run:
            notifier.send_markdown(f"⚠️ 周报生成失败：{str(e)}")
        raise

    finally:
        db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='GitHub AI Trend Tracker - Weekly Report')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending notifications')
    parser.add_argument('--week-start', help='Week start date (YYYY-MM-DD), default: this week Monday')

    args = parser.parse_args()

    # Parse week start
    week_start = None
    if args.week_start:
        try:
            week_start = date.fromisoformat(args.week_start)
        except ValueError:
            print(f"❌ Invalid date format: {args.week_start}", file=sys.stderr)
            return 1

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"❌ Config error: {e}", file=sys.stderr)
        return 1

    # Setup logging
    setup_logging(config)

    # Run weekly task
    try:
        run_weekly_task(config, dry_run=args.dry_run, week_start=week_start)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Test weekly.py**

Run: `python weekly.py --help`
Expected: Show help message

**Step 3: Commit**

```bash
git add weekly.py
git commit -m "feat: add weekly report script"
```

---

## Task 10: Setup Script

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/setup.sh`

**Step 1: Write setup.sh**

Create `setup.sh`:

```bash
#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project paths
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"
CONFIG_FILE="$PROJECT_DIR/config/config.yaml"
CONFIG_EXAMPLE="$PROJECT_DIR/config/config.example.yaml"

# launchd paths
DAILY_PLIST="$HOME/Library/LaunchAgents/com.github-trend.daily.plist"
WEEKLY_PLIST="$HOME/Library/LaunchAgents/com.github-trend.weekly.plist"

echo -e "${GREEN}GitHub AI Trend Tracker - Setup${NC}\n"

# Function: Check Python version
check_python() {
    echo "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
}

# Function: Create virtual environment
setup_venv() {
    if [ -d "$VENV_PATH" ]; then
        echo -e "${YELLOW}Virtual environment already exists${NC}"
    else
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi

    # Activate venv
    source "$VENV_PATH/bin/activate"

    # Install dependencies
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r "$PROJECT_DIR/requirements.txt"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Function: Setup configuration
setup_config() {
    if [ -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}Config file already exists${NC}"
    else
        echo "Creating config file..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo -e "${GREEN}✓ Config file created at $CONFIG_FILE${NC}"
        echo -e "${YELLOW}⚠ Please edit config/config.yaml with your settings${NC}"
    fi
}

# Function: Initialize database
init_database() {
    echo "Initializing database..."
    source "$VENV_PATH/bin/activate"
    python "$PROJECT_DIR/main.py" --init-db
    echo -e "${GREEN}✓ Database initialized${NC}"
}

# Function: Install launchd tasks
install_launchd() {
    echo "Installing launchd tasks..."

    # Create daily task plist
    cat > "$DAILY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.github-trend.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PATH/bin/python</string>
        <string>$PROJECT_DIR/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/daily.error.log</string>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
</dict>
</plist>
EOF

    # Create weekly task plist
    cat > "$WEEKLY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.github-trend.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PATH/bin/python</string>
        <string>$PROJECT_DIR/weekly.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/weekly.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/weekly.error.log</string>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
</dict>
</plist>
EOF

    # Load launchd tasks
    launchctl unload "$DAILY_PLIST" 2>/dev/null || true
    launchctl unload "$WEEKLY_PLIST" 2>/dev/null || true

    launchctl load "$DAILY_PLIST"
    launchctl load "$WEEKLY_PLIST"

    echo -e "${GREEN}✓ Launchd tasks installed${NC}"
    echo -e "  Daily task: Every day at 10:00"
    echo -e "  Weekly task: Every Friday at 16:00"
}

# Function: Uninstall launchd tasks
uninstall_launchd() {
    echo "Uninstalling launchd tasks..."

    launchctl unload "$DAILY_PLIST" 2>/dev/null || true
    launchctl unload "$WEEKLY_PLIST" 2>/dev/null || true

    rm -f "$DAILY_PLIST"
    rm -f "$WEEKLY_PLIST"

    echo -e "${GREEN}✓ Launchd tasks uninstalled${NC}"
}

# Function: Run tests
run_tests() {
    echo "Running tests..."
    source "$VENV_PATH/bin/activate"

    # Install pytest if not installed
    pip install -q pytest

    pytest "$PROJECT_DIR/tests" -v

    echo -e "${GREEN}✓ Tests passed${NC}"
}

# Main menu
case "${1:-}" in
    install)
        check_python
        setup_venv
        setup_config
        init_database
        install_launchd
        echo -e "\n${GREEN}✓ Setup complete!${NC}"
        echo -e "\nNext steps:"
        echo -e "1. Edit config/config.yaml with your settings"
        echo -e "2. Test: python main.py --dry-run"
        echo -e "3. Check logs: tail -f logs/daily.log"
        ;;

    uninstall)
        uninstall_launchd
        echo -e "${GREEN}✓ Uninstall complete${NC}"
        ;;

    test)
        run_tests
        ;;

    *)
        echo "Usage: $0 {install|uninstall|test}"
        echo ""
        echo "Commands:"
        echo "  install    - Install and setup everything"
        echo "  uninstall  - Remove launchd tasks"
        echo "  test       - Run tests"
        exit 1
        ;;
esac
```

**Step 2: Make executable**

Run: `chmod +x setup.sh`

**Step 3: Commit**

```bash
git add setup.sh
chmod +x setup.sh
git commit -m "feat: add setup script for installation"
```

---

## Task 11: Create Config and Test Installation

**Files:**
- Create: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/config/config.yaml`

**Step 1: Copy config from example**

```bash
cp config/config.example.yaml config/config.yaml
```

**Step 2: Verify config.yaml has correct values**

Config should already have:
- ai.base_url: http://127.0.0.1:8045
- ai.api_key: sk-f750eba34c6145fc857feaf7f3851f5b
- ai.model: gemini-3-pro-high
- wecom.webhook_url: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=29f45d56-3f1a-45af-a146-02507f6465b7

**Step 3: Install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Step 4: Initialize database**

Run: `python main.py --init-db`
Expected: "✓ Database initialized at data/trends.db"

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 6: Test dry run**

Run: `python main.py --dry-run`
Expected: Show formatted message without sending

Run: `python weekly.py --dry-run`
Expected: Show weekly report without sending

**Step 7: Commit**

```bash
git add .
git commit -m "chore: setup configuration and verify installation"
```

---

## Task 12: Final Integration Test and Documentation

**Files:**
- Update: `/Users/NikoBelic/app/git/github-trend/.worktrees/implement-tracker/README.md`

**Step 1: Run full integration test**

```bash
# Test daily task (may take a few minutes)
python main.py --dry-run
```

Expected output:
- Fetches GitHub trending
- Filters AI projects with LLM
- Shows top 5 formatted message

**Step 2: Update README with actual usage**

Update `README.md` with complete instructions and troubleshooting section.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with complete usage instructions"
```

---

## Task 13: Merge to Main Branch

**Step 1: Run final verification**

```bash
# Ensure all tests pass
pytest tests/ -v

# Verify executables
python main.py --help
python weekly.py --help
./setup.sh test
```

**Step 2: Merge to main**

```bash
cd /Users/NikoBelic/app/git/github-trend
git checkout master
git merge feature/implement-tracker
```

**Step 3: Install in main directory**

```bash
./setup.sh install
```

**Step 4: Verify launchd tasks**

Run: `launchctl list | grep github-trend`
Expected: See both daily and weekly tasks

**Step 5: Final commit**

```bash
git tag v1.0.0
git log --oneline
```

---

## Summary

This plan implements a complete GitHub AI trend tracker with:

✅ **Core Features:**
- Daily GitHub trending scraping (daily + weekly)
- LLM-based AI project filtering
- Top 5 daily projects pushed to WeCom at 10:00
- Weekly report (Friday 16:00) with trend analysis
- SQLite storage with complete history

✅ **Quality:**
- Comprehensive test coverage
- Error handling and logging
- Dry-run mode for testing
- Keyword fallback when LLM unavailable

✅ **Deployment:**
- macOS launchd automated scheduling
- One-command setup script
- Configuration validation

✅ **Principles:**
- TDD throughout
- DRY (no code duplication)
- YAGNI (minimal necessary features)
- Frequent commits (every task)

**Estimated time:** 2-3 hours for complete implementation
