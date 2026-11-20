import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


app = Server("devagent-mcp-server")

# 2. Available tools list
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="calculate_metrics",
            description="Performs basic code complexity calculation based on line count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lines_of_code": {"type": "number", "description": "Number of lines in the script"}
                },
                "required": ["lines_of_code"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "calculate_metrics":
        loc = arguments.get("lines_of_code", 0)
        complexity = "High" if loc > 50 else "Low"
        result_text = f"Code Analysis: Total Lines = {loc}, Complexity = {complexity}"
        return [TextContent(type="text", text=result_text)]
    
    raise ValueError(f"Unknown tool: {name}")

# 4. Stdio transport par server run karna
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())