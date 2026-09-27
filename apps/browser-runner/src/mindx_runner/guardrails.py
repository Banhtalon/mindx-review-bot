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


def is_allowed_url(url: str, mode: str = "production") -> bool:
    parsed = urlparse(url)
    allowed_hosts = ALLOWED_PRODUCTION_HOSTS
    valid_protocol = parsed.scheme == "https"
    if mode == "synthetic":
        allowed_hosts = ALLOWED_PRODUCTION_HOSTS | ALLOWED_SYNTHETIC_HOSTS
        valid_protocol = parsed.scheme in {"http", "https"}

    try:
        port = parsed.port
    except ValueError:
        return False

    port_allowed = (
        parsed.hostname in ALLOWED_SYNTHETIC_HOSTS
        if mode == "synthetic"
        else port in {None, 443}
    )
    return (
        valid_protocol
        and parsed.hostname in allowed_hosts
        and parsed.username is None
        and parsed.password is None
        and port_allowed
    )


def assert_allowed_url(url: str, mode: str = "production") -> None:
    if not is_allowed_url(url, mode):
        raise RuntimeError("Domain is not allowlisted")
