"""AI project filter using LLM"""
import json
import logging
import re
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
    category: str = ""


@dataclass
class HeuristicAssessment:
    """Heuristic AI-signal assessment used to补足 LLM false negatives."""
    is_ai_related: bool
    reason: str
    category: str = ""
    score: int = 0


class AIFilter:
    """Filter AI-related projects using LLM + heuristic guardrails."""

    AI_KEYWORDS = [
        'ai', 'ml', 'machine learning', 'deep learning', 'neural network',
        'llm', 'gpt', 'transformer', 'bert', 'chatbot', 'computer vision',
        'nlp', 'natural language', 'opencv', 'tensorflow', 'pytorch',
        'stable diffusion', 'gan', 'generative', 'diffusion model',
        'embedding', 'vector database', 'rag', 'agent', 'langchain',
        'copilot', 'assistant', 'inference', 'multimodal', 'mcp',
        'tool calling', 'prompt', 'fine-tuning', 'reasoning model'
    ]

    STRONG_AI_PHRASES = [
        'ai-native', 'ai native', 'ai-powered', 'ai powered', 'built for ai',
        'for ai agents', 'for ai agent', 'for llm apps', 'for llm agents',
        'for agents', 'agentic', 'copilot for', 'assistant for',
        'llm runtime', 'agent runtime', 'tool calling', 'context engineering'
    ]

    AGENT_KEYWORDS = [
        'agent', 'agents', 'agentic', 'assistant', 'copilot', 'autonomous',
        'workflow', 'orchestration', 'memory', 'skills', 'tool calling',
        'mcp', 'planner', 'subagent', 'browser use', 'browser-use'
    ]

    TOOLING_KEYWORDS = [
        'cli', 'sdk', 'runtime', 'adapter', 'bridge', 'automation',
        'desktop', 'browser', 'website', 'web app', 'electron', 'chrome',
        'extension', 'plugin', 'workflow', 'tool', 'tooling', 'sandbox',
        'ide', 'editor', 'coding agent', 'devtool', 'developer tool',
        'command line', 'terminal', 'gui', 'draw.io', 'drawio'
    ]

    MODEL_KEYWORDS = [
        'model', 'inference', 'serving', 'training', 'fine-tuning',
        'finetuning', 'checkpoint', 'quantization', 'embedding',
        'vector database', 'rag', 'diffusion', 'multimodal', 'speech',
        'vision', 'ocr', 'asr', 'tts'
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
        heuristic = self._assess_project(project)

        try:
            prompt = f"""判断以下GitHub项目是否与AI相关。除了模型、训练、推理、Agent、RAG、计算机视觉、语音、多模态，也要把“面向 AI/Agent 的基础设施、运行时、浏览器/CLI/桌面自动化工具、AI-native developer tools”视为 AI 相关项目，而不是只盯着模型类仓库。

项目名：{project.repo_name}
描述：{project.description}
语言：{project.language}

请返回JSON格式：{{"is_ai_related": true/false, "reason": "判断理由"}}"""

            content = call_shared_llm(
                prompt,
                system_prompt="你是一个AI项目识别专家，既能识别显性AI项目，也能识别 AI-native tooling / agent infrastructure / developer tools。",
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
            llm_result = FilterResult(
                is_ai_related=result.get('is_ai_related', False),
                reason=result.get('reason', ''),
                category=heuristic.category,
            )

            if llm_result.is_ai_related:
                if not llm_result.reason.strip():
                    llm_result.reason = heuristic.reason
                return llm_result

            if heuristic.is_ai_related:
                logger.info(
                    "Heuristic override for likely AI-native/tooling project: %s (score=%s)",
                    project.repo_name,
                    heuristic.score,
                )
                return FilterResult(
                    is_ai_related=True,
                    reason=heuristic.reason,
                    category=heuristic.category,
                )

            return llm_result

        except Exception as e:
            self.last_filter_had_llm_failure = True
            logger.warning(f"LLM filter failed for {project.repo_name}, using keyword fallback: {e}")
            return FilterResult(
                is_ai_related=heuristic.is_ai_related,
                reason=(
                    heuristic.reason
                    if heuristic.is_ai_related
                    else "基于项目描述中的关键词判定（LLM暂不可用）"
                ),
                category=heuristic.category,
            )

    def _keyword_fallback(self, text: str) -> bool:
        """Fallback keyword-based detection"""
        return self._assess_text(text).is_ai_related

    def _compose_project_text(self, project: TrendingProject) -> str:
        return " ".join(
            part for part in [
                project.repo_name,
                project.description or "",
                project.language or "",
            ] if part
        )

    def _collect_hits(self, text_lower: str, keywords: list[str]) -> list[str]:
        hits = []
        for keyword in keywords:
            pattern = r"(?<!\\w)" + re.escape(keyword) + r"(?!\\w)"
            if re.search(pattern, text_lower):
                hits.append(keyword)
        return hits

    def _assess_project(self, project: TrendingProject) -> HeuristicAssessment:
        return self._assess_text(self._compose_project_text(project))

    def _assess_text(self, text: str) -> HeuristicAssessment:
        text_lower = (text or "").lower()
        if not text_lower.strip():
            return HeuristicAssessment(False, "", "", 0)

        strong_hits = self._collect_hits(text_lower, self.STRONG_AI_PHRASES)
        core_hits = self._collect_hits(text_lower, self.AI_KEYWORDS)
        agent_hits = self._collect_hits(text_lower, self.AGENT_KEYWORDS)
        tooling_hits = self._collect_hits(text_lower, self.TOOLING_KEYWORDS)
        model_hits = self._collect_hits(text_lower, self.MODEL_KEYWORDS)

        has_strong_signal = bool(strong_hits)
        has_core_signal = bool(core_hits)
        has_agent_signal = bool(agent_hits)
        has_tooling_signal = bool(tooling_hits)
        has_model_signal = bool(model_hits)

        category = ""
        if has_model_signal and has_core_signal:
            category = "model_or_inference"
        elif has_agent_signal and has_tooling_signal:
            category = "ai_native_tooling"
        elif has_tooling_signal and (has_core_signal or has_strong_signal):
            category = "ai_native_tooling"
        elif has_agent_signal:
            category = "agent_workflow"
        elif has_core_signal:
            category = "general_ai"

        score = 0
        score += len(strong_hits) * 3
        score += min(len(core_hits), 3) * 2
        if has_agent_signal:
            score += 2
        if has_tooling_signal:
            score += 1
        if has_model_signal:
            score += 1

        is_ai_related = any([
            has_strong_signal,
            has_model_signal and has_core_signal,
            has_agent_signal and (has_core_signal or has_tooling_signal),
            has_tooling_signal and has_core_signal,
            has_core_signal,
            score >= 5,
        ])

        if not is_ai_related:
            return HeuristicAssessment(False, "", category, score)

        if category == "ai_native_tooling":
            reason = "该项目属于面向 AI 助手 / Agent 的工具链或运行时基础设施，围绕 CLI、浏览器、桌面或工具接入增强 AI 的真实执行能力。"
        elif category == "agent_workflow":
            reason = "该项目聚焦 AI Agent / workflow 编排、记忆或任务执行，属于 AI 应用框架与自动化能力。"
        elif category == "model_or_inference":
            reason = "该项目直接涉及模型、推理、多模态或相关 AI 基础设施，属于明确的 AI 技术栈。"
        else:
            reason = "该项目在描述中命中了明确 AI 信号，属于 AI 相关仓库。"

        return HeuristicAssessment(True, reason, category, score)

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
- <第1条，概括今天最明显的技术热点，20-40字>
- <第2条，概括产品/工程化方向变化，20-40字>
- <第3条，概括值得关注的落地方向，20-40字>

🚀 **搜狐业务价值分析**
- **项目名**
  - **搜索引擎**：<仅在确有价值时填写>
  - **推荐系统**：<仅在确有价值时填写>
  - **AI基础设施**：<仅在确有价值时填写>

硬性要求：
- 只能基于给定项目列表作答，不要编造未出现的项目。
- `## 每日趋势总结` 下必须恰好输出 3 条 bullet，不要写成长段落。
- `🚀 **搜狐业务价值分析**` 只分析确实有明确价值的项目；没有价值的项目不要硬写。若整体都没有明确价值，只输出一条：`- 暂未发现明确可直接落地的项目`。
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
            f"- 热点集中在 AI Agent、LLM 应用与工程工具链，代表项目包括：{top_names}。\n"
            "- 关注点正从单点模型能力转向长期记忆、任务编排与真实流程接入。\n"
            "- 值得优先跟进能直接进入搜索、推荐和内部研发流程的基础能力。\n\n"
            "🚀 **搜狐业务价值分析**\n\n"
            "- **通用落地方向**\n"
            "  - **搜索引擎**：可优先验证查询改写、结构化抽取、结果摘要等能力。\n"
            "  - **推荐系统**：可用于内容标签补全、冷启动特征生成与候选重排增强。\n"
            "  - **AI基础设施**：建议推进统一 LLM 网关、推理成本优化与多模型容灾路由。"
        )
