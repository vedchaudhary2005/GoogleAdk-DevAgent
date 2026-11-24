import asyncio
import os
import sys
import subprocess
from pathlib import Path, PureWindowsPath
from typing import Any

import requests
from dotenv import load_dotenv

from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


# 1. CONFIGURATION

BASE_DIR = Path(__file__).resolve().parent

# Load .env from the same folder as this file
load_dotenv(BASE_DIR / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# All file operations stay inside this directory
WORKSPACE_DIR = (BASE_DIR / "workspace").resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# 2. SECURITY: SAFE FILE PATH

def get_safe_path(filename: str) -> Path:
    """
    Resolve a user-provided filename inside workspace.
    Reject absolute paths and path traversal attempts.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Filename must be a non-empty string.")

    windows_path = PureWindowsPath(filename)

    if windows_path.is_absolute() or windows_path.drive:
        raise ValueError("Absolute paths are not allowed.")

    if ".." in windows_path.parts:
        raise ValueError("Path traversal is not allowed.")

    file_path = (WORKSPACE_DIR / filename).resolve()

    try:
        file_path.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise ValueError("Access outside workspace is not allowed.")

    return file_path


# 3. REGISTER MCP TOOLS SCHEMA

TOOLS = [
    types.Tool(
        name="calculate_metrics",
        description="Estimates code complexity using line count.",
        inputSchema={
            "type": "object",
            "properties": {
                "lines_of_code": {
                    "type": "integer",
                    "description": "Total lines of code"
                }
            },
            "required": ["lines_of_code"]
        }
    ),
    types.Tool(
        name="save_code_to_file",
        description="Saves generated code inside the project workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative path, for example main.py"
                },
                "code_content": {
                    "type": "string",
                    "description": "Source code to save"
                }
            },
            "required": ["filename", "code_content"]
        }
    ),
    types.Tool(
        name="read_local_file",
        description="Reads a file from the project workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative file path inside workspace"
                }
            },
            "required": ["filename"]
        }
    ),
    types.Tool(
        name="run_python_file",
        description=(
            "Executes a Python file from the project workspace. "
            "Use only for testing generated project files."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Python filename inside workspace"
                }
            },
            "required": ["filename"]
        }
    ),
    types.Tool(
        name="web_search",
        description="Searches the web for programming documentation using Tavily.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Programming-related search query"
                }
            },
            "required": ["query"]
        }
    )
]


async def list_tools(
    context: Any = None,
    params: Any = None
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


# 4. HANDLE MCP TOOL CALLS

async def call_tool(
    name_or_context: Any,
    arguments_or_params: Any = None
) -> types.CallToolResult:
    # Handle both (context, CallToolRequestParams) and direct (name, arguments) calls
    if isinstance(arguments_or_params, types.CallToolRequestParams):
        name = arguments_or_params.name
        arguments = arguments_or_params.arguments or {}
    elif hasattr(arguments_or_params, "name"):
        name = arguments_or_params.name
        arguments = getattr(arguments_or_params, "arguments", {}) or {}
    elif isinstance(name_or_context, str):
        name = name_or_context
        arguments = arguments_or_params or {}
    else:
        name = str(name_or_context)
        arguments = arguments_or_params or {}

    try:
        # TOOL 1: CALCULATE METRICS
        if name == "calculate_metrics":
            loc = arguments.get("lines_of_code")

            if loc is None or not isinstance(loc, int) or loc < 0:
                raise ValueError("lines_of_code must be a non-negative integer.")

            complexity = "High" if loc > 40 else "Low"
            result = (
                f"Total Lines: {loc}\n"
                f"Estimated Complexity: {complexity}\n"
                "Note: This is a line-count heuristic, not a true complexity metric."
            )
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=result)],
                is_error=False
            )

        # TOOL 2: SAVE CODE TO FILE
        elif name == "save_code_to_file":
            filename = arguments.get("filename")
            content = arguments.get("code_content")

            if not isinstance(filename, str) or not filename.strip():
                raise ValueError("filename must be a non-empty string.")

            if not isinstance(content, str):
                raise ValueError("code_content must be a string.")

            file_path = get_safe_path(filename)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Success: File saved at {file_path}")],
                is_error=False
            )

        # TOOL 3: READ LOCAL FILE
        elif name == "read_local_file":
            filename = arguments.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError("filename must be a non-empty string.")

            file_path = get_safe_path(filename)

            if not file_path.is_file():
                raise FileNotFoundError(f"File not found: {filename}")

            if file_path.stat().st_size > 200_000:
                raise ValueError("File is too large to read (limit: 200 KB).")

            content = file_path.read_text(encoding="utf-8")
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content)],
                is_error=False
            )

        # TOOL 4: RUN PYTHON FILE
        elif name == "run_python_file":
            filename = arguments.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError("filename must be a non-empty string.")

            file_path = get_safe_path(filename)

            if file_path.suffix.lower() != ".py":
                raise ValueError("Only Python (.py) files can be executed.")

            if not file_path.is_file():
                raise FileNotFoundError(f"Python file not found: {filename}")

            result = subprocess.run(
                [sys.executable, str(file_path)],
                cwd=str(WORKSPACE_DIR),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False
            )

            output = result.stdout
            error = result.stderr
            response = (
                f"Exit Code: {result.returncode}\n\n"
                f"Output:\n{output[:10000]}\n\n"
                f"Errors:\n{error[:10000]}"
            )
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=response)],
                is_error=False
            )

        # TOOL 5: WEB SEARCH
        elif name == "web_search":
            query = arguments.get("query")

            if not isinstance(query, str) or not query.strip():
                raise ValueError("Search query cannot be empty.")

            if not TAVILY_API_KEY:
                raise ValueError("TAVILY_API_KEY is missing in .env.")

            url = "https://api.tavily.com/search"
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": 3
            }

            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            search_results = data.get("results", [])

            if not search_results:
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text="No search results found.")],
                    is_error=False
                )

            formatted_results = []
            for item in search_results:
                title = item.get("title", "No title")
                item_content = item.get("content", "")
                result_url = item.get("url", "")
                formatted_results.append(
                    f"Title: {title}\n"
                    f"Content: {item_content}\n"
                    f"URL: {result_url}"
                )

            return types.CallToolResult(
                content=[types.TextContent(type="text", text="\n\n".join(formatted_results))],
                is_error=False
            )

        # UNKNOWN TOOL
        else:
            raise ValueError(f"Unknown tool: {name}")

    except requests.RequestException as error:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Web search error: {str(error)}")],
            is_error=True
        )
    except (ValueError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as error:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Tool execution error: {str(error)}")],
            is_error=True
        )
    except Exception as error:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unexpected error: {str(error)}")],
            is_error=True
        )


# 5. INITIALIZE SERVER INSTANCE

app = Server(
    "devagent-mcp-server",
    on_list_tools=list_tools,
    on_call_tool=call_tool
)


# 6. START MCP SERVER

async def main():
    print("DevAgent MCP Server starting...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
