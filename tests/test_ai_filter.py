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
