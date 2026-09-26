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


def test_malformed_lms_write_flag_is_rejected() -> None:
    try:
        assert_lms_read_only("true")  # type: ignore[arg-type]
    except RuntimeError as error:
        assert str(error) == "LMS read-only guard violated"
    else:
        raise AssertionError("expected malformed LMS write flag to be rejected")


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


def test_non_default_ports_and_userinfo_are_rejected() -> None:
    for url in (
        "https://lms.mindx.edu.vn:8443/class",
        "https://teacher:password@lms.mindx.edu.vn/class",
        "https://lms.mindx.edu.vn:not-a-port/class",
    ):
        try:
            assert_allowed_url(url)
        except RuntimeError as error:
            assert str(error) == "Domain is not allowlisted"
        else:
            raise AssertionError("expected unsafe origin to be rejected")


def test_synthetic_localhost_may_use_a_development_port() -> None:
    assert_allowed_url("http://localhost:5173/fixture", mode="synthetic")
    assert_allowed_url("http://127.0.0.1:3000/fixture", mode="synthetic")
