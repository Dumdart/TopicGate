import logging
from time import perf_counter

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext


request_logger = logging.getLogger("topicgate.mcp.requests")


def _root_error(error: Exception) -> Exception:
    if isinstance(error, ToolError) and isinstance(error.__cause__, Exception):
        return error.__cause__
    return error


class LoggingMiddleware(Middleware):
    """Log tool outcomes without recording arguments, payloads, or results."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        started_at = perf_counter()
        try:
            result = await call_next(context)
        except Exception as error:
            request_logger.warning(
                "MCP tool failed tool=%s duration_ms=%.1f error_type=%s",
                tool_name,
                self._elapsed_ms(started_at),
                type(_root_error(error)).__name__,
            )
            raise

        request_logger.info(
            "MCP tool completed tool=%s duration_ms=%.1f",
            tool_name,
            self._elapsed_ms(started_at),
        )
        return result

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (perf_counter() - started_at) * 1000
