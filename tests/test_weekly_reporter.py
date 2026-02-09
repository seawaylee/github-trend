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
