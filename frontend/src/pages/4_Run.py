"""
frontend/src/pages/4_Run.py
Run execution.
Fixes:
  - Checkbox conflict: initialize session_state key BEFORE rendering, never pass value=
  - Settings sync: widget keys initialized from settings_manager defaults
  - Re-use: writes to exact widget keys so Streamlit reads new values on rerun
"""

import sys, os, time, threading, queue
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common        import inject_css, render_sidebar, require_login, get_user_db
from backend.app.env_manager    import list_environments
from backend.app.agent_manager  import list_agents
from backend.app.run_manager    import create_run, update_run_status, get_runs_for_env
from backend.app.agent_executor import run_sequential
from backend.app.settings_manager import get_all as get_settings

st.set_page_config(page_title="Run — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name  = get_user_db()
username = st.session_state.get("user", {}).get("username", "")


def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


st.markdown("## Run")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Trigger single or multi-agent sequential runs.</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Environment ───────────────────────────────────────────────────────────────
environments = list_environments(db_name=db_name)
if not environments:
    st.warning("No environments. Create one first.")
    st.stop()

env_options = {e["name"]: e["id"] for e in environments}
env_names   = list(env_options.keys())
_init("run_sel_env", env_names[0])

sel_env_name = st.selectbox(
    "Environment", env_names,
    index=env_names.index(st.session_state["run_sel_env"])
          if st.session_state["run_sel_env"] in env_names else 0,
    key="run_env_sel",
)
st.session_state["run_sel_env"] = st.session_state["run_env_sel"]
sel_env_id = env_options[sel_env_name]

agents = list_agents(sel_env_id, db_name=db_name)
if not agents:
    st.warning(f"No agents in **{sel_env_name}**.")
    st.stop()

agent_map = {a["id"]: a["name"] for a in agents}

st.divider()

# ── Init widget keys from settings (only once — _init skips if already set) ──
settings = get_settings(db_name=db_name)
_init("run_agent_order",     [])
_init("run_msg_input",       "")
_init("run_max_calls_input", int(settings.get("max_calls_default", 10)))
_init("run_timeout_input",   int(settings.get("timeout_default", 60)) // 60 or 1)
_init("run_rpm_input",       int(settings.get("rpm_limit", 20)))

# Init checkbox keys BEFORE rendering to avoid the widget-conflict warning
for ag in agents:
    _init(f"chk_{ag['id']}", False)

# ── Re-use config ─────────────────────────────────────────────────────────────
if st.session_state.get("run_load_config"):
    cfg = st.session_state.pop("run_load_config")
    if cfg:
        valid_ids = [i for i in cfg.get("agent_ids", []) if i in agent_map]
        st.session_state["run_agent_order"]     = valid_ids
        st.session_state["run_msg_input"]       = cfg.get("initial_message", "")
        st.session_state["run_max_calls_input"] = int(cfg.get("max_calls",    st.session_state["run_max_calls_input"]))
        st.session_state["run_timeout_input"]   = int(cfg.get("timeout_secs", st.session_state["run_timeout_input"] * 60)) // 60 or 1
        st.session_state["run_rpm_input"]       = int(cfg.get("rpm_limit",    st.session_state["run_rpm_input"]))
        # Sync checkbox keys to match loaded pipeline
        for ag in agents:
            st.session_state[f"chk_{ag['id']}"] = ag["id"] in valid_ids
        st.success(f"Settings loaded from Run {cfg.get('run_id', '?')} — review and click Run.")

# ── Agent pipeline (checkboxes — no value= to avoid widget conflict) ──────────
st.markdown('<div class="section-hdr">Agent Pipeline</div>', unsafe_allow_html=True)
st.caption("Check agents to include, then reorder with ↑ ↓.")

order     = st.session_state["run_agent_order"]
order_set = set(order)

cols = st.columns(min(len(agents), 4))
for i, agent in enumerate(agents):
    # Key was pre-initialized above with _init — no value= passed here
    checked = cols[i % len(cols)].checkbox(agent["name"], key=f"chk_{agent['id']}")
    if checked and agent["id"] not in order_set:
        order.append(agent["id"])
        order_set.add(agent["id"])
    elif not checked and agent["id"] in order_set:
        order.remove(agent["id"])
        order_set.discard(agent["id"])
st.session_state["run_agent_order"] = order

if order:
    st.markdown("**Execution order:**")
    for idx, aid in enumerate(order):
        pc1, pc2, pc3, pc4 = st.columns([3, 0.4, 0.4, 0.4])
        pc1.markdown(f"`{idx+1}.` **{agent_map.get(aid, f'Agent {aid}')}**")
        if idx > 0 and pc2.button("↑", key=f"up_{aid}_{idx}"):
            order[idx-1], order[idx] = order[idx], order[idx-1]
            st.session_state["run_agent_order"] = order
            st.rerun()
        if idx < len(order)-1 and pc3.button("↓", key=f"dn_{aid}_{idx}"):
            order[idx], order[idx+1] = order[idx+1], order[idx]
            st.session_state["run_agent_order"] = order
            st.rerun()
        if pc4.button("✕", key=f"rm_{aid}_{idx}"):
            order.remove(aid)
            st.session_state[f"chk_{aid}"] = False
            st.session_state["run_agent_order"] = order
            st.rerun()
else:
    st.info("Check at least one agent.")

# ── Settings (all widgets use explicit keys — Re-use writes to these keys) ────
st.markdown('<div class="section-hdr">Settings</div>', unsafe_allow_html=True)

user_msg    = st.text_area("Initial message", height=90,
                            placeholder="What task should the agent(s) perform?",
                            key="run_msg_input")
r1, r2, r3  = st.columns(3)
max_calls   = r1.number_input("Max API calls",        min_value=1, max_value=500,
                               key="run_max_calls_input")
timeout_min = r2.number_input("Timeout (min)",          min_value=1, max_value=60,
                               key="run_timeout_input")
rpm_limit   = r3.number_input("Max calls/min (RPM)",  min_value=1, max_value=600,
                               key="run_rpm_input")
st.divider()

# ── Run controls ──────────────────────────────────────────────────────────────
_init("run_active", False)
_init("run_result", None)
_init("run_error",  None)
_init("stop_event", None)
_init("result_q",   None)
_init("run_log_q",  None)
_init("run_log",    [])

rc1, rc2, _ = st.columns([1, 1, 5])
run_btn  = rc1.button("▶ Run", type="primary",
                       disabled=bool(st.session_state.run_active)
                                or not user_msg.strip() or not order)
stop_btn = rc2.button("⏹ Stop", disabled=not st.session_state.run_active)

if stop_btn and st.session_state.stop_event:
    st.session_state.stop_event.set()
    st.warning("Stop signal sent.")

if run_btn and user_msg.strip() and order:
    run_config = {
        "agent_ids":       order,
        "initial_message": user_msg,
        "max_calls":       int(max_calls),
        "timeout_secs":    int(timeout_min) * 60,
        "rpm_limit":       int(rpm_limit),
        "agent_names":     [agent_map.get(i, str(i)) for i in order],
    }
    run_id     = create_run(sel_env_id, config=run_config, db_name=db_name)
    stop_event = threading.Event()
    result_q   = queue.Queue()

    st.session_state.update({
        "run_active": True, "run_result": None,
        "run_error": None, "stop_event": stop_event, "result_q": result_q,
        "run_log": [], "run_log_q": None,
    })

    log_q = queue.Queue()
    _db, _user, _env_id, _run_id = db_name, username, sel_env_id, run_id
    _order = list(order)
    st.session_state["run_log_q"] = log_q

    def _worker():
        try:
            result = run_sequential(
                agent_ids=_order, environment_id=_env_id, run_id=_run_id,
                initial_message=user_msg, max_calls=int(max_calls),
                timeout_secs=int(timeout_min) * 60, rpm_limit=int(rpm_limit),
                stop_event=stop_event,
                db_name=_db, username=_user, log_queue=log_q,
            )
            result_q.put(("ok", result))
        except Exception as exc:
            update_run_status(_run_id, "failed", db_name=_db)
            result_q.put(("err", str(exc)))

    threading.Thread(target=_worker, daemon=True).start()
    st.rerun()

if st.session_state.run_active:
    # Drain live log queue
    lq = st.session_state.get("run_log_q")
    if lq:
        while True:
            try: st.session_state["run_log"].append(lq.get_nowait())
            except queue.Empty: break
    try:
        kind, payload = st.session_state.result_q.get_nowait()
        st.session_state.run_active = False
        if kind == "ok": st.session_state.run_result = payload
        else:            st.session_state.run_error  = payload
    except queue.Empty:
        # Show live progress
        if st.session_state["run_log"]:
            st.markdown('<div class="section-hdr">Live Progress</div>', unsafe_allow_html=True)
            for msg in st.session_state["run_log"][-30:]:
                st.markdown(msg)
        with st.spinner("Running…"):
            time.sleep(0.5)
        st.rerun()

if st.session_state.run_error:
    st.error(f"Run failed: {st.session_state.run_error}")
    st.session_state.run_error = None

if st.session_state.run_result:
    result = st.session_state.run_result
    fn = {"completed": st.success, "stopped": st.warning, "failed": st.error}
    fn.get(result["status"], st.info)(f"Run {result['run_id']} — {result['status']}")
    for r in result["results"]:
        with st.expander(f"Output — {agent_map.get(r['agent_id'], 'Agent')}", expanded=True):
            st.markdown(r["output"])
    st.info(f"Full trace on Audit Log — Run ID: {result['run_id']}")
    st.session_state.run_result = None

# ── Run history ───────────────────────────────────────────────────────────────
st.divider()
st.markdown(f'<div class="section-hdr">Run History — {sel_env_name}</div>',
            unsafe_allow_html=True)
runs = get_runs_for_env(sel_env_id, db_name=db_name)
if not runs:
    st.info("No runs yet.")
else:
    cls_map = {"completed":"pill-ok","running":"pill-run","failed":"pill-fail","stopped":"pill-stop"}
    for run in runs[:20]:
        cls  = cls_map.get(run["status"], "pill-run")
        cfg  = run.get("config") or {}
        names = cfg.get("agent_names", [f"Agent {i}" for i in cfg.get("agent_ids", [])])
        pipe  = " → ".join(names) if names else "—"

        with st.expander(
            f"Run {run['id']}  ·  {run['status'].upper()}  ·  "
            f"{run['started_at'] or '—'}  ·  {run['log_count']} steps"
        ):
            st.markdown(
                f"<span class='pill {cls}'>{run['status']}</span>&nbsp;&nbsp;"
                f"<small style='color:#999;'>{pipe}</small>",
                unsafe_allow_html=True,
            )
            if cfg:
                msg_prev = (cfg.get("initial_message") or "")[:200]
                if msg_prev: st.markdown(f"**Message:** {msg_prev}")
                sc1, sc2, sc3 = st.columns(3)
                sc1.caption(f"Max calls: {cfg.get('max_calls','—')}")
                sc2.caption(f"Timeout: {cfg.get('timeout_secs','—')}s")
                sc3.caption(f"RPM: {cfg.get('rpm_limit','—')}")

            c_reuse, c_trace = st.columns(2)
            if c_reuse.button("♻ Re-use settings", key=f"reuse_{run['id']}",
                               disabled=not cfg):
                cfg["run_id"] = run["id"]
                st.session_state["run_load_config"] = cfg
                st.rerun()
            c_trace.page_link("pages/5_Audit_Log.py", label="📋 View trace")
