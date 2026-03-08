from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from src.openclaw_notifier import OpenClawNotifier


def test_from_config_defaults_to_disabled_without_target():
    notifier = OpenClawNotifier.from_config({})

    assert notifier.enabled is False
    assert notifier.is_enabled is False
    assert notifier.account == "sohu"


@patch("src.openclaw_notifier.subprocess.run")
def test_send_markdown_file_copies_to_inbound_and_calls_helper(mock_run, tmp_path):
    report = tmp_path / "2026-03-07-daily.md"
    report.write_text("# test report\n", encoding="utf-8")
    media_dir = tmp_path / "media"
    helper_script = tmp_path / "openclaw_feishu_skill.sh"
    helper_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    mock_run.return_value = CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok": true}',
        stderr="",
    )

    notifier = OpenClawNotifier(
        enabled=True,
        account="sohu",
        target="user:ou_test",
        helper_script=str(helper_script),
        media_dir=str(media_dir),
    )

    assert notifier.send_markdown_file(report, title="日报") is True

    copied = media_dir / report.name
    assert copied.exists()
    command = mock_run.call_args.args[0]
    assert command[:3] == ["bash", str(helper_script), "send"]
    assert "--account" in command and "sohu" in command
    assert "--target" in command and "user:ou_test" in command
    assert "--media" in command and str(copied) in command


@patch("src.openclaw_notifier.subprocess.run")
def test_send_markdown_file_returns_false_on_helper_failure(mock_run, tmp_path):
    report = tmp_path / "2026-03-07-daily.md"
    report.write_text("# test report\n", encoding="utf-8")
    helper_script = tmp_path / "openclaw_feishu_skill.sh"
    helper_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    mock_run.return_value = CompletedProcess(
        args=[],
        returncode=1,
        stdout='{"error":"send failed"}',
        stderr="",
    )

    notifier = OpenClawNotifier(
        enabled=True,
        account="sohu",
        target="user:ou_test",
        helper_script=str(helper_script),
        media_dir=str(tmp_path / "media"),
    )

    assert notifier.send_markdown_file(report) is False


@patch("src.openclaw_notifier.subprocess.run")
def test_send_message_calls_helper_without_media(mock_run, tmp_path):
    helper_script = tmp_path / "openclaw_feishu_skill.sh"
    helper_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    mock_run.return_value = CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok": true}',
        stderr="",
    )

    notifier = OpenClawNotifier(
        enabled=True,
        account="sohu",
        target="user:ou_test",
        helper_script=str(helper_script),
        media_dir=str(tmp_path / "media"),
    )

    assert notifier.send_message("LLM failed") is True

    command = mock_run.call_args.args[0]
    assert command[:3] == ["bash", str(helper_script), "send"]
    assert "--message" in command and "LLM failed" in command
    assert "--media" not in command
