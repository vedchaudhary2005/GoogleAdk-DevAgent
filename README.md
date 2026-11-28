# 🤖 DevAgent Enterprise

### AI-Powered Multi-Agent Software Development Assistant

**DevAgent Enterprise** is an AI-powered software development assistant built using **Google Agent Development Kit (ADK), Python, Groq, LiteLLM, and Model Context Protocol (MCP)**.

It uses a multi-agent architecture to understand programming tasks, generate code, review implementations, identify potential issues, and improve solutions through iterative collaboration between AI agents.

The project also explores persistent conversation storage, Google OAuth 2.0 authentication, model switching, custom developer tools, and human-in-the-loop workflows.

---

## 🔗 Project Links

- **GitHub Repository:** https://github.com/vedchaudhary2005/GoogleAdk-DevAgent
- **Live:** https://googleadkdevagent.vercel.app
- **Developer:** Ved Chaudhary
- **Email:** vedchaudhary162005@gmail.com

---

## 📌 Project Overview

DevAgent Enterprise is designed to work like an AI development assistant.

Instead of relying on a single LLM response, it uses multiple specialized agents that collaborate during the software development process.

The main architecture consists of:

- Root Agent – coordinates the complete workflow.
- Writer Agent – generates and modifies code.
- Reviewer Agent – evaluates generated implementations.
- LoopAgent – manages iterative development and review.
- MCP Server – provides external developer tools.
- Model Manager – supports configurable LLM integration.
- Memory Manager – handles MongoDB-based conversation storage.

The objective is to make AI-assisted software development more structured, modular, and extensible.

## 🚀 Key Features

### 1. Multi-Agent Development Workflow
- Hierarchical agent architecture using Google ADK.
- Specialized Writer and Reviewer agents.
- Iterative code generation and review.
- Feedback-based code refinement.
- Configurable iteration limits.

### 2. AI Code Generation
- Generate code using natural-language instructions.
- Create new Python implementations.
- Modify existing project files.
- Generate readable and maintainable solutions.

### 3. Automated Code Review
- Review generated implementations.
- Identify potential syntax and logical issues.
- Check missing imports and dependencies.
- Suggest error handling and code-quality improvements.
- Provide feedback to the Writer Agent.

### 4. Multiple LLM Integration
- Groq-based model inference.
- LiteLLM integration.
- Configurable model selection.
- Model switching through the application interface.
- Environment-based model configuration.

### 5. MCP Integration
- Custom MCP server.
- Tool discovery and execution through MCP.
- Integration using ADK's McpToolset.
- STDIO-based MCP communication.

### 6. Google Authentication
- Google OAuth 2.0 integration.
- Google Cloud Console configuration.
- Google sign-in workflow for the application.
- User authentication integration.

### 7. MongoDB Integration
- MongoDB connection using PyMongo.
- Conversation and message storage.
- Persistent chat-history functionality.
- Cross-chat memory development.

### 8. Developer Tools
- Local file reading.
- Code generation and file writing.
- Python execution.
- Basic code metrics.
- Programming-related web research using Tavily.

### 9. Human-in-the-Loop
- Approval-based workflow experiments.
- Controlled execution of agent operations.
- Additional confirmation before sensitive operations.

### 10. Web Application
- Browser-based chat interface.
- New conversation workflow.
- Previous conversation and chat-history interface.
- AI model selection interface.
- Backend integration.

---

## 🧠 System Architecture

DevAgent follows a hierarchical multi-agent architecture.

```text
                    USER
                      |
                      v
              WEB APPLICATION
                      |
                      v
                SERVER / API
                      |
                      v
                ROOT AGENT
                 (Coordinator)
                      |
                      v
                 CODE LOOP
                  LoopAgent
                      |
             +--------+--------+
             |                 |
             v                 |
         WRITER AGENT          |
             |                 |
             v                 |
        MCP DEVELOPER TOOLS    |
             |                 |
             v                 |
        GENERATED CODE        |
             |                 |
             v                 |
        REVIEWER AGENT         |
             |                 |
             v                 |
        REVIEW FEEDBACK        |
             |                 |
             +-----------------+
                      |
              MAX ITERATIONS: 2
                      |
                      v
                FINAL RESPONSE
```

### 1. Root Agent

The Root Agent acts as the main coordinator.

Responsibilities:

- Understand incoming user requests.
- Identify software development-related tasks.
- Enforce the agent's intended scope.
- Delegate tasks to the Code Loop.
- Coordinate the development workflow.

### 2. Writer Agent

The Writer Agent handles code generation and modification.

Responsibilities:

- Understand programming requirements.
- Generate code based on user instructions.
- Read existing project files when necessary.
- Use MCP developer tools.
- Save generated code using `save_code_to_file`.
- Improve previous implementations using reviewer feedback.

### 3. Reviewer Agent

The Reviewer Agent evaluates the Writer Agent's implementation.

It focuses on:

