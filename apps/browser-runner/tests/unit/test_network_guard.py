import pytest

from mindx_runner.network_guard import classify_request


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_read_methods_are_allowed_on_exact_production_hosts(method: str) -> None:
    decision = classify_request(method, "https://lms.mindx.edu.vn/classes/abc")

    assert decision.allowed is True
    assert decision.code == "ALLOWED_READ"


def test_explicit_login_post_is_allowed_only_for_configured_path() -> None:
    decision = classify_request(
        "POST",
        "https://lms.mindx.edu.vn/auth/login",
        body=b"username=teacher&password=hidden",
        content_type="application/x-www-form-urlencoded",
        login_paths=("/auth/login",),
    )

    assert decision.allowed is True
    assert decision.code == "ALLOWED_LOGIN"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutation_requests_are_blocked(method: str) -> None:
    decision = classify_request(method, "https://lms.mindx.edu.vn/api/reviews")

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


def test_login_post_is_blocked_when_path_is_not_explicitly_allowlisted() -> None:
    decision = classify_request(
        "POST",
        "https://lms.mindx.edu.vn/auth/login",
        body=b"username=teacher&password=hidden",
        content_type="application/x-www-form-urlencoded",
    )

    assert decision.allowed is False
    assert decision.code == "LOGIN_ENDPOINT_NOT_ALLOWLISTED"


@pytest.mark.parametrize(
    "url",
    [
        "http://lms.mindx.edu.vn/classes/abc",
        "https://evil.example/classes/abc",
        "https://lms.mindx.edu.vn.evil.example/classes/abc",
    ],
)
def test_non_allowlisted_origin_is_blocked(url: str) -> None:
    decision = classify_request("GET", url)

    assert decision.allowed is False
    assert decision.code == "DOMAIN_BLOCKED"


@pytest.mark.parametrize(
    "url",
    [
        "https://lms.mindx.edu.vn:8443/classes/abc",
        "https://teacher:password@lms.mindx.edu.vn/classes/abc",
        "https://lms.mindx.edu.vn:not-a-port/classes/abc",
    ],
)
def test_unsafe_production_origins_are_blocked(url: str) -> None:
    decision = classify_request("GET", url)

    assert decision.allowed is False
    assert decision.code == "DOMAIN_BLOCKED"


@pytest.mark.parametrize("path", ["/save", "/submit", "/comments/create", "/review/update"])
def test_comment_like_paths_are_blocked_even_when_read_method_is_used(path: str) -> None:
    decision = classify_request("GET", f"https://lms.mindx.edu.vn{path}")

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


def test_login_body_is_never_in_decision_repr() -> None:
    secret = b"password=do-not-log"
    decision = classify_request(
        "POST",
        "https://teachingmindx.top/login",
        body=secret,
        content_type="application/x-www-form-urlencoded",
        login_paths=("/login",),
    )

    assert secret.decode() not in repr(decision)


def test_mutation_like_body_is_blocked_even_on_allowlisted_login_path() -> None:
    decision = classify_request(
        "POST",
        "https://lms.mindx.edu.vn/auth/login",
        body=b'{"comment":"must never be submitted"}',
        content_type="application/json",
        login_paths=("/auth/login",),
    )

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("GET", b"review_text=teacher-note"),
        ("HEAD", b'{"save":"true"}'),
        ("OPTIONS", b'{"editor":"<p>draft</p>"}'),
    ],
)
def test_mutation_like_bodies_are_blocked_even_on_read_methods(
    method: str, body: bytes
) -> None:
    decision = classify_request(
        method,
        "https://lms.mindx.edu.vn/classes/abc",
        body=body,
        content_type="application/json",
    )

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


@pytest.mark.parametrize("path", ["/SAVE", "/Comments/Create", "/Editor"])
def test_mutation_like_paths_are_blocked_case_insensitively(path: str) -> None:
    decision = classify_request("GET", f"https://lms.mindx.edu.vn{path}")

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


@pytest.mark.parametrize(
    "query",
    [
        "action=save",
        "operation=submit",
        "payload=%7B%22comment%22%3A%22must-not-write%22%7D",
    ],
)
def test_mutation_like_query_parameters_are_blocked(query: str) -> None:
    decision = classify_request("GET", f"https://lms.mindx.edu.vn/classes/abc?{query}")

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"


def test_non_mutating_query_parameters_remain_allowed() -> None:
    decision = classify_request("GET", "https://lms.mindx.edu.vn/classes/abc?session=3&view=roster")

    assert decision.allowed is True
    assert decision.code == "ALLOWED_READ"


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_non_post_login_methods_never_bypass_mutation_block(method: str) -> None:
    decision = classify_request(
        method,
        "https://lms.mindx.edu.vn/auth/login",
        body=b"username=teacher&password=hidden",
        content_type="application/x-www-form-urlencoded",
        login_paths=("/auth/login",),
    )

    assert decision.allowed is False
    assert decision.code == "LMS_MUTATION_BLOCKED"
