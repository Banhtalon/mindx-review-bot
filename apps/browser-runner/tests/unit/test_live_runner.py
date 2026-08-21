import base64

import pytest

from mindx_runner.live_runner import (
    LiveConfigError,
    load_live_config,
    safe_error_code,
    validate_job_id,
    validate_runner_id,
)

KEY = base64.b64encode(bytes(range(32))).decode("ascii")
BASE_ENV = {
    "AUTOMATION_ENABLED": "true",
    "MVP_LMS_WRITE_ENABLED": "false",
    "JOB_ID": "00000000-0000-4000-8000-000000000001",
    "RUNNER_ID": "runner-test-01",
    "JOB_TYPE": "sync_teaching",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": "server-secret",
    "BROWSER_STATE_ENCRYPTION_KEY": KEY,
    "TEACHING_USERNAME": "teacher@example.invalid",
    "TEACHING_PASSWORD": "teaching-password",
    "LMS_USERNAME": "lms@example.invalid",
    "LMS_PASSWORD": "lms-password",
}


def test_load_live_config_validates_flags_and_key_without_secret_repr() -> None:
    config = load_live_config(BASE_ENV)

    assert config.job_id == BASE_ENV["JOB_ID"]
    assert config.runner_id == BASE_ENV["RUNNER_ID"]
    assert config.job_type == "sync_teaching"
    assert config.browser_state_key == bytes(range(32))
    assert "server-secret" not in repr(config)
    assert "teaching-password" not in repr(config)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AUTOMATION_ENABLED", "false"),
        ("MVP_LMS_WRITE_ENABLED", "true"),
        ("JOB_TYPE", "unsupported"),
        ("BROWSER_STATE_ENCRYPTION_KEY", "not-base64"),
    ],
)
def test_load_live_config_rejects_unsafe_values(name: str, value: str) -> None:
    environment = {**BASE_ENV, name: value}

    with pytest.raises(LiveConfigError) as error:
        load_live_config(environment)

    assert error.value.code == "LIVE_CONFIG_INVALID"
    assert value not in str(error.value)


def test_load_live_config_rejects_missing_required_secret() -> None:
    environment = {
        key: value for key, value in BASE_ENV.items() if key != "TEACHING_PASSWORD"
    }

    with pytest.raises(LiveConfigError) as error:
        load_live_config(environment)

    assert error.value.code == "LIVE_CONFIG_INVALID"
    assert "TEACHING_PASSWORD" in str(error.value)


def test_validate_job_id_accepts_uuid_and_rejects_other_values() -> None:
    assert validate_job_id(BASE_ENV["JOB_ID"]) == BASE_ENV["JOB_ID"]

    with pytest.raises(LiveConfigError):
        validate_job_id("not-a-uuid")


def test_validate_runner_id_accepts_safe_identifier_and_rejects_unsafe_values() -> None:
    assert validate_runner_id(BASE_ENV["RUNNER_ID"]) == BASE_ENV["RUNNER_ID"]

    for value in ("", "runner/name", "runner with spaces", "x" * 65):
        with pytest.raises(LiveConfigError):
            validate_runner_id(value)


def test_load_live_config_requires_runner_id() -> None:
    environment = {key: value for key, value in BASE_ENV.items() if key != "RUNNER_ID"}

    with pytest.raises(LiveConfigError) as error:
        load_live_config(environment)

    assert error.value.code == "LIVE_CONFIG_INVALID"
    assert "RUNNER_ID" in str(error.value)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.supabase.co/rest/v1",
        "https://example.supabase.co:443",
        "https://example.supabase.co:not-a-port",
        "https://user:password@example.supabase.co",
        "https://example.supabase.co?query=1",
        "https://example.supabase.co#fragment",
    ],
)
def test_load_live_config_rejects_non_origin_supabase_url(value: str) -> None:
    with pytest.raises(LiveConfigError):
        load_live_config({**BASE_ENV, "SUPABASE_URL": value})


def test_load_live_config_only_requires_credentials_for_job_type() -> None:
    teaching_env = {
        key: value
        for key, value in BASE_ENV.items()
        if key not in {"LMS_USERNAME", "LMS_PASSWORD"}
    }
    lms_env = {
        **BASE_ENV,
        "JOB_TYPE": "read_lms_pending",
        "TEACHING_USERNAME": "",
        "TEACHING_PASSWORD": "",
    }
    lms_env.pop("TEACHING_USERNAME")
    lms_env.pop("TEACHING_PASSWORD")

    assert load_live_config(teaching_env).lms_username == ""
    assert load_live_config(lms_env).teaching_username == ""


def test_safe_error_code_does_not_return_arbitrary_exception_text() -> None:
    assert safe_error_code(LiveConfigError("hidden-value")) == "LIVE_CONFIG_INVALID"
    assert safe_error_code(RuntimeError("password=hidden")) == "RUNNER_FAILED"


def test_safe_error_code_rejects_unknown_uppercase_codes() -> None:
    class UnknownCodeError(RuntimeError):
        code = "PII_VALUE"

    assert safe_error_code(UnknownCodeError()) == "RUNNER_FAILED"
