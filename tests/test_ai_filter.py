import pytest
from unittest.mock import patch
from src.ai_filter import AIFilter, FilterResult
from src.github_scraper import TrendingProject


@pytest.fixture
def mock_llm_call():
    """Mock shared LLM bridge."""
    with patch("src.ai_filter.call_shared_llm", return_value='{"is_ai_related": true, "reason": "Uses machine learning"}') as mocked:
        yield mocked


def test_filter_ai_projects(mock_llm_call):
    """Test filtering AI-related projects"""
    filter = AIFilter(
        base_url="https://gmn.chuangzuoli.com",
        api_key="sk-test",
        model="gpt-5.4",
        timeout=120,
        max_retries=3,
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
    _, kwargs = mock_llm_call.call_args
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["timeout"] == 120
    assert kwargs["reasoning_effort"] == "xhigh"


def test_keyword_fallback():
    """Test keyword-based fallback when LLM fails"""
    filter = AIFilter(
        base_url="https://gmn.chuangzuoli.com",
        api_key="sk-test",
        model="gpt-5.4"
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
    """Test summary falls back when all LLM retries return invalid meta/system leakage text"""
    with patch("src.ai_filter.call_shared_llm") as mocked_call:
        mocked_call.return_value = (
            "我按说明本应先使用 using-superpowers 等技能文件，"
            "但这些路径位于 /Users/... 无法读取 SKILL.md。"
        )

        filter = AIFilter(
            base_url="https://gmn.chuangzuoli.com",
            api_key="sk-test",
            model="gpt-5.4",
            timeout=120,
            max_retries=2,
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
        assert mocked_call.call_count == 2


def test_generate_daily_summary_retries_and_uses_second_valid_response():
    """When first summary is invalid and second is valid, should return second response."""
    with patch("src.ai_filter.call_shared_llm") as mocked_call:
        mocked_call.side_effect = [
            "using-superpowers /Users/... SKILL.md",
            "## 每日趋势总结\n\n这是一次正常总结。",
        ]

        filter = AIFilter(
            base_url="https://gmn.chuangzuoli.com",
            api_key="sk-test",
            model="gpt-5.4",
            timeout=120,
            max_retries=2,
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

        assert summary == "## 每日趋势总结\n\n这是一次正常总结。"
        assert filter.last_summary_had_llm_failure is False
        assert mocked_call.call_count == 2


def test_is_ai_related_marks_llm_failure_when_fallback_used():
    """When LLM call fails, filter should mark failure and fallback to keywords."""
    with patch("src.ai_filter.call_shared_llm", side_effect=RuntimeError("llm down")):

        filter = AIFilter(
            base_url="https://gmn.chuangzuoli.com",
            api_key="sk-test",
            model="gpt-5.4",
            timeout=120,
            max_retries=3,
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