- Syntax and runtime issues.
- Incorrect programming logic.
- Missing imports and dependencies.
- Potential security vulnerabilities.
- Error handling.
- Code readability and maintainability.

It provides structured feedback to the Writer Agent.

### 4. LoopAgent

Google ADK's `LoopAgent` manages the iterative Writer–Reviewer workflow.

Execution flow:

1. Writer Agent generates the initial implementation.
2. Reviewer Agent examines the generated solution.
3. Review feedback is stored in agent state.
4. Writer Agent receives the previous feedback.
5. Writer improves the implementation.
6. The loop stops after the configured maximum iterations.

**Agent State Keys:**

- `generated_code`
- `review_feedback`

---

## 🔌 MCP – Model Context Protocol

DevAgent uses a custom MCP server implemented in `mcp_server.py`.

It connects developer tools to AI agents using:

- MCP Server
- `McpToolset`
- STDIO transport
- Tool registration and invocation

### Available MCP Tools

| Tool | Purpose |
|---|---|
| `calculate_metrics` | Estimates code complexity using line count |
| `save_code_to_file` | Saves generated code |
| `read_local_file` | Reads existing workspace files |
| `run_python_file` | Executes Python files |
| `web_search` | Searches technical resources using Tavily |

### MCP Workflow

```text
       GOOGLE ADK AGENT
               |
               v
           McpToolset
               |
               v
          STDIO CLIENT
               |
               v
          MCP SERVER
               |
       +-------+-------+
       |       |       |
       v       v       v
      FILE   PYTHON   TAVILY
     TOOLS   EXECUTION SEARCH
       |
       v
    WORKSPACE
```

### Workspace Security

File operations are restricted to the project's `workspace/` directory.

Implemented safeguards include:

- Blocking absolute file paths.
- Preventing path traversal.
- Restricting file access to the workspace.
- Limiting file reads to 200 KB.
- Executing Python files using `subprocess`.
- Using `shell=False`.
- Applying a 20-second execution timeout.

MCP tool confirmation is also supported through ADK configuration.

**Security Note:** These protections reduce accidental or unauthorized file access, but do not constitute a fully isolated execution sandbox. Generated code should only be executed in a trusted environment.

---

## 🤖 LLM Integration – Groq & LiteLLM

DevAgent uses LiteLLM to integrate supported language models through a consistent interface.

### Why LiteLLM?

Different LLM providers expose different APIs and model configurations.

LiteLLM provides a unified integration layer, making it easier to configure and switch between supported models.

### Model Configuration

The project uses Groq for LLM inference.

Example configuration:

```python
from google.adk.models.lite_llm import LiteLlm

model = LiteLlm(
    model="groq/qwen/qwen3.8-27b"
)
```

The model can also be configured through environment variables.

```env
MODEL_NAME=groq/qwen/qwen3.8-27b
```

The application includes a model-selection workflow so that different configured models can be selected without redesigning the agent architecture.

Actual model availability depends on provider access, API limits, and model availability.

---

## 🧠 MongoDB – Persistent Conversation Storage

MongoDB is used through PyMongo for conversation-related data storage.

The memory-management layer is separated from the agent orchestration logic.

Its responsibilities include:

- Establishing a MongoDB connection.
- Storing conversation information.
- Storing individual messages.
- Retrieving previous conversations.
- Supporting persistent chat-history functionality.

The intended architecture separates conversation persistence from the in-memory state used during an individual ADK execution.

This distinction is important:

- ADK Session State manages execution/session context.
- MongoDB stores application-level conversation history.
- Cross-chat memory requires retrieving and providing relevant stored information to the agent.

---

## 🔐 Google OAuth 2.0 Authentication

The web application includes Google sign-in integration using Google OAuth 2.0.

Google Cloud Console is used to configure the OAuth application.

Authentication workflow:

```text
       USER
        |
        v
    WEB APPLICATION
        |
        v
   GOOGLE SIGN-IN
        |
        v
    GOOGLE OAUTH
        |
        v
  AUTHENTICATION
        |
        v
   BACKEND SERVER
        |
        v
  USER DATA / MONGODB
```

Authentication is handled at the application layer rather than being treated as an ADK agent capability.

Google Cloud configuration includes OAuth client credentials and authorized application origins.

**Important:** API secrets and OAuth credentials must remain in environment variables and must never be committed to GitHub.

---

## 🧑‍💻 Human-in-the-Loop (HITL)

The project also explores human approval workflows.

The purpose of HITL is to introduce human supervision into AI-driven execution.

A typical workflow:

```text
       USER REQUEST
             |
             v
         AI AGENT
             |
             v
      TOOL OPERATION
             |
             v
      APPROVAL CHECK
             |
        +----+----+
        |         |
        v         v
      APPROVE   REJECT
        |         |
        v         v
     EXECUTE    STOP
```

