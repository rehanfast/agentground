# AgentGround — API Documentation (Python Module Interface)

Sprint 1 does not expose a REST API. All functionality is accessed either through the **Streamlit UI** or by importing the backend Python modules directly (e.g. from a Jupyter notebook). A REST API layer is planned for Sprint 3.

---

## Module: `backend.app.env_manager`

### `create_environment(name, description="")`
Creates a new environment.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | ✅ | Unique name (max 100 chars) |
| `description` | `str` | ❌ | Optional description |

**Returns:** `(bool, str)` — `(True, "ok message")` or `(False, "error message")`

---

### `list_environments()`
Returns all environments.

**Returns:** `list[dict]` — each dict has keys: `id`, `name`, `description`, `created_at`, `agent_count`

---

### `get_environment(env_id)`
Returns a single environment by ID.

**Returns:** `dict | None`

---

### `delete_environment(env_id)`
Deletes an environment and all its children (cascade).

**Returns:** `(bool, str)`

---

## Module: `backend.app.agent_manager`

### `create_agent(environment_id, name, api_url, model_name, system_prompt)`
Registers a new agent in an environment.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `environment_id` | `int` | ✅ | FK to environments table |
| `name` | `str` | ✅ | Unique within environment |
| `api_url` | `str` | ✅ | Valid http/https URL |
| `model_name` | `str` | ✅ | e.g. `"gpt-4"` |
| `system_prompt` | `str` | ✅ | Non-empty system prompt |

**Returns:** `(bool, str)`

---

### `list_agents(environment_id)`
Returns all agents in a given environment.

**Returns:** `list[dict]` — each dict has keys: `id`, `name`, `api_url`, `model_name`, `system_prompt`, `created_at`, `updated_at`

---

### `get_agent(agent_id)`
Returns a single agent by ID.

**Returns:** `dict | None`

---

### `update_system_prompt(agent_id, new_prompt)`
Updates the system prompt of an existing agent.

**Returns:** `(bool, str)`

---

### `delete_agent(agent_id)`
Deletes an agent and all its tool assignments.

**Returns:** `(bool, str)`

---

## Module: `backend.app.tool_manager`

### `list_tools()`
Returns all tools in the tools table.

**Returns:** `list[dict]` — keys: `id`, `name`, `description`, `is_builtin`

---

### `get_agent_tools(agent_id)`
Returns all tools assigned to a specific agent.

**Returns:** `list[dict]` — keys: `assignment_id`, `tool_id`, `tool_name`, `description`, `scope`, `created_at`

---

### `assign_tool(agent_id, tool_id, scope="private")`
Assigns a tool to an agent.

| Parameter | Type | Values |
|---|---|---|
| `scope` | `str` | `"private"` or `"shared"` |

**Returns:** `(bool, str)`

---

### `remove_tool_assignment(assignment_id)`
Removes a tool assignment from an agent.

**Returns:** `(bool, str)`

---

## Module: `backend.app.tools.terminal_tool`

### `run_terminal_command(command)`
Runs a whitelisted shell command and returns its stdout.

**Raises:** `ValueError` if the command is not on the whitelist.

**Allowed commands:** `ls`, `echo`, `pwd`, `cat`, `mkdir`, `date`, `whoami`, `head`, `tail`, `wc`, `find`, `grep`

---

### `get_langchain_terminal_tool()`
Returns a LangChain `ShellTool` instance pre-configured with the whitelist. Used by the agent executor in Sprint 2.

**Returns:** `ShellTool` instance
