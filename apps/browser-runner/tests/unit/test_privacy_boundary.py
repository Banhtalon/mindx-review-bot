from mindx_runner.privacy_boundary import assert_agent_page_safe


def test_navigation_page_without_roster_can_reach_agent() -> None:
    page = '<main data-class-code="SYN-CLASS-01"><h1>Session 3</h1></main>'

    assert assert_agent_page_safe(page) == page


def test_roster_page_is_blocked_from_navigation_agent() -> None:
    page = '<div data-student-id="syn-01">Student Alpha</div>'

    try:
        assert_agent_page_safe(page)
    except RuntimeError as error:
        assert str(error) == "Navigation agent cannot receive roster page"
    else:
        raise AssertionError("expected roster page to be blocked")
