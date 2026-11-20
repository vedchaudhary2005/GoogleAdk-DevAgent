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

#WRITER AGENT
writer_agent = LlmAgent(
    name="writer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Writes code and checks code metrics using MCP tools.",
    instruction="You are a senior developer. Write clean Python code and use the `calculate_metrics` tool to analyze code complexity when required.",
    tools=[MCPToolSet(server_params=mcp_server_params)]
)

#REVIEWER AGENT
reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Reviews the written code for quality.",
    instruction="Review the code provided by the writer agent. If it meets quality standards, approve it."
)

# REFINEMENT LOOP WORKFLOW 
code_loop = LoopAgent(
    name="code_loop",
    sub_agents=[writer_agent, reviewer_agent],
    max_iterations=2
)

#ROOT AGENT 
root_agent = LlmAgent(
    name="root_agent",
    model=LiteLlm(model="groq/openai/gpt-oss-20b"),
    description="Main coordinator managing the code generation and review pipeline.",
    instruction="Take the user's coding request and delegate it to the `code_loop` workflow.",
    sub_agents=[code_loop]
)