import re
from collections.abc import Collection
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlparse

from .guardrails import is_allowed_url

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MUTATION_PATH_PARTS = frozenset({"save", "submit", "comment", "comments", "editor"})
MUTATION_QUERY_PARTS = frozenset(
    {
        "save",
        "submit",
        "comment",
        "comments",
        "review",
        "review_id",
        "review_text",
        "content",
        "html",
        "editor",
    }
)
_MUTATION_BODY_FIELD = re.compile(
    r"(?:^|[&\s\"'{,])"
    r"(?:comment|comments|review|review_id|review_text|content|html|submit|save|editor)"
    r"(?:\"|\s)*(?:=|:)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RequestDecision:
    allowed: bool
    code: str


def _normalise_login_paths(login_paths: Collection[str]) -> frozenset[str]:
    return frozenset(
        path if path.startswith("/") else f"/{path}"
        for path in login_paths
    )


def _is_mutation_path(path: str) -> bool:
    segments = {segment for segment in path.lower().split("/") if segment}
    return bool(segments & MUTATION_PATH_PARTS) or path.lower().endswith("/review/update")


def _body_has_mutation_field(body: bytes | None) -> bool:
    if body is None:
        return False
    return _MUTATION_BODY_FIELD.search(body.decode("utf-8", errors="ignore")) is not None


def _query_has_mutation_part(query: str) -> bool:
    if not query:
        return False
    for key, value in parse_qsl(query, keep_blank_values=True):
        for part in (key, value):
            tokens = {
                token
                for token in re.split(r"[^a-z0-9_]+", part.lower())
                if token
            }
            if tokens & MUTATION_QUERY_PARTS:
                return True
    return False


def classify_request(
    method: str,
    url: str,
    body: bytes | None = None,
    content_type: str | None = None,
    *,
    login_paths: Collection[str] = (),
) -> RequestDecision:
    del content_type
    parsed = urlparse(url)
    if not is_allowed_url(url):
        return RequestDecision(False, "DOMAIN_BLOCKED")

    path = parsed.path or "/"
    if _is_mutation_path(path):
        return RequestDecision(False, "LMS_MUTATION_BLOCKED")
    if _query_has_mutation_part(parsed.query):
        return RequestDecision(False, "LMS_MUTATION_BLOCKED")
    if _body_has_mutation_field(body):
        return RequestDecision(False, "LMS_MUTATION_BLOCKED")

    normalised_method = method.upper()
    if normalised_method in READ_METHODS:
        return RequestDecision(True, "ALLOWED_READ")

    if normalised_method == "POST":
        if path in _normalise_login_paths(login_paths):
            return RequestDecision(True, "ALLOWED_LOGIN")
        if "login" in {segment for segment in path.lower().split("/") if segment}:
            return RequestDecision(False, "LOGIN_ENDPOINT_NOT_ALLOWLISTED")
        return RequestDecision(False, "LMS_MUTATION_BLOCKED")

    if normalised_method in MUTATION_METHODS:
        return RequestDecision(False, "LMS_MUTATION_BLOCKED")

    return RequestDecision(False, "LMS_MUTATION_BLOCKED")
