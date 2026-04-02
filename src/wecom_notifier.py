"""WeCom (Enterprise WeChat) notifier module"""
import requests
import logging
import time
from typing import List
from datetime import date
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult, ProjectAnalysis


logger = logging.getLogger(__name__)


class WeComNotifier:
    """WeCom webhook notifier"""
    PUSH_MARKDOWN_LIMIT = 3800
    RETRY_SHRINK_LIMIT = 2500
    SUMMARY_CONTENT_LIMIT = 2600
    PUSH_TEXT_TRUNCATION_PROFILES = (
        (None, None),
        (240, 260),
        (180, 200),
        (140, 160),
        (100, 120),
    )

    def __init__(self, webhook_url: str):
        """
        Initialize notifier

        Args:
            webhook_url: WeCom webhook URL
        """
        self.webhook_url = webhook_url

    def send_markdown(self, content: str) -> bool:
        """
        Send markdown message to WeCom

        Args:
            content: Markdown content

        Returns:
            True if successful
        """
        message = self._fit_markdown_limit(content)
        success, result = self._send_markdown_once(message)
        if success:
            logger.info("Message sent successfully to WeCom")
            return True

        if result is None:
            return False

        # If WeCom rejects content, auto-shorten and retry once.
        shrunk_message = self._shrink_for_retry(message)
        if shrunk_message == message:
            logger.error(f"WeCom API error: {result}")
            return False

        logger.warning(f"WeCom API error: {result}. Retrying with shorter content...")
        retry_success, retry_result = self._send_markdown_once(shrunk_message)
        if retry_success:
            logger.info("Message sent successfully to WeCom (shortened retry)")
            return True

        logger.error(f"WeCom API error after shortened retry: {retry_result}")
        return False

    def _send_markdown_once(self, content: str) -> tuple[bool, dict | None]:
        """Send one markdown request and return (success, api_result)."""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('errcode') == 0, result
        except requests.RequestException as e:
            logger.error(f"Failed to send WeCom message: {e}")
            return False, None

    def format_daily_report(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = "",
        weekly_references: List[tuple[TrendingProject, FilterResult]] | None = None,
        monthly_references: List[tuple[TrendingProject, FilterResult]] | None = None,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Format daily report without sending"""
        return self._format_daily_message(
            projects_with_reasons,
            report_date,
            summary,
            weekly_references=weekly_references,
            monthly_references=monthly_references,
            analysis_map=analysis_map,
        )

    def format_daily_push_messages(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = "",
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> tuple[str, str]:
        """Format two WeCom messages: trend list + summary/business analysis."""
        trend_message = self._format_daily_top_message(
            projects_with_reasons, report_date, analysis_map=analysis_map
        )
        summary_message = self._format_daily_summary_message(report_date, summary)
        return trend_message, summary_message

    def send_daily_report(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = "",
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> bool:
        """
        Send daily AI trends report

        Args:
            projects_with_reasons: List of (project, filter_result) tuples
            report_date: Date of the report
            summary: Optional LLM-generated summary
            analysis_map: Optional LLM-generated project analysis

        Returns:
            True if successful
        """
        message = self._format_daily_message(
            projects_with_reasons, report_date, summary, analysis_map=analysis_map
        )
        return self.send_markdown(message)

    def send_daily_report_split(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = "",
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> bool:
        """Send daily report as two WeCom markdown messages."""
        trend_message, summary_message = self.format_daily_push_messages(
            projects_with_reasons,
            report_date,
            summary,
            analysis_map=analysis_map,
        )

        if not self.send_markdown(trend_message):
            return False

        # Avoid hitting bot webhook rate limits with immediate back-to-back calls.
        time.sleep(1)
        return self.send_markdown(summary_message)

    def format_weekly_push_messages(
        self,
        report_content: str,
        week_start: date,
        week_end: date,
        summary: str = ""
    ) -> tuple[str, str]:
        """Format two weekly messages: trend report + summary/business analysis."""
        trend_message = self._fit_markdown_limit(report_content)
        summary_message = self._format_weekly_summary_message(week_start, week_end, summary)
        return trend_message, summary_message

    def send_weekly_report_split(
        self,
        report_content: str,
        week_start: date,
        week_end: date,
        summary: str = ""
    ) -> bool:
        """Send weekly report as two WeCom markdown messages."""
        trend_message, summary_message = self.format_weekly_push_messages(
            report_content,
            week_start,
            week_end,
            summary
        )

        if not self.send_markdown(trend_message):
            return False

        # Avoid hitting bot webhook rate limits with immediate back-to-back calls.
        time.sleep(1)
        return self.send_markdown(summary_message)

    def _format_daily_top_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        for_push: bool = True,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Format top projects message in markdown."""
        if for_push:
            message = self._format_push_top_message(
                projects_with_reasons, report_date, analysis_map=analysis_map
            )
            return self._fit_markdown_limit(message)
        return self._format_local_top_message(
            projects_with_reasons, report_date, analysis_map=analysis_map
        )

    def _format_push_top_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Render richer push cards and only shorten when the whole message needs it."""
        last_message = ""
        for description_max, highlight_max in self.PUSH_TEXT_TRUNCATION_PROFILES:
            message = self._render_push_top_message(
                projects_with_reasons,
                report_date,
                description_max=description_max,
                highlight_max=highlight_max,
                analysis_map=analysis_map,
            )
            if len(message.encode("utf-8")) <= self.PUSH_MARKDOWN_LIMIT:
                return message
            last_message = message
        return self._fit_markdown_limit(last_message)

    def _render_push_top_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        description_max: int | None = None,
        highlight_max: int | None = None,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Build a WeCom-friendly project list with optional adaptive shortening."""
        limit = len(projects_with_reasons)
        lines = [
            f"🔥 **今日GitHub AI趋势 Top {limit}**",
            f"📅 {report_date.strftime('%Y-%m-%d')}",
            ""
        ]

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, (project, result) in enumerate(projects_with_reasons):
            emoji = emojis[idx] if idx < len(emojis) else f"{idx+1}."
            stars_str = f"{project.stars:,}"
            growth_str = f"{project.stars_growth:+,}"

            # Use LLM-generated features if available, otherwise fall back
            analysis = (analysis_map or {}).get(project.repo_name)
            if analysis and analysis.features:
                description = analysis.features
            else:
                description = self._build_project_description(project)

            if analysis and analysis.advantages:
                highlight = analysis.advantages
            else:
                highlight = self._normalize_ai_highlight(result.reason, project.description)

            if description_max is not None:
                description = self._truncate_text(description, description_max)
            if highlight_max is not None:
                highlight = self._truncate_text(highlight, highlight_max)

            lines.extend([
                f"{emoji} **{project.repo_name}**｜{project.language or 'Unknown'}｜⭐ {stars_str}｜{growth_str}",
                f"- 📝 {description}",
                f"- 💡 {highlight}",
                f"- 🔗 {project.url}",
                ""
            ])

        lines.extend([
            "---",
            "⏰ 由GitHub-Trend-Bot自动推送"
        ])
        return "\n".join(lines)

    def _format_local_top_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Readable local markdown report for Feishu file delivery."""
        limit = len(projects_with_reasons)
        lines = [
            f"# GitHub AI 趋势 Top {limit}",
            "",
            f"- 日期：{report_date.strftime('%Y-%m-%d')}",
            f"- 样本：当日筛选后的 Top {limit} AI 项目",
            "",
            "## 项目卡片",
            "",
        ]

        for idx, (project, result) in enumerate(projects_with_reasons, start=1):
            language = project.language or "Unknown"
            description = self._build_project_description(project)
            analysis = (analysis_map or {}).get(project.repo_name)

            if analysis and (analysis.features or analysis.advantages):
                features = analysis.features or self._build_project_description(project)
                advantages = analysis.advantages or ""
                disadvantages = analysis.disadvantages or ""
                recommendation = analysis.recommendation or ""
            else:
                normalized_reason = self._normalize_ai_highlight(
                    result.reason, project.description
                )
                project_detail = self._build_local_project_detail(project, normalized_reason)
                features = project_detail['what_it_does']
                advantages = ""
                disadvantages = ""
                recommendation = project_detail['problem_it_solves']

            lines.extend([
                f"### {idx}. {project.repo_name}",
                f"- 语言：{language}",
                f"- 热度：⭐ {project.stars:,} ｜ 今日 {project.stars_growth:+,}",
                f"- 项目描述：{description}",
                f"- 项目特点：{features}",
            ])
            if advantages:
                lines.append(f"- 优势：{advantages}")
            if disadvantages:
                lines.append(f"- 劣势：{disadvantages}")
            if recommendation:
                lines.append(f"- 推荐理由：{recommendation}")
            lines.extend([
                f"- 链接：{project.url}",
                ""
            ])

        lines.extend([
            "---",
            "⏰ 由GitHub-Trend-Bot自动推送"
        ])
        return "\n".join(lines)

    def _format_daily_summary_message(self, report_date: date, summary: str, for_push: bool = True) -> str:
        """Format summary/business analysis message in markdown."""
        summary_content = self._prepare_summary_content(summary, for_push=for_push)

        lines = [
            "📝 **AI智能总结 & 业务价值分析**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n",
            summary_content,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _format_weekly_summary_message(
        self,
        week_start: date,
        week_end: date,
        summary: str,
        for_push: bool = True
    ) -> str:
        """Format weekly summary/business analysis message in markdown."""
        summary_content = self._prepare_summary_content(summary, for_push=for_push)

        lines = [
            "📝 **AI智能总结 & 业务价值分析**",
            f"\n📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}",
            "\n---\n",
            summary_content,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _prepare_summary_content(self, summary: str, for_push: bool = True) -> str:
        """Normalize summary and keep truncation for push-only output."""
        content = summary.strip() if summary and summary.strip() else "（生成总结失败）"
        if not for_push:
            return content

        if len(content.encode("utf-8")) <= self.SUMMARY_CONTENT_LIMIT:
            return content

        suffix = "\n\n（总结较长，已自动精简）"
        suffix_bytes = len(suffix.encode("utf-8"))
        allowed = self.SUMMARY_CONTENT_LIMIT - suffix_bytes
        if allowed <= 0:
            return self._truncate_by_bytes(content, self.SUMMARY_CONTENT_LIMIT)
        return self._truncate_by_bytes(content, allowed) + suffix

    def _shrink_for_retry(self, content: str) -> str:
        """Shrink markdown for one retry attempt after API rejection."""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= self.RETRY_SHRINK_LIMIT:
            return content

        suffix = "\n\n（首次推送失败，已自动精简重发）"
        suffix_bytes = len(suffix.encode("utf-8"))
        allowed = self.RETRY_SHRINK_LIMIT - suffix_bytes
        if allowed <= 0:
            return self._truncate_by_bytes(content, self.RETRY_SHRINK_LIMIT)
        return self._truncate_by_bytes(content, allowed) + suffix

    @staticmethod
    def _normalize_ai_highlight(reason: str, description: str = "") -> str:
        """Rewrite unreadable fallback reasons into a user-facing Chinese highlight."""
        normalized = (reason or "").strip()
        lower_reason = normalized.lower()

        fallback_markers = (
            "keyword-based detection",
            "keyword based detection",
            "llm unavailable"
        )
        if not normalized or any(marker in lower_reason for marker in fallback_markers):
            desc_text = (description or "").lower()
            if any(kw in desc_text for kw in ("agent", "assistant", "copilot", "workflow")):
                area = "AI Agent/智能助手方向"
            elif any(kw in desc_text for kw in ("llm", "gpt", "chat", "rag", "prompt")):
                area = "LLM 应用方向"
            elif any(kw in desc_text for kw in ("vision", "image", "video", "multimodal")):
                area = "多模态/视觉方向"
            else:
                area = "AI 应用或工具方向"

            return f"基于项目描述中的关键词判定，该项目与 {area}相关，建议后续结合 README 做进一步复核。"

        return normalized

    @classmethod
    def _build_project_brief(
        cls,
        project: TrendingProject,
        reason: str
    ) -> str:
        """Build a short, user-facing one-liner for list views."""
        normalized_reason = cls._normalize_ai_highlight(reason, project.description)
        intro = cls._strip_ai_classification_tail(normalized_reason)
        intro = cls._strip_ai_relevance_prefix(intro)
        if intro:
            return intro
        return cls._build_project_description(project)

    @staticmethod
    def _build_project_description(project: TrendingProject) -> str:
        """Return the raw project description or a readable fallback."""
        return (project.description or "").strip() or "GitHub Trending 未提供项目描述。"

    @staticmethod
    def _escape_table_cell(text: str) -> str:
        """Escape markdown table-breaking characters."""
        return (text or "").replace("|", "／").replace("\n", " ").strip()

    @staticmethod
    def _strip_ai_relevance_prefix(text: str) -> str:
        """Remove generic 'this is AI-related' openers for cleaner summaries."""
        cleaned = (text or "").strip()
        prefixes = (
            "该项目与AI高度相关。",
            "该项目与AI相关。",
            "该项目明显与AI相关。",
            "该项目大概率与AI相关。",
            "该项目与AI高度相关",
            "该项目与AI相关",
        )
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        return cleaned

    @staticmethod
    def _strip_reasoning_prefix(text: str) -> str:
        """Remove reasoning-style openings so local docs read like introductions."""
        cleaned = (text or "").strip()
        prefixes = (
            "项目描述中明确提到",
            "项目描述明确提到",
            "项目描述中写明",
            "项目描述明确写明",
            "项目描述中包含",
            "项目描述包含",
            "描述中明确提到",
            "描述中提到",
            "描述明确提到",
            "描述明确写有",
            "描述写明",
            "该项目明确提到",
            "该项目是",
        )
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" ：:，,。")
                break
        return cleaned

    @classmethod
    def _build_local_project_detail(
        cls,
        project: TrendingProject,
        normalized_reason: str
    ) -> dict[str, str]:
        """Generate a fuller explanation for Feishu Markdown attachments."""
        what_it_does = cls._infer_project_overview(project, normalized_reason)
        problem_it_solves = cls._infer_problem_statement(project, what_it_does)
        if not problem_it_solves:
            problem_it_solves = "当前信息更偏项目定位说明，具体要解决的业务问题还需要结合 README 和示例进一步确认。"

        return {
            "what_it_does": what_it_does.strip(),
            "problem_it_solves": problem_it_solves.strip(),
        }

    @staticmethod
    def _strip_ai_classification_tail(reason: str) -> str:
        """Remove generic 'therefore it is AI-related' tails and keep what the project does."""
        text = (reason or "").strip()
        if not text:
            return ""

        split_markers = ("因此", "所以", "由此可见", "因此可以判断", "因此可归类", "因此应归类")
        classification_markers = (
            "AI相关",
            "AI 相关",
            "AI工具",
            "AI 工具",
            "LLM",
            "生态相关",
            "归类",
            "范畴",
            "相关项目"
        )

        for marker in split_markers:
            head, sep, tail = text.partition(marker)
            if sep and any(keyword in tail for keyword in classification_markers):
                text = head.strip("，。；; ")
                break

        if not text:
            return ""
        if text[-1] not in "。！？!?":
            text += "。"
        return text

    @classmethod
    def _infer_project_overview(cls, project: TrendingProject, normalized_reason: str) -> str:
        """Rewrite repo info into a project intro instead of AI classification reasoning."""
        description = cls._build_project_description(project)
        combined = " ".join(
            part for part in (
                project.repo_name,
                project.description,
                normalized_reason,
                project.language,
            )
            if part
        ).lower()

        if any(keyword in combined for keyword in ("pdf", "document", "doc", "parser", "knowledge", "笔记", "研究", "知识", "rag")):
            return f"这是一个面向文档与知识处理的工具，核心是把像 PDF 这类非结构化内容整理成更适合系统、检索或模型继续使用的数据。当前项目描述是：{description}"

        if any(keyword in combined for keyword in ("accounting", "invoice", "receipt", "finance", "trading", "财务", "发票", "收据", "交易")):
            return f"这是一个面向财务或交易场景的智能分析工具/框架，重点是把票据、交易数据或决策流程自动化。当前项目描述是：{description}"

        if any(keyword in combined for keyword in ("robot", "drone", "lidar", "camera", "无人机", "机器人", "激光雷达", "摄像头")):
            return f"这是一个面向机器人或实体硬件平台的智能体控制框架，用来把感知、规划、执行和自然语言指令统一起来。当前项目描述是：{description}"

        if any(keyword in combined for keyword in ("browser", "gui", "page", "web", "automation", "网页", "浏览器")):
            return f"这是一个面向浏览器、网页界面或 GUI 自动化的基础设施项目，适合做自动操作、任务执行和代理控制。当前项目描述是：{description}"

        if any(keyword in combined for keyword in (" api", "sdk", "wrapper", "封装", "接口")):
            return f"这是一个把底层能力做成程序化接口的封装项目，方便开发者在脚本、服务或产品功能里直接接入。当前项目描述是：{description}"

        if any(keyword in combined for keyword in ("design system", "design language", " ui ", " ux ", "设计")):
            return f"这是一个偏设计语言或设计规范方向的项目，目的是让设计输出更稳定、更一致，也更容易被团队或系统复用。当前项目描述是：{description}"

        if any(keyword in combined for keyword in ("assistant", "agent", "copilot", "workflow", "智能体", "工作流", "subagent")):
            return f"这是一个面向 AI 助手、智能体或工作流编排的项目，重点在于把多步骤任务拆开、规划并交给不同角色或模块执行。当前项目描述是：{description}"

        cleaned_reason = cls._strip_ai_classification_tail(normalized_reason)
        cleaned_reason = cls._strip_ai_relevance_prefix(cleaned_reason)
        cleaned_reason = cls._strip_reasoning_prefix(cleaned_reason)
        if cleaned_reason:
            return cleaned_reason

        return f"这是一个当前在 GitHub Trending 上榜的项目。现有公开描述为：{description}"

    @staticmethod
    def _infer_problem_statement(project: TrendingProject, intro: str) -> str:
        """Explain what pain point the project likely addresses."""
        combined = " ".join(
            part for part in (
                project.repo_name,
                project.description,
                intro,
                project.language,
            )
            if part
        ).lower()

        if any(keyword in combined for keyword in ("pdf", "document", "doc", "parser", "knowledge", "笔记", "研究", "知识", "rag")):
            return "主要解决文档、PDF、知识资料难以直接进入 AI/LLM 工作流的问题，让内容更容易被解析、检索、理解和二次利用。"

        if any(keyword in combined for keyword in ("accounting", "invoice", "receipt", "finance", "trading", "财务", "发票", "收据", "交易")):
            return "主要解决财务票据处理、交易分析或金融决策中信息整理成本高、人工判断慢的问题。"

        if any(keyword in combined for keyword in ("robot", "drone", "lidar", "camera", "无人机", "机器人", "激光雷达", "摄像头")):
            return "主要解决机器人或实体设备缺少统一智能体控制层的问题，帮助把感知、规划、执行和自然语言指令串起来。"

        if any(keyword in combined for keyword in ("browser", "gui", "page", "web", "automation", "网页", "浏览器")):
            return "主要解决网页操作、界面控制和重复交互难以自动化的问题，适合浏览器自动化、GUI 操作代理和线上流程执行。"

        if any(keyword in combined for keyword in (" api", "sdk", "wrapper", "封装", "接口")):
            return "主要解决底层能力不好直接接入业务系统的问题，方便在脚本、自动化流程、后端服务或产品功能里快速调用。"

        if any(keyword in combined for keyword in ("design system", "design language", " ui ", " ux ", "设计")):
            return "主要解决 AI 生成结果在设计表达、界面一致性和交互规范上不稳定的问题。"

        if any(keyword in combined for keyword in ("dashboard", "monitor", "news", "intelligence", "aggregation", "监控", "情报", "聚合")):
            return "主要解决信息源分散、热点变化快、不容易持续跟踪的问题，适合做聚合、监控和分析。"

        if any(keyword in combined for keyword in ("assistant", "agent", "copilot", "workflow", "智能体", "工作流", "subagent")):
            return "主要解决多步骤任务需要人工串联、规划和执行的问题，适合复杂流程自动化、AI 助手编排和多人/多角色协作。"

        return ""

    def _format_daily_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = "",
        weekly_references: List[tuple[TrendingProject, FilterResult]] | None = None,
        monthly_references: List[tuple[TrendingProject, FilterResult]] | None = None,
        analysis_map: dict[str, ProjectAnalysis] | None = None,
    ) -> str:
        """Format daily message in markdown"""
        top_message = self._format_daily_top_message(
            projects_with_reasons,
            report_date,
            for_push=False,
            analysis_map=analysis_map,
        )
        summary_message = self._format_daily_summary_message(
            report_date,
            summary,
            for_push=False
        )

        # Keep history output as one markdown document.
        top_without_footer = top_message.rsplit("\n---\n⏰ 由GitHub-Trend-Bot自动推送", 1)[0]
        summary_body = summary_message.split("\n---\n", 1)[-1]
        summary_without_footer = summary_body.rsplit("\n---\n⏰ 由GitHub-Trend-Bot自动推送", 1)[0]

        lines = [
            top_without_footer,
            "\n---\n",
            summary_without_footer,
        ]

        weekly_section = self._format_reference_section("周榜参考", weekly_references or [])
        monthly_section = self._format_reference_section("月榜参考", monthly_references or [])
        if weekly_section or monthly_section:
            lines.append("\n---\n")
            if weekly_section:
                lines.append(weekly_section)
            if monthly_section:
                if weekly_section:
                    lines.append("")
                lines.append(monthly_section)

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")
        return "\n".join(lines)

    def _format_reference_section(
        self,
        title: str,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        limit: int = 5,
    ) -> str:
        """Format bottom appendix sections for weekly/monthly references in local Markdown."""
        if not projects_with_reasons:
            return ""

        lines = [f"## {title}", ""]
        for idx, (project, result) in enumerate(projects_with_reasons[:limit], start=1):
            detail = self._build_local_project_detail(
                project,
                self._normalize_ai_highlight(result.reason, project.description)
            )
            lines.extend([
                f"{idx}. `{project.repo_name}`",
                f"   - 语言：{project.language or 'Unknown'}",
                f"   - Stars：{project.stars:,}",
                f"   - 增长：{project.stars_growth:+,}",
                f"   - 项目介绍：{detail['what_it_does']}",
                "",
            ])
        return "\n".join(lines).rstrip()

    def _fit_markdown_limit(self, content: str) -> str:
        """Ensure markdown content stays within WeCom message UTF-8 byte limit."""
        if len(content.encode("utf-8")) <= self.PUSH_MARKDOWN_LIMIT:
            return content

        suffix = "\n\n（内容过长，已截断）"
        suffix_bytes = len(suffix.encode("utf-8"))
        if suffix_bytes >= self.PUSH_MARKDOWN_LIMIT:
            return self._truncate_by_bytes(suffix, self.PUSH_MARKDOWN_LIMIT)

        allowed_bytes = self.PUSH_MARKDOWN_LIMIT - suffix_bytes
        return self._truncate_by_bytes(content, allowed_bytes) + suffix

    @staticmethod
    def _truncate_by_bytes(text: str, max_bytes: int) -> str:
        """Truncate text by UTF-8 bytes without breaking characters."""
        if max_bytes <= 0:
            return ""
        if len(text.encode("utf-8")) <= max_bytes:
            return text

        left = 0
        right = len(text)
        while left < right:
            mid = (left + right + 1) // 2
            if len(text[:mid].encode("utf-8")) <= max_bytes:
                left = mid
            else:
                right = mid - 1
        return text[:left]

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """Truncate text with ellipsis when necessary."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def send_weekly_report(self, report_content: str) -> bool:
        """
        Send weekly report

        Args:
            report_content: Formatted weekly report markdown

        Returns:
            True if successful
        """
        return self.send_markdown(report_content)
