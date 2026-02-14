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


def test_generate_daily_summary_filters_meta_leakage():
    """Test summary falls back when LLM returns meta/system leakage text"""
    with patch('src.ai_filter.OpenAI') as mock:
        client = Mock()
        mock.return_value = client

        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = (
            "我按说明本应先使用 using-superpowers 等技能文件，"
            "但这些路径位于 /Users/... 无法读取 SKILL.md。"
        )
        client.chat.completions.create.return_value = response

        filter = AIFilter(
            base_url="http://localhost:8045",
            api_key="sk-test",
            model="gpt-5.1 low"
        )

        projects = [
            (
                TrendingProject(
                    repo_name="test/ml-project",
                    description="A machine learning framework for deep learning",
                    language="Python",
                    url="https://github.com/test/ml-project",
                    stars=1000,
                    stars_growth=100,
                    ranking=1
                ),
                FilterResult(is_ai_related=True, reason="Uses machine learning")
            )
        ]

        summary = filter.generate_daily_summary(projects)

        assert "using-superpowers" not in summary.lower()
        assert "/users/" not in summary.lower()
        assert "skill.md" not in summary.lower()
        assert "每日趋势总结" in summary
        assert "搜狐业务价值分析" in summary
        assert filter.last_summary_had_llm_failure is True


def test_is_ai_related_marks_llm_failure_when_fallback_used():
    """When LLM call fails, filter should mark failure and fallback to keywords."""
    with patch('src.ai_filter.OpenAI') as mock:
        client = Mock()
        mock.return_value = client
        client.chat.completions.create.side_effect = RuntimeError("llm down")

        filter = AIFilter(
            base_url="http://localhost:8045",
            api_key="sk-test",
            model="gemini-3-pro-high"
        )

        project = TrendingProject(
            repo_name="test/llm-agent",
            description="An LLM agent framework",
            language="Python",
            url="https://github.com/test/llm-agent",
            stars=1000,
            stars_growth=100,
            ranking=1
        )

        result = filter.is_ai_related(project)

        assert result.is_ai_related is True
        assert "关键词" in result.reason
        assert filter.last_filter_had_llm_failure is True
