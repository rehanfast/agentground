# AgentGround

**AI Agent Sandbox Platform** — A Python-native sandbox for experimenting with autonomous AI agents in a governed, observable environment.

AgentGround provides isolated workspaces (environments) where AI agents can be registered, assigned tools, executed against real LLM APIs, and audited step by step — all through a browser-based Streamlit interface. No command-line expertise or frontend development is required for normal use.

---

## Features

- **Auto Mode:** Describe your goal and let the Master Agent plan, provision sub-agents, execute them, evaluate results, and iterate autonomously.
- **Model Registry:** Curate your own LLM endpoints (OpenAI, Google, xAI, DeepSeek, Ollama) with intelligence ranking and automatic API key rotation on rate limits.
- **Authentication & Multi-tenancy:** Secure user registration, fast query-parameter sessions, and fully isolated per-user MySQL databases and file workspaces.
- **Agent Pipeline Execution:** Run sequential or parallel multi-agent workflows with ease.
- **Governance:** Strict rate limit enforcement (Max Calls, Timeout, RPM) using custom LangChain callbacks.
- **Comprehensive Audit Trail:** Every LLM request, tool call, and response is recorded immutably.
- **Built-in Tools:** Terminal (whitelisted commands only), Web Search (Tavily), and File Read/Write (sandboxed).

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| UI | Streamlit | Browser-based interface, no HTML/CSS/JS required |
| Agent Framework | LangChain | Agent orchestration, tool calling, agent loops |
| LLM Access | LangChain wrappers | Connects to OpenAI-compatible, Google, xAI, DeepSeek, Ollama endpoints |
| Built-in Tools | LangChain Community Tools | SafeShellTool, Tavily Search API, File Read/Write |
| Database | MySQL 8.0+ | Persistent storage for all platform data |
| ORM | SQLAlchemy 2.0 | Python-to-MySQL bridge, session management |
| Governance | LangChain Callbacks | Token limits, call caps, execution timeouts, RPM throttling |
| Language | Python 3.10+ | Entire stack — backend, UI, tooling |

---

## Repository Structure

```
agentground/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── _common.py            # UI helpers, CSS, session persistence
│   │   ├── agent_executor.py     # LangChain agent executor, multi-agent runs
│   │   ├── agent_manager.py      # Agent CRUD operations
│   │   ├── audit_logger.py       # Audit log write and read operations
│   │   ├── auth_manager.py       # User auth and per-user DB management
│   │   ├── database.py           # SQLAlchemy engine and session factory
│   │   ├── env_manager.py        # Environment CRUD operations
│   │   ├── key_manager.py        # Multi-key rotation and rate-limit mitigation
│   │   ├── model_manager.py      # Model registry CRUD
│   │   ├── provider_adapters.py  # Multi-provider LLM factory
│   │   ├── resource_callback.py  # LangChain callback for resource governance
│   │   ├── run_manager.py        # Run record lifecycle
│   │   ├── settings_manager.py   # User settings K/V storage
│   │   ├── tool_manager.py       # Tool assignment and scope management
│   │   ├── auto_mode/
│   │   │   ├── __init__.py
│   │   │   └── master_agent.py   # Autonomous orchestrator
│   │   └── tools/
│   │       ├── __init__.py
│   │       └── terminal_tool.py  # Whitelisted shell tool wrapper
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── .streamlit/
│       │   └── config.toml       # Streamlit theme config
│       ├── app.py                # Streamlit entry point (Home page)
│       └── pages/
│           ├── 0_Login.py
│           ├── 1_Environments.py
│           ├── 2_Agents.py
│           ├── 3_Tools.py
│           ├── 4_Run.py
│           ├── 5_Audit_Log.py
│           ├── 6_Settings.py
│           └── 7_Auto_Mode.py
├── database/
│   ├── schema.sql                # DDL reference (Core DB)
│   ├── seed.sql                  # Legacy tool data reference
│   └── erd_README.txt            # Instructions for generating the ERD image
├── docs/
│   ├── Iteration_1.docx          # Sprint 1 report
│   ├── Iteration_2.docx          # Sprint 2 report
│   ├── api-docs.md               # Python module API reference
│   └── diagrams/                 # UML diagrams (PNG)
├── .env.example                  # Environment variable template
├── .gitignore
└── README.md
```

---

## Setup on Ubuntu / Debian Linux

### 1. Install system dependencies & Secure MySQL
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git mysql-server
sudo systemctl enable mysql
sudo systemctl start mysql

# Run the security wizard (Answer 'y' to prompts)
sudo mysql_secure_installation
```

Verify the versions:

```bash
python3 --version    # must be 3.10+
mysql --version
git --version
```

## Prerequisites

**All platforms:**
- Python 3.10 or later
- MySQL Server 8.0 or later (running locally or accessible remotely)
- Git

### 2. Setup the Database and Application User

Log into MySQL as the system administrator:

```bash
sudo mysql
```

Run these commands inside the MySQL prompt to create the database:

```sql
CREATE DATABASE IF NOT EXISTS agentground;
-- IMPORTANT: The MySQL user must have privileges to CREATE and DROP 
-- databases matching the pattern 'agentground_%' to support per-user DB isolation.
GRANT ALL PRIVILEGES ON agentground.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON `agentground\_%`.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Clone repository and install dependencies

```bash
git clone https://github.com/rehanfast/agentground
cd agentground
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. Configure environment variables

Create your .env file:

```bash
cp .env.example .env
nano .env
```

Fill in your MySQL credentials and any LLM API keys:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=agentground

OPENAI_API_KEY=sk-...        # if using OpenAI
TAVILY_API_KEY=tvly-...      # required for Web Search tool
```

### 5. Run the application

```bash
streamlit run frontend/src/app.py
```

Streamlit will print a local URL, typically `http://localhost:8501`. Open it in a browser.

To stop the application, press `Ctrl + C` in the terminal.

### Reset Option: The Nuke Option (Start from Scratch)
Use this if you want to completely destroy the project, the database, the user, and the virtual environment, returning your system to the state before you cloned the repository.

**1. Stop the application**
If Streamlit is running, press `Ctrl + C` in your terminal. Deactivate the virtual environment:
```bash
deactivate
```

**2. Delete the MySQL Database**
Run this command to wipe the database and all user databases:
```bash
sudo mysql -e "DROP DATABASE IF EXISTS agentground;"
```

**3. Delete the Project Files and Virtual Environment**
Move out of the project folder and delete the entire directory:
```bash
cd ~
rm -rf agentground
```

**How to run afterwards:**
If you execute the Nuke Option, you must start over from **Step 2 (Setup the Database and Application User)** in the guide above, followed by cloning the repo, building the `venv`, creating the `.env`, and importing the SQL files.

---

## Using a Local LLM (No API Key Required)

You can run agents against a local model using [Ollama](https://ollama.com) without any paid API:

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Ollama exposes an OpenAI-compatible endpoint at:
# http://localhost:11434/v1
```

When registering an agent or adding to the Model Registry in AgentGround, set:
- **Provider:** Ollama (local)
- **API Endpoint URL:** `http://localhost:11434/v1`
- **Model ID:** `llama3`

No API key is needed for local models.

---

## Security Notes

- Never commit the `.env` file. It is listed in `.gitignore`.
- Use `.env.example` with placeholder values for version control.
- The Terminal built-in tool only permits these commands: `ls`, `echo`, `pwd`, `cat`, `mkdir`, `date`, `whoami`, `head`, `tail`, `wc`, `find`, `grep`. All others are blocked.
- Path traversal ('..') is strictly blocked in the Terminal tool.
