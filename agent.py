import os
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import MCPToolSet
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset

load_dotenv()

# MCP SERVER CONNECTION SETUP 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

mcp_server_params = StdioServerParameters(
    command=sys.executable,
    args=[os.path.join(BASE_DIR, "mcp_server.py")]
)

mcp_tools = McpToolset(
    connection_params=mcp_server_params,
    require_confirmation=True
)

#  HUMAN-IN-THE-LOOP
def hitl_approval_callback(tool_name: str, arguments: dict) -> bool:
    print(f"\n🚨 [SECURITY GATE - HITL] Agent wants to execute: '{tool_name}'")
    print(f"Arguments: {arguments}")
    
    choice = input("Do you want to approve this action? (y/n): ").strip().lower()
    if choice == 'y':
        print("✅ Action Approved.")
        return True
    else:
        print("❌ Action Rejected.")
        return False

#  WRITER AGENT(Connected with MCP Tools)
writer_agent = LlmAgent(
    name="writer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Writes production code and utilizes MCP developer tools.",
    instruction=(
     "You are a senior software engineer. Write clean code, "
    "read existing files when requested, and use the provided MCP tools "
    "(save_code_to_file, read_local_file, calculate_metrics, "
    "run_python_file, web_search) to complete development tasks."
    ),
    tools=[MCPToolSet(connection_params=mcp_server_params)]
)

#  REVIEWER AGENT
reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    instruction=(
        "Review this generated code: {generated_code}. "
        "Identify bugs and provide corrections."
    ),
    output_key="review_feedback"
)

#  REFINEMENT LOOP WORKFLOW 
code_loop = LoopAgent(
    name="code_loop",
    sub_agents=[writer_agent, reviewer_agent],
    max_iterations=2
)

# ROOT AGENT 
root_agent = LlmAgent(
    name="root_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Main coordinator for software development tasks.",
    instruction=(
        "You are an enterprise coding assistant (DevAgent Enterprise). "
        "GUARDRAIL RULE: You ONLY help with programming, debugging, code review, and architecture. "
        "If the user asks anything outside of software development, strictly refuse. "
        "For valid coding tasks, delegate them to the `code_loop` workflow."
    ),
    sub_agents=[code_loop]
)