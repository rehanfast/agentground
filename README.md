# AgentGround

**AI Agent Sandbox Platform** — A Python-native sandbox for experimenting with autonomous AI agents in a governed, observable environment.

AgentGround provides isolated workspaces (environments) where AI agents can be registered, assigned tools, executed against real LLM APIs, and audited step by step — all through a browser-based Streamlit interface. No command-line expertise or frontend development is required for normal use.

---

## Team

| Name | Roll No. | Role |
|---|---|---|
| Rehan Abid | 24L-2573 | Solo Developer |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| UI | Streamlit | Browser-based interface, no HTML/CSS/JS required |
| Agent Framework | LangChain | Agent orchestration, tool calling, agent loops |
| LLM Access | LangChain model wrappers | Connects to any OpenAI-compatible endpoint |
| Built-in Tools | LangChain Community Tools | ShellTool, DuckDuckGoSearch, FileManagement |
| Database | MySQL 8.0+ | Persistent storage for all platform data |
| ORM | SQLAlchemy 2.0 | Python-to-MySQL bridge, session management |
| Governance | LangChain Callbacks | Token limits, call caps, execution timeouts |
| Language | Python 3.10+ | Entire stack — backend, UI, tooling |

---

## Repository Structure

```
agentground/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLAlchemy engine and session factory
│   │   ├── models.py             # ORM models mirroring schema.sql
│   │   ├── env_manager.py        # Environment CRUD operations
│   │   ├── agent_manager.py      # Agent CRUD operations
│   │   ├── tool_manager.py       # Tool assignment and scope management
│   │   ├── run_manager.py        # Run record lifecycle
│   │   ├── agent_executor.py     # LangChain agent executor, multi-agent runs
│   │   ├── audit_logger.py       # Audit log write and read operations
│   │   ├── resource_callback.py  # LangChain callback for resource governance
│   │   └── tools/
│   │       ├── __init__.py
│   │       └── terminal_tool.py  # Whitelisted shell tool wrapper
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app.py                # Streamlit entry point (Home page)
│       └── pages/
│           ├── 1_Environments.py
│           ├── 2_Agents.py
│           ├── 3_Tools.py
│           ├── 4_Run.py
│           └── 5_Audit_Log.py
├── database/
│   ├── schema.sql                # DDL — run this before the application
│   ├── seed.sql                  # Initial tool data
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

Run these commands inside the MySQL prompt to create the database, lower the local password policy, and create a dedicated app user:

```sql
CREATE DATABASE IF NOT EXISTS agentground;
SET GLOBAL validate_password.policy=LOW;
CREATE USER IF NOT EXISTS 'agent_user'@'localhost' IDENTIFIED BY 'rehan1977';
GRANT ALL PRIVILEGES ON agentground.* TO 'agent_user'@'localhost';
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
nano .env
```

Fill in your MySQL credentials and any LLM API keys:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=agentground

OPENAI_API_KEY=sk-...        # if using OpenAI
ANTHROPIC_API_KEY=...         # if using Anthropic
```

### 5. Run the database schema and seed data

Import the tables and default data:

```bash
sudo mysql agentground < database/schema.sql
sudo mysql agentground < database/seed.sql
```

### 6. Run the application

```bash
streamlit run frontend/src/app.py
```

Streamlit will print a local URL, typically `http://localhost:8501`. Open it in a browser.

To stop the application, press `Ctrl + C` in the terminal.

### Reset Option 1: Soft Reset (Wipe Database Data Only)
Use this if you have been testing the app, the database is full of junk runs/logs, and you want to clear the data **without** reinstalling Python packages or deleting your project files.

**1. Wipe and recreate the database:**
Run this single command from your terminal to drop the old database and create a fresh one:
```bash
sudo mysql -e "DROP DATABASE IF EXISTS agentground; CREATE DATABASE agentground;"
```

**2. Re-import the fresh schema and seed data:
Make sure you are in your agentground directory, then run:

```bash
sudo mysql agentground < database/schema.sql
sudo mysql agentground < database/seed.sql
```
**3. Run the app again:
Your venv and .env are still intact, so you can just start the app right away:

```bash
source venv/bin/activate
streamlit run frontend/src/app.py
```

### Reset Option 2: The Nuke Option (Start from Scratch)
Use this if you want to completely destroy the project, the database, the user, and the virtual environment, returning your system to the state before you cloned the repository.

**1. Stop the application**
If Streamlit is running, press `Ctrl + C` in your terminal. Deactivate the virtual environment:
```bash
deactivate
```

**2. Delete the MySQL Database and User**
Run this command to wipe the database and the `agent_user` from your system:
```bash
sudo mysql -e "DROP DATABASE IF EXISTS agentground; DROP USER IF EXISTS 'agent_user'@'localhost'; FLUSH PRIVILEGES;"
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

When registering an agent in AgentGround, set:
- **API Endpoint URL:** `http://localhost:11434/v1`
- **Model Name:** `llama3`

No API key is needed for local models.

---

## Security Notes

- Never commit the `.env` file. It is listed in `.gitignore`.
- Use `.env.example` with placeholder values for version control.
- The Terminal built-in tool only permits these commands: `ls`, `echo`, `pwd`, `cat`, `mkdir`, `date`, `whoami`, `head`, `tail`, `wc`, `find`, `grep`. All others are blocked.

---

## Sprint Progress

| Sprint | Weeks | Status | Key Deliverables |
|---|---|---|---|
| Sprint 1 | 1 — 2 | Complete | MySQL schema, environment and agent CRUD, Terminal tool, Streamlit UI (5 pages) |
| Sprint 2 | 3 — 4 | Complete | LangChain agent executor, resource limits, multi-agent runs, audit log viewer |
| Sprint 3 | 5 — 6 | Planned | Web Search and File tools, trace viewer improvements, Python module interface |
