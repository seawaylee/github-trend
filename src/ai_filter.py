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
