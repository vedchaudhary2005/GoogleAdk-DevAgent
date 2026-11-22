import asyncio
import os
import subprocess
import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent  
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = Server("devagent-mcp-server")

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
            description="Saves generated code into a local file on disk safely.",
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
            description="Reads an existing file from disk.",
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
            description="Runs a python script or safe terminal command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Terminal command to run"}
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="web_search",
            description="Searches the web for latest programming documentation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "calculate_metrics":
        loc = arguments.get("lines_of_code", 0)
        # Improved complexity check based on structure/lines
        complexity = "High" if loc > 40 else "Low"
        return [TextContent(type="text", text=f"Total Lines: {loc}, Estimated Complexity: {complexity}")]
    
    elif name == "save_code_to_file":
        filename = arguments.get("filename")
        content = arguments.get("code_content")
        # Security: Prevent path traversal attacks (e.g. ../../etc/passwd)
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            return [TextContent(type="text", text="Error: Unsafe file path restricted.")]
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return [TextContent(type="text", text=f"Success: File '{filename}' saved safely!")]

    elif name == "read_local_file":
        filename = arguments.get("filename")
        if not os.path.exists(filename):
            return [TextContent(type="text", text=f"Error: File '{filename}' does not exist.")]
        with open(filename, "r", encoding="utf-8") as f:
            return [TextContent(type="text", text=f.read())]

    elif name == "run_terminal_command":
        cmd = arguments.get("command")
        # Basic security block for destructive shell commands
        forbidden = ["rm -rf", "del /f", "shutdown", "format"]
        if any(f in cmd.lower() for f in forbidden):
            return [TextContent(type="text", text="Security Error: Destructive terminal command blocked.")]
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout if result.returncode == 0 else result.stderr
        return [TextContent(type="text", text=output or "Command executed successfully with no output.")]

    elif name == "web_search":
        query = arguments.get("query")
        if not TAVILY_API_KEY:
            return [TextContent(type="text", text="Error: Tavily API key missing in environment.")]
        url = "https://api.tavily.com/search"
        payload = {"api_key": TAVILY_API_KEY, "query": query}
        res = requests.post(url, json=payload).json()
        results = "\n".join([r.get("content", "") for r in res.get("results", [])[:3]])
        return [TextContent(type="text", text=results or "No search results found.")]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())