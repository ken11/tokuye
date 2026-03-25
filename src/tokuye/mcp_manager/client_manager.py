"""
MCP (Model Context Protocol) client manager.

Manages lifecycle of MCP clients configured in .tokuye/config.yaml.
Supports SSE and stdio transport types.
"""

import logging
from typing import List

from tokuye.utils.config import Settings

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages multiple MCP client connections."""

    @staticmethod
    def _build_tool_filters(cfg: "Settings.McpServerConfig") -> dict | None:
        """Build tool_filters dict from config allowed/rejected lists.

        Returns None when no filtering is configured so that MCPClient
        falls back to its default (all tools allowed).
        """
        if not cfg.allowed_tools and not cfg.rejected_tools:
            return None
        filters: dict = {}
        if cfg.allowed_tools:
            filters["allowed"] = list(cfg.allowed_tools)
        if cfg.rejected_tools:
            filters["rejected"] = list(cfg.rejected_tools)
        return filters

    def __init__(self, configs: List[Settings.McpServerConfig]):
        self.configs = configs
        self._clients: list = []
        self._started = False

    def start(self) -> None:
        """Start all configured MCP client connections.

        Failures are logged and skipped — built-in tools remain available.
        """
        if self._started:
            logger.warning("MCP clients already started, skipping")
            return

        if not self.configs:
            logger.debug("No MCP servers configured")
            return

        try:
            from mcp import StdioServerParameters, stdio_client
            from mcp.client.sse import sse_client
            from strands.tools.mcp import MCPClient
        except ImportError as e:
            logger.warning(
                f"MCP dependencies not available, skipping MCP setup: {e}. "
                "Install with: pip install 'strands-agents-tools[mcp]'"
            )
            return

        for cfg in self.configs:
            try:
                if cfg.type == "sse":
                    if not cfg.url:
                        logger.warning(
                            f"MCP server '{cfg.name}': type=sse requires 'url', skipping"
                        )
                        continue
                    url = cfg.url
                    tool_filters = self._build_tool_filters(cfg)
                    client = MCPClient(
                        lambda url=url: sse_client(url),
                        **({"tool_filters": tool_filters} if tool_filters else {}),
                    )

                elif cfg.type == "stdio":
                    if not cfg.command:
                        logger.warning(
                            f"MCP server '{cfg.name}': type=stdio requires 'command', skipping"
                        )
                        continue
                    params = StdioServerParameters(
                        command=cfg.command,
                        args=cfg.args or [],
                        env=cfg.env,
                    )
                    tool_filters = self._build_tool_filters(cfg)
                    client = MCPClient(
                        lambda params=params: stdio_client(params),
                        **({"tool_filters": tool_filters} if tool_filters else {}),
                    )

                else:
                    logger.warning(
                        f"MCP server '{cfg.name}': unknown type '{cfg.type}', skipping"
                    )
                    continue

                # Enter context manager to start the connection
                client.__enter__()
                self._clients.append(client)
                logger.info(f"MCP server '{cfg.name}' ({cfg.type}) connected")

            except Exception as e:
                logger.warning(
                    f"Failed to connect MCP server '{cfg.name}': {e}, skipping"
                )

        self._started = True
        logger.info(
            f"MCP client manager started: {len(self._clients)}/{len(self.configs)} servers connected"
        )

    def get_tools(self) -> list:
        """Get all tools from connected MCP servers.

        Returns:
            List of tools from all connected MCP servers.
        """
        tools = []
        for client in self._clients:
            try:
                server_tools = client.list_tools_sync()
                tools.extend(server_tools)
                logger.debug(
                    f"Got {len(server_tools)} tools from MCP server"
                )
            except Exception as e:
                logger.warning(f"Failed to list tools from MCP server: {e}")
        return tools

    def stop(self) -> None:
        """Stop all MCP client connections."""
        for client in self._clients:
            try:
                client.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error stopping MCP client: {e}")

        self._clients.clear()
        self._started = False
        logger.info("MCP client manager stopped")
