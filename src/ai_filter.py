"""AI project filter using LLM"""
import json
import logging
from dataclasses import dataclass
from typing import List
from openai import OpenAI
from src.github_scraper import TrendingProject


logger = logging.getLogger(__name__)
SUMMARY_BLOCKLIST = (
    "using-superpowers",
    "skill.md",
    "/users/",
    "/private/tmp",
    "沙箱",
    "无法读取",
    "权限",
    "技能文件"
)


def _normalize_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URL to local proxy path."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


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
        normalized_base_url = _normalize_base_url(base_url)
        self.client = OpenAI(base_url=normalized_base_url, api_key=api_key)
        self.model = model
        # Per-run health flags. main.py uses them to decide whether to push.
        self.last_filter_had_llm_failure = False
        self.last_summary_had_llm_failure = False

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

            # Clean up markdown code blocks if present
            if content.startswith("```"):
                content = content.strip().strip("`")
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            return FilterResult(
                is_ai_related=result.get('is_ai_related', False),
                reason=result.get('reason', '')
            )

        except Exception as e:
            self.last_filter_had_llm_failure = True
            logger.warning(f"LLM filter failed for {project.repo_name}, using keyword fallback: {e}")
            # Fallback to keyword matching
            is_ai = self._keyword_fallback(project.description + " " + project.repo_name)
            return FilterResult(
                is_ai_related=is_ai,
                reason="基于项目描述中的关键词判定（LLM暂不可用）"
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
        self.last_filter_had_llm_failure = False
        results = []

        for project in projects:
            result = self.is_ai_related(project)
            if result.is_ai_related:
                results.append((project, result))
                logger.info(f"✓ AI project: {project.repo_name} - {result.reason}")
            else:
                logger.debug(f"✗ Not AI: {project.repo_name}")

        return results

    def generate_daily_summary(self, projects: List[tuple[TrendingProject, FilterResult]]) -> str:
        """
        Generate a summary of the provided projects, highlighting relevance to Sohu's business.

        Args:
            projects: List of (project, filter_result) tuples

        Returns:
            Summary text
        """
        self.last_summary_had_llm_failure = False
        if not projects:
            return ""

        projects_text = ""
        for i, (p, r) in enumerate(projects, 1):
            projects_text += f"{i}. {p.repo_name}: {p.description} (Language: {p.language})\n"

        prompt = f"""
分析以下今日GitHub热门AI项目列表：

{projects_text}

请完成以下任务：
1. **每日趋势总结**：用一段话简要概括今日项目的整体技术方向或热点（如Agent、RAG、多模态等）。
2. **搜狐业务价值评估**：
   请仔细评估这些项目对搜狐公司的**搜索引擎**、**推荐系统**、**AI基础设施**（训练/推理/部署）是否有明确的技术价值或应用潜力。
   - 只有在确实相关且有提升可能时才提及。
   - 如果有，请列出项目名并详细说明其对特定业务场景（如搜索相关性、推荐多样性、模型推理加速等）的潜在收益。
   - 如果没有明显的直接价值，则不要编造，这部分留空即可。

输出格式要求：
- 使用Markdown格式。
- 总结部分尽量精炼。
- 业务评估部分如果有内容，请使用"🚀 **搜狐业务价值分析**"作为标题。
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个资深技术专家，擅长评估开源项目对企业业务的价值。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=800
            )
            summary_text = response.choices[0].message.content.strip()
            if self._is_invalid_summary(summary_text):
                self.last_summary_had_llm_failure = True
                logger.warning("LLM summary flagged as invalid/meta content, using fallback summary")
                return self._build_fallback_summary(projects)
            return summary_text
        except Exception as e:
            self.last_summary_had_llm_failure = True
            logger.error(f"Failed to generate summary: {e}")
            return self._build_fallback_summary(projects)

    def _is_invalid_summary(self, text: str) -> bool:
        """Detect leaked meta/system text that should never be pushed."""
        if not text or not text.strip():
            return True

        lower_text = text.lower()
        return any(marker in lower_text for marker in SUMMARY_BLOCKLIST)

    def _build_fallback_summary(self, projects: List[tuple[TrendingProject, FilterResult]]) -> str:
        """Build stable summary when LLM output is unavailable or invalid."""
        top_names = "、".join([project.repo_name for project, _ in projects[:3]]) or "今日上榜项目"
        return (
            "## 每日趋势总结\n\n"
            f"今日热点主要集中在 AI Agent、LLM 应用与工程工具链，代表项目包括：{top_names}。\n\n"
            "🚀 **搜狐业务价值分析**\n\n"
            "- 搜索引擎：可优先验证查询改写、结构化抽取、结果摘要等能力。\n"
            "- 推荐系统：可用于内容标签补全、冷启动特征生成与候选重排增强。\n"
            "- AI基础设施：建议推进统一 LLM 网关、推理成本优化与多模型容灾路由。"
        )
