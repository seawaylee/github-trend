"""Database operations module"""
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
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

        # Daily push records table (actual pushed repos history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_push_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT NOT NULL,
                pushed_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo_name, pushed_date)
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

    def save_daily_push_records(self, repo_names: List[str], pushed_date: date) -> None:
        """Save daily pushed repo names for de-duplication in next days."""
        if not repo_names:
            return

        cursor = self.conn.cursor()
        values = [(repo_name, pushed_date.isoformat()) for repo_name in repo_names]
        cursor.executemany("""
            INSERT OR IGNORE INTO daily_push_records (repo_name, pushed_date)
            VALUES (?, ?)
        """, values)
        self.conn.commit()

    def get_recently_pushed_repo_names(
        self,
        lookback_days: int = 7,
        reference_date: Optional[date] = None
    ) -> set[str]:
        """
        Get repo names pushed within lookback window before reference date.

        Example:
            reference_date=2026-02-12, lookback_days=7
            window: [2026-02-05, 2026-02-11]
        """
        if reference_date is None:
            reference_date = date.today()

        if lookback_days < 1:
            return set()

        window_start = reference_date - timedelta(days=lookback_days - 1)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT repo_name
            FROM daily_push_records
            WHERE pushed_date >= ? AND pushed_date <= ?
        """, (window_start.isoformat(), reference_date.isoformat()))

        return {row[0] for row in cursor.fetchall()}

    def close(self):
        """Close database connection"""
        self.conn.close()
