
import os
import sys
from dotenv import load_dotenv

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset
from mcp import StdioServerParameters



# 1. CONFIGURATION

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

MODEL = LiteLlm(
    model="groq/llama-3.3-70b-versatile"
)


# 2. MCP SERVER CONNECTION


mcp_server_params = StdioServerParameters(
    command=sys.executable,
    args=[
        os.path.join(BASE_DIR, "mcp_server.py")
    ]
)

mcp_tools = McpToolset(
    connection_params=mcp_server_params,
    require_confirmation=True
)



# 3. WRITER DYNAMIC INSTRUCTION


def writer_instruction(context: ReadonlyContext) -> str:

    feedback = context.state.get(
        "review_feedback",
        ""
    )

    if feedback:
        feedback_section = f"""
        PREVIOUS REVIEWER FEEDBACK:
        {feedback}

        You must improve your previous code based on this feedback.
        Do not ignore the reviewer's corrections.
        """
    else:
        feedback_section = """
        This is the first iteration.
        Create the initial solution based on the user's request.
        """

    return f"""
    You are a senior software engineer.

    Your responsibilities:
    1. Understand the user's programming task.
    2. Write clean, readable and maintainable code.
    3. Read existing files when necessary.
    4. Use MCP tools when required.
    5. Save the final code using save_code_to_file.
    6. Never claim that a file was saved unless the tool confirms it.

    {feedback_section}

    If you are revising code, preserve working functionality.
    Explain what you changed and why.

    Return the complete updated code in your final response.
    """



# 4. WRITER AGENT


writer_agent = LlmAgent(
    name="writer_agent",
    model=MODEL,

    description=(
        "Writes, modifies and saves production-oriented code "
        "using MCP developer tools."
    ),

    instruction=writer_instruction,

    tools=[
        mcp_tools
    ],

    output_key="generated_code"
)



# 5. REVIEWER AGENT


reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=MODEL,

    description=(
        "Reviews generated code and identifies bugs, "
        "security issues and improvements."
    ),

    instruction="""
    You are a senior code reviewer.

    Review the following code:

    {generated_code}

    Check:
    1. Syntax and runtime errors.
    2. Incorrect logic.
    3. Missing imports and dependencies.
    4. Security vulnerabilities.
    5. Error handling.
    6. Code quality and maintainability.

    Give specific corrections to the Writer Agent.

    If the code is good, clearly say:
    APPROVED: No major issues found.

    Do not rewrite the entire project unnecessarily.
    """,

    output_key="review_feedback"
)



# 6. REFINEMENT LOOP


code_loop = LoopAgent(
    name="code_loop",

    sub_agents=[
        writer_agent,
        reviewer_agent
    ],

    max_iterations=2
)



# 7. ROOT AGENT


root_agent = LlmAgent(
    name="root_agent",
    model=MODEL,

    description=(
        "Main coordinator for DevAgent Enterprise."
    ),

    
instruction="""
You are DevAgent Enterprise, an AI software development assistant.

SCOPE:
You must help with:
- Programming and code generation.
- Debugging and code review.
- Software architecture.
- Programming documentation and tutorials.
- Searching the web for programming-related information.
- Explaining programming concepts and libraries.

GUARDRAILS:
- Refuse requests unrelated to software development.
- Programming-related web searches are ALLOWED.
- Never refuse a programming documentation search just because
  the user asks to search the web.
- Never claim a tool was executed unless it actually was.

DELEGATION:
For coding, debugging, code review and programming research tasks,
delegate to code_loop.

The Writer Agent can use MCP tools including web_search.
The Reviewer Agent reviews generated code.
"""
,

    sub_agents=[
        code_loop
    ]
)
