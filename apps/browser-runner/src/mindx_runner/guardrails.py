from urllib.parse import urlparse

ALLOWED_PRODUCTION_HOSTS: frozenset[str] = frozenset(
    {"teachingmindx.top", "lms.mindx.edu.vn"}
)
ALLOWED_SYNTHETIC_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost"})


def can_run_automation(enabled: bool) -> bool:
    return enabled is True


def assert_lms_read_only(write_enabled: bool) -> None:
    if write_enabled is not False:
        raise RuntimeError("LMS read-only guard violated")


def assert_allowed_url(url: str, mode: str = "production") -> None:
    parsed = urlparse(url)
    allowed_hosts = ALLOWED_PRODUCTION_HOSTS
    valid_protocol = parsed.scheme == "https"
    if mode == "synthetic":
        allowed_hosts = ALLOWED_PRODUCTION_HOSTS | ALLOWED_SYNTHETIC_HOSTS
        valid_protocol = parsed.scheme in {"http", "https"}

    if not valid_protocol or parsed.hostname not in allowed_hosts:
        raise RuntimeError("Domain is not allowlisted")
