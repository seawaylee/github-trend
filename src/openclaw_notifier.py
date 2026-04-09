"""OpenClaw Feishu notifier for sending local report files as attachments."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


DEFAULT_CHANNEL = "feishu"
DEFAULT_ACCOUNT = "sohu"
DEFAULT_TITLE = "GitHub AI 趋势日报（自动推送）"
DEFAULT_TIMEOUT = 60
DEFAULT_AGENT_TIMEOUT = 240
DEFAULT_HELPER_SCRIPT = (
    Path.home()
    / "app"
    / "git"
    / "core-common-tools"
    / "scripts"
    / "openclaw_feishu_skill.sh"
)
DEFAULT_MEDIA_DIR = Path.home() / ".openclaw" / "media" / "inbound"


@dataclass
class OpenClawNotifier:
    enabled: bool = False
    channel: str = DEFAULT_CHANNEL
    account: str = DEFAULT_ACCOUNT
    target: str = ""
    title: str = DEFAULT_TITLE
    timeout: int = DEFAULT_TIMEOUT
    agent_timeout: int = DEFAULT_AGENT_TIMEOUT
    helper_script: str = str(DEFAULT_HELPER_SCRIPT)
    openclaw_bin: str = ""
    media_dir: str = str(DEFAULT_MEDIA_DIR)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "OpenClawNotifier":
        config = config or {}
        return cls(
            enabled=bool(config.get("enabled", False)),
            channel=str(config.get("channel") or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL,
            account=str(config.get("account") or DEFAULT_ACCOUNT).strip() or DEFAULT_ACCOUNT,
            target=str(config.get("target") or "").strip(),
            title=str(config.get("title") or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
            timeout=max(10, int(config.get("timeout") or DEFAULT_TIMEOUT)),
            agent_timeout=max(30, int(config.get("agent_timeout") or DEFAULT_AGENT_TIMEOUT)),
            helper_script=str(config.get("helper_script") or DEFAULT_HELPER_SCRIPT).strip(),
            openclaw_bin=str(config.get("openclaw_bin") or "").strip(),
            media_dir=str(config.get("media_dir") or DEFAULT_MEDIA_DIR).strip(),
        )

    @property
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.target)

    def send_message(self, message: str) -> bool:
        if not self.is_enabled:
            logger.info("OpenClaw notifier disabled or target missing, skip send")
            return True

        helper_script = self._resolve_helper_script()
        if helper_script is None:
            return False

        command = self._build_helper_command(
            helper_script=helper_script,
            subcommand="send",
            message=str(message or "").strip(),
            timeout_seconds=self.timeout,
        )
        proc = self._run_helper_command(
            command,
            timeout_seconds=self.timeout,
            execute_error_label="OpenClaw text send",
        )
        if proc is None:
            return False

        if proc.returncode == 0:
            logger.info("OpenClaw text message sent successfully")
            return True

        logger.error(
            "OpenClaw text send failed (code=%s): %s",
            proc.returncode,
            self._summarize_failure(proc.stdout, proc.stderr),
        )
        return False

    def send_markdown_file(self, report_path: str | Path, title: str = "") -> bool:
        if not self.is_enabled:
            logger.info("OpenClaw notifier disabled or target missing, skip send")
            return True

        source = Path(report_path)
        if not source.exists() or not source.is_file():
            logger.error("OpenClaw report file not found: %s", source)
            return False

        helper_script = self._resolve_helper_script()
        if helper_script is None:
            return False

        try:
            media_path = self._prepare_media_file(source)
        except Exception as exc:
            logger.error("Failed to prepare OpenClaw media file: %s", exc)
            return False

        message = str(title or self.title)
        command = self._build_helper_command(
            helper_script=helper_script,
            subcommand="send",
            message=message,
            media_path=media_path,
            timeout_seconds=self.timeout,
        )
        proc = self._run_helper_command(
            command,
            timeout_seconds=self.timeout,
            execute_error_label="OpenClaw attachment send",
        )
        if proc is not None and proc.returncode == 0:
            logger.info("OpenClaw markdown attachment sent successfully")
            return True

        if proc is not None:
            logger.error(
                "OpenClaw attachment send failed (code=%s): %s",
                proc.returncode,
                self._summarize_failure(proc.stdout, proc.stderr),
            )

        logger.info(
            "OpenClaw attachment direct send failed; retrying with longer timeout "
            "(timeout=%ss)",
            self.agent_timeout,
        )
        fallback_command = self._build_helper_command(
            helper_script=helper_script,
            subcommand="send",
            message=message,
            media_path=media_path,
            timeout_seconds=self.agent_timeout,
        )
        fallback_proc = self._run_helper_command(
            fallback_command,
            timeout_seconds=self.agent_timeout,
            execute_error_label="OpenClaw attachment fallback send",
        )
        if fallback_proc is None:
            return False

        if fallback_proc.returncode == 0:
            logger.info("OpenClaw markdown attachment sent successfully via fallback send")
            return True

        logger.error(
            "OpenClaw attachment fallback send failed (code=%s): %s",
            fallback_proc.returncode,
            self._summarize_failure(fallback_proc.stdout, fallback_proc.stderr),
        )
        return False

    def _resolve_helper_script(self) -> Path | None:
        helper_script = Path(self.helper_script)
        if helper_script.exists() and helper_script.is_file():
            return helper_script
        logger.error("OpenClaw helper script not found: %s", helper_script)
        return None

    def _build_helper_command(
        self,
        *,
        helper_script: Path,
        subcommand: str,
        message: str,
        timeout_seconds: int,
        media_path: Path | None = None,
    ) -> list[str]:
        command = [
            "bash",
            str(helper_script),
            subcommand,
            "--message",
            message,
            "--channel",
            self.channel,
            "--account",
            self.account,
            "--target",
            self.target,
            "--timeout",
            str(timeout_seconds),
        ]
        if media_path is not None:
            command.extend(["--media", str(media_path)])
        if self.openclaw_bin:
            command.extend(["--openclaw-bin", self.openclaw_bin])
        return command

    @staticmethod
    def _run_helper_command(
        command: list[str],
        *,
        timeout_seconds: int,
        execute_error_label: str,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 20,
            )
        except Exception as exc:
            logger.error("%s failed to execute: %s", execute_error_label, exc)
            return None

    def _prepare_media_file(self, source: Path) -> Path:
        media_dir = Path(self.media_dir).expanduser()
        media_dir.mkdir(parents=True, exist_ok=True)
        destination = media_dir / source.name
        shutil.copyfile(source, destination)
        return destination

    @staticmethod
    def _summarize_failure(stdout: str, stderr: str) -> str:
        payload = OpenClawNotifier._extract_json_payload(stdout)
        error = str(payload.get("error") or payload.get("message") or "").strip()
        if error:
            return error
        stderr = (stderr or "").strip()
        if stderr:
            return stderr.splitlines()[-1][:400]
        stdout = (stdout or "").strip()
        if stdout:
            return stdout.splitlines()[-1][:400]
        return "unknown error"

    @staticmethod
    def _extract_json_payload(raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if not line.lstrip().startswith("{"):
                continue
            candidate = "\n".join(lines[index:])
            try:
                payload = json.loads(candidate)
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return {}
