from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import tz

from .openclaw_notifier import OpenClawNotifier
from .shared_llm import call_shared_llm


logger = logging.getLogger(__name__)


@dataclass
class SkillWatchConfig:
    name: str
    url: str
    request_timeout: int = 30
    state_dir: str = "data/skill_watch"
    report_dir: str = "history/skill_watch"
    notify_on_no_change: bool = False
    notify_on_first_run: bool = False
    timezone: str = "Asia/Shanghai"


def load_skill_watch_config(config_path: str | Path) -> dict[str, Any]:
    config_file = Path(config_path).expanduser().resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with config_file.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    if "watch" not in config:
        raise ValueError("Missing required configuration section: watch")
    if "logging" not in config:
        raise ValueError("Missing required configuration section: logging")

    watch = config["watch"]
    for key in ["name", "url"]:
        if not str(watch.get(key) or "").strip():
            raise ValueError(f"Missing required watch field: {key}")

    return config


def setup_logging(level: str, file_path: str | Path) -> None:
    log_file = Path(file_path).expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )


def _resolve_path(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _js_unescape(raw: str | None) -> str:
    if raw is None:
        return ""
    try:
        return json.loads(f'"{raw}"')
    except Exception:
        return raw.encode("utf-8", "ignore").decode("unicode_escape", "ignore")


def _first_regex(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    return match.group(1) if match else ""


def _extract_stats(html: str) -> dict[str, int]:
    match = re.search(
        r"stats:\$R\[\d+\]=\{comments:(\d+),downloads:(\d+),installsAllTime:(\d+),installsCurrent:(\d+),stars:(\d+),versions:(\d+)\}",
        html,
    )
    if not match:
        return {}
    comments, downloads, installs_all_time, installs_current, stars, versions = match.groups()
    return {
        "comments": int(comments),
        "downloads": int(downloads),
        "installs_all_time": int(installs_all_time),
        "installs_current": int(installs_current),
        "stars": int(stars),
        "versions": int(versions),
    }


def _extract_reason_codes(html: str) -> list[str]:
    raw = _first_regex(r"reasonCodes:\$R\[\d+\]=\[(.*?)\]", html)
    if not raw:
        return []
    return re.findall(r'"([^"]+)"', raw)


def _extract_dimensions(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    labels = soup.select("div.dimension-row")
    for row in labels:
        label = _clean_text(row.select_one("div.dimension-label").get_text(" ", strip=True) if row.select_one("div.dimension-label") else "")
        detail = _clean_text(row.select_one("div.dimension-detail").get_text(" ", strip=True) if row.select_one("div.dimension-detail") else "")
        if label or detail:
            rows.append({"label": label, "detail": detail})
    return rows


def fetch_skill_snapshot(url: str, *, timeout: int = 30) -> dict[str, Any]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
    )
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "lxml")

    markdown_el = soup.select_one("div.tab-body div.markdown")
    markdown_text = markdown_el.get_text("\n", strip=True) if markdown_el else ""

    pending_banner = soup.select_one("div.pending-banner-content")
    latest_tag = soup.select_one("div.skill-tag-row .tag-meta")
    version_el = soup.select_one("div.skill-version-pill strong")
    title_el = soup.select_one("h1.section-title")
    subtitle_el = soup.select_one("p.section-subtitle")

    moderation_updated_at_ms = _first_regex(r"moderationInfo:\$R\[\d+\]=\{.*?updatedAt:(\d+),verdict:", html)
    latest_created_at_ms = _first_regex(r"latestVersion:\$R\[\d+\]=\{.*?createdAt:(\d+),createdBy:", html)

    snapshot = {
        "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "url": response.url,
        "status_code": response.status_code,
        "title": _clean_text(title_el.get_text(" ", strip=True) if title_el else ""),
        "summary": _clean_text(subtitle_el.get_text(" ", strip=True) if subtitle_el else ""),
        "current_version": _clean_text((version_el.get_text(" ", strip=True) if version_el else "").replace("v ", "v")),
        "latest_tag": _clean_text(latest_tag.get_text(" ", strip=True) if latest_tag else ""),
        "latest_version_id": _first_regex(r'latestVersionId:"([^"]+)"', html),
        "owner": _first_regex(r'owner:\$R\[\d+\]=\{.*?displayName:"([^"]+)"', html),
        "license": _first_regex(r'<div class="tag tag-accent">([^<]+)</div>', html),
        "download_url": _first_regex(r'href="(https://[^"]+/api/v1/download\?slug=[^"]+)"', html),
        "canonical_url": _first_regex(r'<link rel="canonical" href="([^"]+)"', html),
        "changelog": _js_unescape(_first_regex(r'changelog:"((?:\\.|[^"])*)"', html)),
        "fingerprint": _first_regex(r'fingerprint:"([0-9a-f]+)"', html),
        "skill_sha256": _first_regex(r'files:\$R\[\d+\]=\[\$R\[\d+\]=\{contentType:"text/markdown",path:"SKILL\.md",sha256:"([0-9a-f]+)"', html),
        "skill_size": int(_first_regex(r'path:"SKILL\.md",sha256:"[0-9a-f]+",size:(\d+)', html) or 0),
        "skill_text_sha256": _sha256_text(markdown_text),
        "skill_text": markdown_text,
        "stats": _extract_stats(html),
        "moderation": {
            "banner": _clean_text(pending_banner.get_text(" ", strip=True) if pending_banner else ""),
            "is_suspicious": "isSuspicious:!0" in html,
            "verdict": _first_regex(r'moderationInfo:\$R\[\d+\]=\{.*?verdict:"([^"]+)"', html),
            "summary": _js_unescape(_first_regex(r'moderationInfo:\$R\[\d+\]=\{.*?summary:"((?:\\.|[^"])*)"', html)),
            "reason_codes": _extract_reason_codes(html),
            "updated_at_ms": int(moderation_updated_at_ms) if moderation_updated_at_ms else 0,
        },
        "latest_version_created_at_ms": int(latest_created_at_ms) if latest_created_at_ms else 0,
        "scan_dimensions": _extract_dimensions(soup),
        "raw_html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }
    return snapshot


def _format_timestamp(ms: int, timezone_name: str) -> str:
    if not ms:
        return ""
    target_tz = tz.gettz(timezone_name) or tz.gettz("Asia/Shanghai")
    return datetime.fromtimestamp(ms / 1000, tz=tz.UTC).astimezone(target_tz).strftime("%Y-%m-%d %H:%M:%S %Z")


def summarize_changes(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"status": "first_run", "changes": ["首次建立监控基线"]}

    changes: list[str] = []

    for key, label in [
        ("current_version", "版本"),
        ("latest_version_id", "版本 ID"),
        ("changelog", "更新说明"),
        ("fingerprint", "技能指纹"),
        ("skill_sha256", "SKILL.md 文件哈希"),
        ("skill_text_sha256", "SKILL.md 文本哈希"),
    ]:
        old = previous.get(key)
        new = current.get(key)
        if old != new:
            changes.append(f"{label}变化：{old or '空'} -> {new or '空'}")

    prev_mod = previous.get("moderation") or {}
    curr_mod = current.get("moderation") or {}
    for key, label in [
        ("verdict", "安全判定"),
        ("summary", "安全摘要"),
    ]:
        if prev_mod.get(key) != curr_mod.get(key):
            changes.append(f"{label}变化：{prev_mod.get(key) or '空'} -> {curr_mod.get(key) or '空'}")
    if (prev_mod.get("reason_codes") or []) != (curr_mod.get("reason_codes") or []):
        changes.append(
            "安全原因码变化："
            f"{', '.join(prev_mod.get('reason_codes') or ['空'])} -> {', '.join(curr_mod.get('reason_codes') or ['空'])}"
        )

    prev_stats = previous.get("stats") or {}
    curr_stats = current.get("stats") or {}
    for key, label in [
        ("downloads", "下载量"),
        ("installs_current", "当前安装量"),
        ("installs_all_time", "累计安装量"),
        ("stars", "收藏量"),
        ("versions", "版本数"),
        ("comments", "评论数"),
    ]:
        old = prev_stats.get(key)
        new = curr_stats.get(key)
        if old != new and (old is not None or new is not None):
            delta = None if old is None or new is None else new - old
            delta_text = "" if delta is None else f"（Δ {delta:+d}）"
            changes.append(f"{label}变化：{old if old is not None else '空'} -> {new if new is not None else '空'}{delta_text}")

    if not changes:
        return {"status": "no_change", "changes": []}
    return {"status": "changed", "changes": changes}


def _fallback_summary(name: str, diff: dict[str, Any], current: dict[str, Any], timezone_name: str) -> str:
    stats = current.get("stats") or {}
    moderation = current.get("moderation") or {}
    lines = [
        f"结论：{'检测到更新' if diff['status'] == 'changed' else '已建立首个基线' if diff['status'] == 'first_run' else '今天未发现变化'}。",
        f"当前版本：{current.get('current_version') or '未知'}，版本 ID：{current.get('latest_version_id') or '未知'}。",
        f"当前安全判定：{moderation.get('verdict') or '未知'}；原因码：{', '.join(moderation.get('reason_codes') or ['无'])}。",
        (
            "当前指标："
            f"downloads={stats.get('downloads', 'NA')}，"
            f"installs_current={stats.get('installs_current', 'NA')}，"
            f"installs_all_time={stats.get('installs_all_time', 'NA')}，"
            f"stars={stats.get('stars', 'NA')}。"
        ),
    ]
    updated_at = _format_timestamp(moderation.get("updated_at_ms") or 0, timezone_name)
    if updated_at:
        lines.append(f"安全扫描更新时间：{updated_at}。")
    if diff.get("changes"):
        lines.append("关键变化：")
        lines.extend([f"- {item}" for item in diff["changes"][:12]])
    return "\n".join(lines)


def _llm_summary(config: dict[str, Any], name: str, diff: dict[str, Any], previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    ai_config = config.get("ai") or {}
    if not ai_config.get("api_key"):
        raise RuntimeError("AI api_key not configured")

    payload = {
        "name": name,
        "diff": diff,
        "previous": previous,
        "current": current,
    }
    prompt = (
        "你是一个代码与安全监控助手。请基于下面这个 ClawHub skill 页面快照 diff，"
        "输出一份简洁、准确的中文更新摘要。\n"
        "要求：\n"
        "1. 先给一句结论。\n"
        "2. 再列出 3-6 条关键变化。\n"
        "3. 明确区分'内容变化'、'分发/安装数据变化'、'安全扫描结果变化'。\n"
        "4. 如果只是基线建立或无变化，要明确说明。\n"
        "5. 不要编造页面上没有的信息。\n\n"
        f"数据：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return call_shared_llm(
        prompt,
        system_prompt="你擅长把网页版本变更与安全扫描结果总结成简洁中文播报。",
        model=str(ai_config.get("model") or "gpt-5.4"),
        timeout=int(ai_config.get("timeout") or 120),
        base_url=str(ai_config.get("base_url") or "").strip() or None,
        api_key=str(ai_config.get("api_key") or "").strip() or None,
        reasoning_effort=str(ai_config.get("reasoning_effort") or "xhigh"),
        temperature=0.2,
    ).strip()


def build_summary(config: dict[str, Any], name: str, diff: dict[str, Any], previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    timezone_name = ((config.get("watch") or {}).get("timezone") or "Asia/Shanghai")
    try:
        summary = _llm_summary(config, name, diff, previous, current)
        if summary:
            return summary
    except Exception as exc:
        logger.warning("LLM summary failed, fallback to template: %s", exc)
    return _fallback_summary(name, diff, current, timezone_name)


def write_report(report_path: str | Path, *, name: str, diff: dict[str, Any], summary: str, current: dict[str, Any], previous: dict[str, Any] | None, timezone_name: str) -> Path:
    report_file = Path(report_path).expanduser()
    report_file.parent.mkdir(parents=True, exist_ok=True)
    moderation = current.get("moderation") or {}
    stats = current.get("stats") or {}

    lines = [
        f"# {name} 监控报告",
        "",
        f"- 监控时间：{datetime.now(tz.gettz(timezone_name) or tz.gettz('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 目标地址：{current.get('url')}",
        f"- 检测结果：{diff.get('status')}",
        "",
        "## 中文摘要",
        "",
        summary.strip(),
        "",
        "## 关键变化",
        "",
    ]
    if diff.get("changes"):
        lines.extend([f"- {item}" for item in diff["changes"]])
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 当前快照",
            "",
            f"- 标题：{current.get('title')}",
            f"- 当前版本：{current.get('current_version')}",
            f"- 版本 ID：{current.get('latest_version_id')}",
            f"- 更新说明：{current.get('changelog') or '空'}",
            f"- 安全判定：{moderation.get('verdict') or '未知'}",
            f"- 原因码：{', '.join(moderation.get('reason_codes') or ['无'])}",
            f"- 安全摘要：{moderation.get('summary') or '空'}",
            f"- 安全扫描更新时间：{_format_timestamp(moderation.get('updated_at_ms') or 0, timezone_name) or '空'}",
            f"- 下载量：{stats.get('downloads', 'NA')}",
            f"- 当前安装量：{stats.get('installs_current', 'NA')}",
            f"- 累计安装量：{stats.get('installs_all_time', 'NA')}",
            f"- 收藏量：{stats.get('stars', 'NA')}",
            "",
            "## 对比基线（原始 JSON）",
            "",
            "```json",
            json.dumps({"previous": previous, "current": current}, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )

    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file


def run_skill_watch(config_path: str | Path, *, dry_run: bool = False, force_notify: bool = False) -> dict[str, Any]:
    config = load_skill_watch_config(config_path)
    setup_logging((config.get("logging") or {}).get("level") or "INFO", (config.get("logging") or {}).get("file") or "logs/skill_watch.log")

    watch = SkillWatchConfig(
        name=str(config["watch"]["name"]).strip(),
        url=str(config["watch"]["url"]).strip(),
        request_timeout=max(5, int(config["watch"].get("request_timeout") or 30)),
        state_dir=str(config["watch"].get("state_dir") or "data/skill_watch"),
        report_dir=str(config["watch"].get("report_dir") or "history/skill_watch"),
        notify_on_no_change=bool(config["watch"].get("notify_on_no_change", False)),
        notify_on_first_run=bool(config["watch"].get("notify_on_first_run", False)),
        timezone=str(config["watch"].get("timezone") or "Asia/Shanghai"),
    )

    state_dir = _resolve_path(watch.state_dir)
    report_dir = _resolve_path(watch.report_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    latest_snapshot_path = state_dir / "latest.json"
    previous = None
    if latest_snapshot_path.exists():
        previous = json.loads(latest_snapshot_path.read_text(encoding="utf-8"))

    current = fetch_skill_snapshot(watch.url, timeout=watch.request_timeout)
    diff = summarize_changes(previous, current)

    latest_snapshot_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

    should_notify = force_notify
    if diff["status"] == "changed":
        should_notify = True
    elif diff["status"] == "first_run" and watch.notify_on_first_run:
        should_notify = True
    elif diff["status"] == "no_change" and watch.notify_on_no_change:
        should_notify = True

    now_local = datetime.now(tz.gettz(watch.timezone) or tz.gettz("Asia/Shanghai"))
    report_path = report_dir / f"{now_local.strftime('%Y-%m-%d-%H%M%S')}-using-superpowers.md"
    summary = build_summary(config, watch.name, diff, previous, current)
    wrote_report = False

    if should_notify or diff["status"] in {"changed", "first_run"}:
        write_report(
            report_path,
            name=watch.name,
            diff=diff,
            summary=summary,
            current=current,
            previous=previous,
            timezone_name=watch.timezone,
        )
        wrote_report = True

    notifier = OpenClawNotifier.from_config(config.get("openclaw"))
    sent = False
    if should_notify and wrote_report and not dry_run:
        sent = notifier.send_markdown_file(report_path, title=f"{watch.name} 监控更新")
        if not sent:
            sent = notifier.send_message(summary[:800])
    elif dry_run:
        logger.info("Dry run enabled, skip notification send")

    result = {
        "status": diff["status"],
        "change_count": len(diff.get("changes") or []),
        "report_path": str(report_path) if wrote_report else "",
        "latest_snapshot_path": str(latest_snapshot_path),
        "sent": sent,
        "dry_run": dry_run,
        "summary": summary,
    }
    logger.info("Skill watch result: %s", result)
    return result
