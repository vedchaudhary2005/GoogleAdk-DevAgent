import asyncio
import os
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("devagent-mcp-server")

# Available Tools List 
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
        ),
        Tool(
            name="read_local_file",
            description="Reads an existing file from disk so the agent can review or fix it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name of the file to read"}
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="run_terminal_command",
            description="Runs a python script or terminal command to test output/errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Terminal command to run (e.g. python main.py)"}
                },
                "required": ["command"]
            }
        )
    ]

# 2. Tool Execution Logic
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
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            return [TextContent(type="text", text=f"Success: File '{filename}' saved successfully!")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error saving file: {str(e)}")]

    elif name == "read_local_file":
        filename = arguments.get("filename")
        try:
            if not os.path.exists(filename) and not os.path.exists(filename): # basic check
                pass
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            return [TextContent(type="text", text=content)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading file '{filename}': {str(e)}")]

    elif name == "run_terminal_command":
        cmd = arguments.get("command")
        try:
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout if result.returncode == 0 else result.stderr
            return [TextContent(type="text", text=f"Execution Output:\n{output}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Command execution failed: {str(e)}")]

    raise ValueError(f"Unknown tool: {name}")

# 3. Stdio Transport Server Run
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())