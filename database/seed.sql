-- =========================================================================
-- WARNING: LEGACY / REFERENCE ONLY
-- DO NOT RUN THIS SCRIPT MANUALLY!
--
-- This script was used in Sprint 1. In the current architecture, tools are
-- seeded automatically via Python (`backend.app.database._seed_tools`)
-- into each user's isolated `agentground_<username>` database.
-- Running this script on the master `agentground` database will fail
-- or pollute the global schema.
-- =========================================================================

USE agentground;

INSERT IGNORE INTO tools (name, description, is_builtin) VALUES
    ('Terminal',
     'Executes whitelisted shell commands on the host machine. '
     'Permitted: ls, echo, pwd, cat, mkdir, date, whoami, head, tail, wc, find, grep. '
     'Powered by SafeShellTool (LangChain BaseTool subclass).',
     TRUE),
    ('Web Search',
     'Searches the web using Tavily Search API (max 3 results). '
     'Requires TAVILY_API_KEY environment variable. '
     'Powered by LangChain TavilySearchResults.',
     TRUE),
    ('File Read/Write',
     'Reads and writes plain text files within a sandboxed working directory. '
     'Powered by LangChain FileManagementToolkit.',
     TRUE);
