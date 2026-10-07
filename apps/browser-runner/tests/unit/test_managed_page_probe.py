import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "managed_page_probe", Path(__file__).parents[1] / "integration/managed_page_probe.py"
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
READY = "49152\n/devtools/browser/11111111-2222-3333-4444-555555555555"


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [None, b"49152\n", READY.encode()])
async def test_readiness_uses_chrome_file_even_after_old_eight_second_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initial: bytes | None,
) -> None:
    clock = [0.0]
    ready = tmp_path / "DevToolsActivePort"
    if initial is not None:
        ready.write_bytes(initial)

    async def sleep(seconds: float) -> None:
        clock[0] += seconds
        if clock[0] >= 10:
            ready.write_text(READY, encoding="ascii")

    monkeypatch.setattr(probe, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(probe.asyncio, "sleep", sleep)
    endpoint = await probe.wait_for_chromium(SimpleNamespace(poll=lambda: None), tmp_path)
    assert endpoint == f"ws://127.0.0.1:{READY.replace(chr(10), '')}"
    assert clock[0] == 0 if initial == READY.encode() else 10 <= clock[0] < 10.2


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [
    None, b"49152\n", b"x" * 257, b"\xff", READY.replace("49152", "0").encode(),
    READY.replace("49152", "65536").encode(),
    b"49152\nws://external.invalid/private", b"49152\n/devtools/browser/not-a-uuid",
])
async def test_bad_or_missing_readiness_never_returns_an_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: bytes | None,
) -> None:
    if data is not None:
        (tmp_path / "DevToolsActivePort").write_bytes(data)
    clock = [0.0]

    async def sleep(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(probe, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(probe.asyncio, "sleep", sleep)
    with pytest.raises(probe.ChromiumStartupError, match="CHROMIUM_START_TIMEOUT") as caught:
        await probe.wait_for_chromium(SimpleNamespace(poll=lambda: None), tmp_path)
    assert caught.value.exit_code is None
    assert 30 <= clock[0] < 30.2


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1, -9])
async def test_exited_chrome_is_rejected_even_if_readiness_file_exists(
    tmp_path: Path, exit_code: int,
) -> None:
    (tmp_path / "DevToolsActivePort").write_text(READY, encoding="ascii")
    with pytest.raises(probe.ChromiumStartupError, match="CHROMIUM_EXITED") as caught:
        await probe.wait_for_chromium(SimpleNamespace(poll=lambda: exit_code), tmp_path)
    assert caught.value.exit_code == exit_code


@pytest.mark.asyncio
async def test_failed_startup_launches_once_and_cleans_child_without_removing_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    cleanup = []
    child = SimpleNamespace(
        poll=lambda: None, terminate=lambda: cleanup.append("terminate"),
        wait=lambda **_: cleanup.append("wait"),
    )

    def popen(flags: list[str], **options: object) -> SimpleNamespace:
        calls.append((flags, options))
        return child

    async def not_ready(*_: object) -> str:
        raise probe.ChromiumStartupError()

    monkeypatch.setattr(probe.subprocess, "Popen", popen)
    monkeypatch.setattr(probe, "wait_for_chromium", not_ready)
    with pytest.raises(probe.ChromiumStartupError):
        await probe.probe("synthetic-chromium")
    assert len(calls) == 1 and cleanup == ["terminate", "wait"]
    flags, options = calls[0]
    assert "--remote-debugging-port=0" in flags
    assert "--proxy-server=http://127.0.0.1:9" in flags
    assert "--proxy-bypass-list=<-loopback>" in flags
    assert "--host-resolver-rules=MAP * ~NOTFOUND" in flags
    assert options["stdout"] == options["stderr"] == probe.subprocess.DEVNULL


def test_startup_diagnostic_contains_only_fixed_code_and_numeric_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    executable = tmp_path / "synthetic-chromium"
    executable.touch()

    async def failed(_: str) -> dict:
        raise probe.ChromiumStartupError(-9) from RuntimeError("private-startup-canary")

    monkeypatch.setattr(probe, "probe", failed)
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--chromium", str(executable)])
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 1
    output = capsys.readouterr()
    diagnostic = probe.json.loads(output.out)
    assert diagnostic["chromium_startup"] == {"code": "CHROMIUM_EXITED", "exit_code": -9}
    assert diagnostic["teaching_server_attempts"] == 0
    assert "private-startup-canary" not in output.out + output.err
    assert str(executable) not in output.out + output.err
