import asyncio

from mcp.server.mcpserver import MCPServer


app = MCPServer("ansible-mcp-local-server", version="1.0.a-dev")


@app.tool()
def calculate_sum(a: float, b: float) -> str:
    """Adds two numbers together."""
    return str(a + b)


if __name__ == "__main__":
    asyncio.run(app.run_stdio_async())
