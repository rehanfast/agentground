-- AgentGround Database Schema
-- MySQL 8.0+
-- Run: mysql -u root -p agentground < schema.sql

CREATE DATABASE IF NOT EXISTS agentground;
USE agentground;

-- ─── Environments ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS environments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ─── Tools (seeded via seed.sql) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tools (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_builtin  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ─── Agents ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    environment_id  INT          NOT NULL,
    name            VARCHAR(100) NOT NULL,
    api_url         VARCHAR(500) NOT NULL,
    model_name      VARCHAR(100) NOT NULL DEFAULT 'gpt-4',
    system_prompt   TEXT         NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_env
        FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE,
    CONSTRAINT uq_agent_name_per_env
        UNIQUE (environment_id, name)
);

-- ─── Agent ↔ Tool Assignments ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_tools (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    agent_id   INT                        NOT NULL,
    tool_id    INT                        NOT NULL,
    scope      ENUM('private','shared')   NOT NULL DEFAULT 'private',
    created_at DATETIME                   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_at_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_at_tool  FOREIGN KEY (tool_id)  REFERENCES tools(id)  ON DELETE CASCADE,
    CONSTRAINT uq_agent_tool UNIQUE (agent_id, tool_id)
);

-- ─── Runs (populated in Sprint 2) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    environment_id INT          NOT NULL,
    status         ENUM('pending','running','stopped','completed','failed')
                                NOT NULL DEFAULT 'pending',
    started_at     DATETIME,
    ended_at       DATETIME,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_run_env FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);

-- ─── Audit Logs (populated in Sprint 2) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    run_id      INT          NOT NULL,
    agent_id    INT          NOT NULL,
    step_number INT          NOT NULL,
    action_type VARCHAR(50)  NOT NULL,  -- e.g. 'tool_call', 'llm_request', 'llm_response'
    payload     JSON,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_log_run   FOREIGN KEY (run_id)   REFERENCES runs(id)   ON DELETE CASCADE,
    CONSTRAINT fk_log_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
