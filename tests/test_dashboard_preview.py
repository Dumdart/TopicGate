import asyncio

import pytest

pytest.importorskip(
    "prefab_ui",
    reason="dashboard preview checks require the apps extra",
)

from topicgate.mcp.api.preview.dashboard_preview import mcp


def test_dashboard_preview_exposes_ui_entry_point() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert "open_topicgate_dashboard" in {tool.name for tool in tools}