This approach is useful when AI agents interact with files, execute code, or perform operations requiring additional supervision.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core development language |
| Google ADK | Agent creation and orchestration |
| LlmAgent | Specialized AI agents |
| LoopAgent | Iterative agent workflow |
| Groq | LLM inference |
| LiteLLM | Unified model integration |
| Qwen 3.8 27B | Configured language model |
| MCP | External developer tool integration |
| McpToolset | ADK and MCP integration |
| Tavily | Web research |
| MongoDB | Conversation storage |
| PyMongo | MongoDB integration |
| FastAPI | Backend API development |
| Google OAuth 2.0 | User authentication |
| Google Cloud Console | OAuth application configuration |
| python-dotenv | Environment configuration |
| HTML, CSS, JavaScript | Web application interface |

---

## 📂 Project Structure

The core public repository contains the following files:

```text
GoogleAdk-DevAgent/
│
├── agent.py
│   └── Root Agent, Writer Agent,
│       Reviewer Agent and LoopAgent
│
├── mcp_server.py
│   └── Custom MCP server and developer tools
│
├── memory_manager.py
│   └── MongoDB connection and chat storage
│
├── workspace/
│   └── Generated code and project files
│
├── __init__.py
│   └── Agent package initialization
│
├── requirements.txt
│   └── Python dependencies
│
├── .env
│   └── Environment configuration (not committed)
│
├── .gitignore
│
└── README.md
```

The extended web application development also includes:

```text
GoogleAdk-DevAgent/
│
├── server.py
│   └── Application backend and API integration
│
├── model_manager.py
│   └── LLM model configuration and management
│
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── ...
```

The extended application files should be included in the public repository before treating this as the complete published project structure.

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.10 or compatible version supported by the installed ADK release.
- Git
- MongoDB (optional for standalone agent usage; required for MongoDB-backed features).
- Groq API Key
- Tavily API Key

### 1. Clone Repository

```bash
git clone https://github.com/vedchaudhary2005/GoogleAdk-DevAgent.git

cd GoogleAdk-DevAgent
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate Environment

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key

TAVILY_API_KEY=your_tavily_api_key

MONGO_URI=mongodb://localhost:27017/

MODEL_NAME=groq/qwen/qwen3.8-27b

REQUIRE_CONFIRMATION=true
```

Add the appropriate Google OAuth credentials and other application-specific configuration when running the authenticated web application.

Do not share your `.env` file or publish API keys.

---

## ▶️ Running the Project

### Run Google ADK Agent

```bash
adk run .
```

### Launch ADK Web Interface

```bash
adk web .
```

### Run the Extended Web Application

The extended application uses its backend server and static frontend.

Start the backend using the project's configured server entry point and port.

Make sure MongoDB, OAuth configuration, and the required API keys are configured before using the corresponding application features.

---

## 💬 Example Use Cases

### 1. Code Generation

```text
Create a Python calculator with addition,
subtraction, multiplication and division.
```

### 2. Debugging

```text
Read my existing Python file and identify
potential bugs and runtime errors.
```

### 3. Automated Code Review

```text
Review this Python implementation and suggest
improvements for security and readability.
```

### 4. Web Research

```text
Search for Python documentation about
asynchronous programming.
```

### 5. Code Execution

```text
Create a Python file that checks whether
a number is prime and execute it.
```

### 6. Code Refinement

```text
Create a Python implementation of a REST API.

Review the implementation and improve it
based on the reviewer's feedback.
```

---

## 🧩 Important Concepts Implemented

Working on this project provided practical exposure to:

- Agentic AI and Generative AI.
- Google Agent Development Kit.
- LLM integration using LiteLLM.
- Multi-agent orchestration.
- Sequential and iterative agent workflows.
- Agent state and output keys.
- MCP architecture and custom tool development.
- Tool calling and external integrations.
- Human-in-the-loop approval workflows.
- MongoDB persistence.
- Google OAuth 2.0.
- Backend API development.
- Environment-based configuration.
- Workspace security and subprocess execution.
- Model configuration and switching.

---

## 🔮 Future Improvements

- More advanced persistent memory and retrieval.
- Better agent context management.
- Improved code execution isolation.
- Dedicated testing and debugging agents.
- Support for additional programming languages.
- Advanced code-quality analysis.
- More robust approval and permission management.
- Improved error handling and observability.
- Production-ready deployment and scaling.

---

## 📌 Project Status

**DevAgent Enterprise** is an actively developed personal project exploring practical multi-agent software development using Google ADK, LiteLLM, Groq, and MCP.

The project focuses on understanding how AI agents can collaborate, use external tools, manage development workflows, and integrate with application-level services.

Some advanced features and production-hardening improvements remain under development.

---

## 👨‍💻 Author

**Ved Chaudhary**

- GitHub: https://github.com/vedchaudhary2005
- Repository: https://github.com/vedchaudhary2005/GoogleAdk-DevAgent
- Email: vedchaudhary162005@gmail.com

---

**Built with Python, Google ADK, Groq, LiteLLM and MCP. ❤️**
