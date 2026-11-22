# 🤖 DevAgent Enterprise

**An AI-powered software development agent built using Google Agent Development Kit (ADK), Groq, LiteLLM and Model Context Protocol (MCP).**

DevAgent Enterprise is a multi-agent coding assistant designed to understand programming tasks, generate code, review implementations, identify potential issues and improve solutions through iterative agent collaboration.

It uses a Writer–Reviewer architecture powered by Google ADK's agent orchestration capabilities and external MCP tools.

---

## 🚀 Key Features

- **AI Code Generation:** Generates clean, readable and maintainable code from natural-language instructions.
- **Automated Code Review:** Reviews generated code for syntax errors, logical issues, security vulnerabilities and missing dependencies.
- **Iterative Code Refinement:** Uses a Writer–Reviewer feedback loop to improve generated solutions.
- **MCP Integration:** Connects AI agents with external developer tools through Model Context Protocol.
- **File Management:** Reads existing files and saves generated code inside a restricted workspace.
- **Python Execution:** Executes Python files to test generated implementations.
- **Web Research:** Searches programming documentation and technical resources using Tavily.
- **Code Metrics:** Provides basic code-size and complexity estimates.
- **Agent Guardrails:** Restricts the root agent to software development-related tasks.

## 🧠 Agent Architecture

The project follows a hierarchical multi-agent architecture.

```text
                  USER REQUEST
                       |
                       v
                  ROOT AGENT
                 (Coordinator)
                       |
                       v
                  CODE LOOP
                  LoopAgent
                       |
             +---------+---------+
             |                   |
             v                   |
         WRITER AGENT            |
             |                   |
             v                   |
        MCP DEVELOPER TOOLS      |
             |                   |
             v                   |
        GENERATED CODE           |
             |                   |
             v                   |
        REVIEWER AGENT           |
             |                   |
             v                   |
        REVIEW FEEDBACK          |
             |                   |
             +-------------------+
                       |
              Maximum 2 Iterations
                       |
                       v
                 FINAL RESPONSE
```

### 1. Root Agent

The main coordinator of DevAgent Enterprise.

Responsibilities:
- Understand user requests.
- Enforce software development scope.
- Delegate coding, debugging, code review and programming research tasks to the Code Loop.
- Coordinate the overall development workflow.

### 2. Writer Agent

Responsible for generating and modifying code.

Responsibilities:
- Understand programming requirements.
- Generate clean and maintainable code.
- Read existing project files when necessary.
- Use MCP tools to interact with the development workspace.
- Save generated code using `save_code_to_file`.
- Improve previous implementations using reviewer feedback.

### 3. Reviewer Agent

Responsible for reviewing generated implementations.

It evaluates:
- Syntax and runtime errors.
- Incorrect programming logic.
- Missing imports and dependencies.
- Potential security vulnerabilities.
- Error handling.
- Code quality and maintainability.

The reviewer provides specific feedback to the Writer Agent.

### 4. Code Loop

The project uses Google ADK's `LoopAgent` to coordinate the Writer and Reviewer agents.

- Writer generates the initial solution.
- Reviewer evaluates the generated code.
- Feedback is stored in agent state.
- Writer uses the previous feedback to improve the implementation.
- The process can run for a maximum of two iterations.

**Agent State Keys:**
- `generated_code`
- `review_feedback`

## 🔌 MCP Developer Tools

DevAgent uses a custom MCP server (`mcp_server.py`) connected through `McpToolset` and standard input/output (stdio) transport.

The MCP server exposes the following tools:

| Tool | Description |
|---|---|
| `calculate_metrics` | Estimates code complexity using line count |
| `save_code_to_file` | Saves generated code inside the workspace |
| `read_local_file` | Reads existing project files |
| `run_python_file` | Executes Python files for testing |
| `web_search` | Searches programming resources using Tavily |

### Workspace Security

File operations are restricted to the project's `workspace/` directory.

Implemented safeguards include:
- Blocking absolute file paths.
- Preventing path traversal.
- Restricting file access to the workspace.
- Limiting file reads to 200 KB.
- Executing Python files using `subprocess` with `shell=False`.
- Applying a 20-second execution timeout.

MCP tool confirmation is also enabled in the ADK configuration.

**Note:** These controls restrict file access and command execution, but do not constitute a fully isolated execution sandbox.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core development language |
| Google ADK | Agent creation and orchestration |
| Groq | LLM inference provider |
| LiteLLM | Model integration |
| Qwen 3.8 27B | Configured language model |
| MCP | External tool integration |
| Tavily | Programming-related web search |
| MongoDB / PyMongo | Chat-history storage helper |
| python-dotenv | Environment configuration |

## 📂 Project Structure

```text
GoogleAdk-DevAgent/
│
├── agent.py              # Root, Writer, Reviewer and Loop agents
│
├── mcp_server.py         # Custom MCP server and developer tools
│
├── memory_manager.py     # MongoDB chat-history helper
│
├── workspace/            # Generated code and project files
│
├── __init__.py            # Agent package initialization
│
├── requirements.txt      # Python dependencies
│
├── .env                  # API keys and configuration
│
├── .gitignore
│
└── README.md
```

## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/vedchaudhary2005/GoogleAdk-DevAgent.git

cd GoogleAdk-DevAgent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the environment

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key

TAVILY_API_KEY=your_tavily_api_key

MONGO_URI=mongodb://localhost:27017/
```

MongoDB configuration is optional for the standalone memory helper.

## ▶️ Running the Project

### Run the agent

```bash
adk run .
```

### Launch ADK Web Interface

```bash
adk web .
```

The ADK Web interface allows you to interact with the root agent and test its capabilities.

## 💬 Example Prompts

**Code Generation**

```text
Create a Python calculator with addition,
subtraction, multiplication and division.
```

**Debugging**

```text
Read my existing Python file and identify
potential bugs and runtime errors.
```

**Code Review**

```text
Review this Python implementation and
suggest improvements for security and readability.
```

**Web Research**

```text
Search for the latest Python documentation
about asynchronous programming.
```

**Code Execution**

```text
Create a Python file that checks whether
a number is prime and execute it.
```

## 🗺️ Future Improvements

- Persistent conversational memory integrated with the agent workflow.
- Human-in-the-loop approval before executing sensitive operations.
- Advanced testing and debugging agents.
- Improved execution isolation and sandboxing.
- Support for additional programming languages.
- More advanced multi-agent development workflows.

## 📌 Project Status

Actively developed as an exploration of multi-agent software development using Google ADK, LiteLLM and MCP.

---

## 👨‍💻 Author

**Ved Chaudhary**

GitHub: [@vedchaudhary2005](https://github.com/vedchaudhary2005)

Project: [GoogleAdk-DevAgent](https://github.com/vedchaudhary2005/GoogleAdk-DevAgent)

---

**Built with Python, Google ADK and MCP ❤️**
