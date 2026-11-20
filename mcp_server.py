import asyncio
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("devagent-mcp-server")

#Available tools list 
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
        ),
        Tool(
            name="save_code_to_file",
            description="Saves generated code into a local file on disk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name of the file (e.g. main.py)"},
                    "code_content": {"type": "string", "description": "The actual source code to write"}
                },
                "required": ["filename", "code_content"]
            }
        )
    ]

# 2. Tool execution 
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "calculate_metrics":
        loc = arguments.get("lines_of_code", 0)
        complexity = "High" if loc > 50 else "Low"
        result_text = f"Code Analysis: Total Lines = {loc}, Complexity = {complexity}"
        return [TextContent(type="text", text=result_text)]
    
    elif name == "save_code_to_file":
        filename = arguments.get("filename")
        content = arguments.get("code_content")
        
        # File local directory 
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            return [TextContent(type="text", text=f"Success: File '{filename}' saved successfully!")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error saving file: {str(e)}")]

    raise ValueError(f"Unknown tool: {name}")

# 3. Stdio transport server run 
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())