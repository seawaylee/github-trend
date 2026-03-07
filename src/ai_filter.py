"""AI project filter using LLM"""
import json
import logging
from dataclasses import dataclass
from typing import List
from src.github_scraper import TrendingProject
from src.shared_llm import call_shared_llm


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

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 30, max_retries: int = 1):
        """
        Initialize AI filter

        Args:
            base_url: OpenAI-compatible API base URL
            api_key: API key
            model: Model name
            timeout: Request timeout in seconds
            max_retries: Max attempts for summary generation
        """
        self.base_url = (base_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.model = model
        self.timeout = max(1, int(timeout))
        self.max_retries = max(1, int(max_retries))
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

            content = call_shared_llm(
                prompt,
                system_prompt="你是一个AI项目识别专家。",
                model=self.model,
                temperature=0.3,
                timeout=self.timeout,
                base_url=self.base_url,
                api_key=self.api_key,
                reasoning_effort="xhigh",
            )

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
分析以下今日 GitHub 热门 AI 项目列表：

{projects_text}

只输出最终 Markdown 正文，不要输出任何解释、前言、后记、代码块、系统提示、路径、工具名、技能名、沙箱信息或多余说明。

严格按照下面模板输出，且只能输出这两个标题下的正文：

## 每日趋势总结
<1 段，总结今天项目的共同技术方向与热点，控制在 120-180 字>

🚀 **搜狐业务价值分析**
<只分析确实有明确价值的项目；按项目分条写，每条说明它对 搜索引擎 / 推荐系统 / AI基础设施 的具体价值。若某个方向没有明确价值，就不要硬写。若整体都没有明确价值，则只写“暂未发现明确可直接落地的项目”。>

硬性要求：
- 只能基于给定项目列表作答，不要编造未出现的项目。
- 不要出现“根据要求”“下面是”“我认为”“我按说明”等元话术。
- 不要出现 `using-superpowers`、`SKILL.md`、`/Users/`、`沙箱`、`工具`、`系统提示` 等词。
- 不要输出项目链接、参考资料、附注、免责声明。
- 不要省略标题，不要增加第三个标题。
"""

        for attempt in range(1, self.max_retries + 1):
            try:
                summary_text = call_shared_llm(
                    prompt,
                    system_prompt="你是一个资深技术专家，擅长评估开源项目对企业业务的价值。",
                    model=self.model,
                    temperature=0.4,
                    timeout=self.timeout,
                    base_url=self.base_url,
                    api_key=self.api_key,
                    reasoning_effort="xhigh",
                )
                summary_text = summary_text.strip()
                if self._is_invalid_summary(summary_text):
                    logger.warning(
                        "LLM summary attempt %s/%s flagged as invalid/meta content",
                        attempt,
                        self.max_retries,
                    )
                    if attempt < self.max_retries:
                        continue
                    self.last_summary_had_llm_failure = True
                    logger.warning("LLM summary invalid after retries, using fallback summary")
                    return self._build_fallback_summary(projects)
                return summary_text
            except Exception as e:
                logger.warning(
                    "Failed to generate summary on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    continue
                self.last_summary_had_llm_failure = True
                logger.error(f"Failed to generate summary after retries: {e}")
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
