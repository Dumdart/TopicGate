import asyncio
import logging

from fastmcp import Client, FastMCP

from topicgate.mcp.middleware import ErrorHandlingMiddleware, LoggingMiddleware


def middleware_server() -> FastMCP:
    return FastMCP(
        "middleware-test",
        middleware=[ErrorHandlingMiddleware(), LoggingMiddleware()],
    )


def test_logging_middleware_preserves_results_without_logging_contents(caplog) -> None:
    async def scenario() -> None:
        mcp = middleware_server()

        @mcp.tool
        def echo(value: str) -> str:
            return f"result:{value}"

        secret = "secret-payload"
        with caplog.at_level(logging.INFO, logger="topicgate.mcp.requests"):
            async with Client(mcp) as client:
                result = await client.call_tool("echo", {"value": secret})

        assert result.data == f"result:{secret}"
        application_logs = [
            record.getMessage()
            for record in caplog.records
            if record.name.startswith("topicgate.mcp")
        ]
        assert any("MCP tool completed tool=echo" in line for line in application_logs)
        assert all(secret not in line for line in application_logs)

    asyncio.run(scenario())


def test_error_middleware_exposes_actionable_validation_errors() -> None:
    async def scenario() -> None:
        mcp = middleware_server()

        @mcp.tool
        def validate() -> None:
            raise ValueError("QoS must be between 0 and 2")

        async with Client(mcp) as client:
            result = await client.call_tool("validate", {}, raise_on_error=False)

        assert result.is_error
        assert result.content[0].text == "QoS must be between 0 and 2"

    asyncio.run(scenario())


def test_error_middleware_preserves_fastmcp_argument_validation() -> None:
    async def scenario() -> None:
        mcp = middleware_server()

        @mcp.tool
        def set_qos(qos: int) -> None:
            pass

        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_qos", {"qos": "invalid"}, raise_on_error=False
            )

        assert result.is_error
        assert "qos" in result.content[0].text

    asyncio.run(scenario())


def test_error_middleware_masks_connection_and_unexpected_error_details(caplog) -> None:
    async def scenario() -> None:
        mcp = middleware_server()

        @mcp.tool
        def connect() -> None:
            raise ConnectionError("password=broker-secret")

        @mcp.tool
        def crash() -> None:
            raise RuntimeError("token=internal-secret")

        with caplog.at_level(logging.INFO):
            async with Client(mcp) as client:
                connection_result = await client.call_tool(
                    "connect", {}, raise_on_error=False
                )
                crash_result = await client.call_tool("crash", {}, raise_on_error=False)

        assert connection_result.is_error
        assert connection_result.content[0].text == "The MQTT broker operation failed."
        assert crash_result.is_error
        assert (
            crash_result.content[0].text
            == "The tool could not be completed due to an internal error."
        )

        application_logs = [
            record.getMessage()
            for record in caplog.records
            if record.name.startswith("topicgate.mcp")
        ]
        assert any("error_type=ConnectionError" in line for line in application_logs)
        assert any("error_type=RuntimeError" in line for line in application_logs)
        assert all("broker-secret" not in line for line in application_logs)
        assert all("internal-secret" not in line for line in application_logs)

    asyncio.run(scenario())
