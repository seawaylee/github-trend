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

        trend_response = Mock()
        trend_response.choices = [Mock()]
        trend_response.choices[0].message.content = """本周AI领域呈现以下趋势：
1. LLM应用工具持续火热
2. 机器学习框架优化成为焦点"""

        summary_response = Mock()
        summary_response.choices = [Mock()]
        summary_response.choices[0].message.content = """## 本周趋势总结

本周项目主要聚焦 Agent 与 LLM 工具链。

🚀 **搜狐业务价值分析**

- 搜索引擎：可用于检索增强与结果摘要。
- 推荐系统：可用于标签补全与排序优化。"""

        client.chat.completions.create.side_effect = [trend_response, summary_response]
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


def test_generate_weekly_report_includes_ai_highlight(mock_database, mock_llm_client):
    """Weekly report should include per-project AI highlight like daily report"""
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

    assert "💡 AI亮点：" in report
    assert "Machine learning framework" in report


def test_generate_report_package_contains_weekly_summary(mock_database, mock_llm_client):
    """Weekly package should provide standalone summary for second push message"""
    reporter = WeeklyReporter(
        database=mock_database,
        ai_base_url="http://localhost:8045",
        ai_api_key="sk-test",
        ai_model="gemini-3-pro-high"
    )

    report_package = reporter.generate_report_package(
        week_start=date(2026, 2, 3),
        week_end=date(2026, 2, 7)
    )

    assert "report" in report_package
    assert "summary" in report_package
    assert "搜狐业务价值分析" in report_package["summary"]


def test_generate_weekly_report_rewrites_unavailable_reason(mock_llm_client):
    """Weekly report should rewrite unreadable fallback reason to Chinese highlight."""
    db = Mock()
    db.get_weekly_trends.return_value = [
        {
            "repo_name": "test/openclaw-like",
            "description": "Your own personal AI assistant with agent workflow",
            "language": "Python",
            "url": "https://github.com/test/openclaw-like",
            "stars": 100,
            "stars_growth": 50,
            "ai_relevance_reason": "Keyword-based detection (LLM unavailable)"
        }
    ]

    reporter = WeeklyReporter(
        database=db,
        ai_base_url="http://localhost:8045",
        ai_api_key="sk-test",
        ai_model="gemini-3-pro-high"
    )

    report = reporter.generate_report(
        week_start=date(2026, 2, 3),
        week_end=date(2026, 2, 7)
    )

    assert "LLM unavailable" not in report
    assert "基于项目描述中的关键词判定" in report
