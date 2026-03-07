from unittest.mock import patch

from src.shared_llm import call_shared_llm


def test_call_shared_llm_normalizes_blank_base_url_and_api_key_to_none():
    fake_module = type(
        "FakeModule",
        (),
        {"chat_completion_or_raise": staticmethod(lambda *_args, **kwargs: kwargs)},
    )

    with patch("src.shared_llm._load_shared_llm_module", return_value=fake_module):
        kwargs = call_shared_llm(
            "hello",
            system_prompt="system",
            base_url=" ",
            api_key=" ",
        )

    assert kwargs["base_url"] is None
    assert kwargs["api_key"] is None
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["reasoning_effort"] == "xhigh"
