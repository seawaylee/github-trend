import logging
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from src.openclaw_notifier import OpenClawNotifier


def test_from_config_defaults_to_disabled_without_target():
    notifier = OpenClawNotifier.from_config({})

    assert notifier.enabled is False
    assert notifier.is_enabled is False
    assert notifier.account == "sohu"
    assert notifier.agent == "sohu"
    assert notifier.timeout == 60
    assert notifier.agent_timeout == 240


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
def test_send_markdown_file_falls_back_to_agent_when_direct_send_fails(mock_run, tmp_path, caplog):
    report = tmp_path / "2026-03-07-daily.md"
    report.write_text("# test report\n", encoding="utf-8")
    helper_script = tmp_path / "openclaw_feishu_skill.sh"
    helper_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    mock_run.side_effect = [
        CompletedProcess(
            args=[],
            returncode=1,
            stdout='{"error":"send failed"}',
            stderr="",
        ),
        CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
        ),
    ]

    notifier = OpenClawNotifier(
        enabled=True,
        account="sohu",
        target="user:ou_test",
        helper_script=str(helper_script),
        media_dir=str(tmp_path / "media"),
    )

    with caplog.at_level(logging.INFO):
        assert notifier.send_markdown_file(report) is True

    assert mock_run.call_count == 2
    direct_command = mock_run.call_args_list[0].args[0]
    fallback_command = mock_run.call_args_list[1].args[0]
    assert direct_command[:3] == ["bash", str(helper_script), "send"]
    assert fallback_command[:3] == ["bash", str(helper_script), "send-via-agent"]
    assert "--agent" in fallback_command and "sohu" in fallback_command
    assert "--timeout" in fallback_command and "240" in fallback_command
    assert "falling back to send-via-agent" in caplog.text


@patch("src.openclaw_notifier.subprocess.run")
def test_send_markdown_file_returns_false_when_direct_and_fallback_fail(mock_run, tmp_path):
    report = tmp_path / "2026-03-07-daily.md"
    report.write_text("# test report\n", encoding="utf-8")
    helper_script = tmp_path / "openclaw_feishu_skill.sh"
    helper_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    mock_run.side_effect = [
        CompletedProcess(
            args=[],
            returncode=1,
            stdout='{"error":"send failed"}',
            stderr="",
        ),
        CompletedProcess(
            args=[],
            returncode=1,
            stdout='{"error":"agent send failed"}',
            stderr="",
        ),
    ]

    notifier = OpenClawNotifier(
        enabled=True,
        account="sohu",
        target="user:ou_test",
        helper_script=str(helper_script),
        media_dir=str(tmp_path / "media"),
    )

    assert notifier.send_markdown_file(report) is False
    assert mock_run.call_count == 2


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
