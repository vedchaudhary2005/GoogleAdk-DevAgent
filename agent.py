import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import MCPToolSet
from mcp import StdioServerParameters

load_dotenv()

# MCP SERVER CONNECTION SETUP 
mcp_server_params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"]
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
        "You are a senior software engineer. Write clean code, read existing files "
        "when requested, and use the provided MCP tools (like save_code_to_file, calculate_metrics, web_search) "
        "to complete the development task."
    ),
    tools=[MCPToolSet(connection_params=mcp_server_params)]
)

#  REVIEWER AGENT
reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Reviews code for bugs and quality standards.",
    instruction=(
        "Review the code written by the writer agent. Verify syntax, logic, and structure. "
        "Provide constructive feedback so the writer agent can refine it in the next iteration."
    )
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