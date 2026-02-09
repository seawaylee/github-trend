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
