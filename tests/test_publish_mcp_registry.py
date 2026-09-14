import json
from pathlib import Path
from subprocess import CompletedProcess
from urllib.error import URLError

import pytest

from release import publish_mcp_registry


SERVER = {
    "$schema": "https://example.com/server.schema.json",
    "name": "io.github.example/server",
    "version": "1.2.3",
}


class Response:
    def __init__(self, result: dict[str, object]) -> None:
        self._content = json.dumps(result).encode()

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def _server_path(tmp_path: Path) -> Path:
    path = tmp_path / "server.json"
    path.write_text(json.dumps(SERVER), encoding="utf-8")
    return path


def test_publish_server_skips_an_exact_existing_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        publish_mcp_registry,
        "urlopen",
        lambda *args, **kwargs: Response({"servers": [{"server": SERVER}]}),
    )
    run_calls: list[object] = []
    monkeypatch.setattr(
        publish_mcp_registry.subprocess,
        "run",
        lambda *args, **kwargs: run_calls.append(args),
    )

    publish_mcp_registry.publish_server(_server_path(tmp_path))

    assert run_calls == []


def test_publish_server_retries_a_transient_registry_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        publish_mcp_registry,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    results = iter([CompletedProcess([], 1), CompletedProcess([], 0)])
    run_calls: list[object] = []

    def run(*args: object, **kwargs: object) -> CompletedProcess[object]:
        run_calls.append(args)
        return next(results)

    monkeypatch.setattr(publish_mcp_registry.subprocess, "run", run)
    sleep_calls: list[int] = []
    monkeypatch.setattr(publish_mcp_registry.time, "sleep", sleep_calls.append)

    publish_mcp_registry.publish_server(_server_path(tmp_path))

    assert len(run_calls) == 2
    assert sleep_calls == [10]


def test_publish_server_accepts_a_version_visible_after_command_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = iter(
        [
            Response({"servers": []}),
            Response({"servers": [{"server": SERVER}]}),
        ]
    )
    monkeypatch.setattr(
        publish_mcp_registry,
        "urlopen",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(
        publish_mcp_registry.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess([], 1),
    )

    publish_mcp_registry.publish_server(_server_path(tmp_path))
