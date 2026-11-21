import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp import MCPToolSet
from mcp import StdioServerParameters

load_dotenv()

#MCP SERVER CONNECTION SETUP

mcp_server_params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"]
)

# WRITER AGENT 
writer_agent = LlmAgent(
    name="writer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Writes production code and utilizes MCP developer tools.",
    instruction=(
        "You are a senior software engineer. Write clean code, read existing files "
        "when requested, and save files using the provided MCP tools."
    ),
    tools=[MCPToolSet(server_params=mcp_server_params)]
)

# REVIEWER AGENT 
reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Reviews code for bugs and quality standards.",
    instruction=(
        "Review the code written by the writer agent. Verify syntax, logic, and structure. "
        "If errors or improvements are found, instruct the writer to fix them."
    )
)

#REFINEMENT LOOP WORKFLOW (Writer <-> Reviewer Loop) 
code_loop = LoopAgent(
    name="code_loop",
    sub_agents=[writer_agent, reviewer_agent],
    max_iterations=2
)

# ROOT AGENT (Coordinator + Guardrails)
root_agent = LlmAgent(
    name="root_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Main coordinator for software development tasks.",
    instruction=(
        "You are an enterprise coding assistant (DevAgent Enterprise). "
        "GUARDRAIL RULE: You ONLY help with programming, debugging, code review, and architecture. "
        "If the user asks anything outside of software development (like casual chat or general knowledge), "
        "strictly refuse and ask them to provide a coding task. "
        "For valid coding tasks, delegate them to the `code_loop` workflow."
    ),
    sub_agents=[code_loop]
)