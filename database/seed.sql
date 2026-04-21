-- AgentGround Seed Data
-- Run AFTER schema.sql
-- mysql -u root -p agentground < seed.sql

USE agentground;

INSERT IGNORE INTO tools (name, description, is_builtin) VALUES
    ('Terminal',
     'Executes whitelisted shell commands on the host machine. Safe commands only (ls, echo, pwd, cat, mkdir, date). Powered by LangChain ShellTool.',
     TRUE),
    ('Web Search',
     'Searches the internet using DuckDuckGo (no API key required). Returns top results as plain text. Powered by LangChain DuckDuckGoSearchRun.',
     TRUE),
    ('File Read/Write',
     'Reads and writes plain text files within a sandboxed working directory. Powered by LangChain FileManagementToolkit.',
     TRUE);
