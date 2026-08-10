from mindx_runner.guardrails import (
    ALLOWED_PRODUCTION_HOSTS,
    assert_allowed_url,
    assert_lms_read_only,
    can_run_automation,
)


def test_kill_switch_blocks_automation() -> None:
    assert can_run_automation(False) is False


def test_enabled_kill_switch_allows_synthetic_runner() -> None:
    assert can_run_automation(True) is True


def test_lms_write_flag_is_rejected() -> None:
    try:
        assert_lms_read_only(True)
    except RuntimeError as error:
        assert str(error) == "LMS read-only guard violated"
    else:
        raise AssertionError("expected LMS read-only guard to reject mutation")


def test_production_hosts_are_explicit() -> None:
    assert ALLOWED_PRODUCTION_HOSTS == frozenset(
        {"teachingmindx.top", "lms.mindx.edu.vn"}
    )
    assert_allowed_url("https://lms.mindx.edu.vn/class")


def test_arbitrary_domain_is_rejected() -> None:
    try:
        assert_allowed_url("https://example.invalid")
    except RuntimeError as error:
        assert str(error) == "Domain is not allowlisted"
    else:
        raise AssertionError("expected arbitrary domain to be rejected")
