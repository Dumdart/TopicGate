import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


REGISTRY_SEARCH_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
MAX_ATTEMPTS = 5


def publish_server(server_path: Path) -> None:
    server = json.loads(server_path.read_text(encoding="utf-8"))
    if _is_published(server):
        print(f"MCP Registry already contains {server['name']} {server['version']}")
        return

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = subprocess.run(
            ["mcp-publisher", "publish", str(server_path)],
            check=False,
        )
        if result.returncode == 0 or _is_published(server):
            return
        if attempt == MAX_ATTEMPTS:
            raise SystemExit(result.returncode)

        delay_seconds = attempt * 10
        print(
            "MCP Registry publish failed; "
            f"retrying in {delay_seconds} seconds...",
            file=sys.stderr,
        )
        time.sleep(delay_seconds)


def _is_published(server: dict[str, object]) -> bool:
    query = urlencode({"search": server["name"]})
    try:
        with urlopen(f"{REGISTRY_SEARCH_URL}?{query}", timeout=15) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return False

    return any(item.get("server") == server for item in result.get("servers", []))


def main(argv: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit(
            "Usage: python -m release.publish_mcp_registry SERVER.json"
        )
    publish_server(Path(arguments[0]))


if __name__ == "__main__":
    main()
