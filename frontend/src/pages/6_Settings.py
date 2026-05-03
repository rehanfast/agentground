"""
frontend/src/pages/6_Settings.py
Settings — rate limits, run defaults, and the Model Registry.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common          import inject_css, render_sidebar, require_login, get_user_db, show_result
from backend.app.settings_manager import get_all, set_setting
from backend.app.model_manager    import (
    list_models, create_model, update_model, delete_model, get_model,
)
from backend.app.provider_adapters import PROVIDER_BASE_URLS

st.set_page_config(page_title="Settings — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()


def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


tab_limits, tab_registry = st.tabs(["⚙️ Rate Limits & Defaults", "🗂 Model Registry"])

# ════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Rate Limits & Run Defaults
# ════════════════════════════════════════════════════════════════════════════
with tab_limits:
    st.markdown("## Settings")
    st.markdown(
        "<span style='color:#6B7A99;font-size:0.9rem;'>"
        "Changes take effect on the next run.</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    cfg = get_all(db_name=db_name)
    st.markdown('<div class="section-hdr">Rate Limits</div>', unsafe_allow_html=True)

    rpm = st.number_input(
        "Max LLM API calls per minute (RPM)",
        min_value=1, max_value=600,
        value=int(cfg.get("rpm_limit", 20)),
        help="Applied per run — a stop signal is sent when exceeded.",
    )
    daily = st.number_input(
        "Max run starts per day",
        min_value=1, max_value=10000,
        value=int(cfg.get("daily_run_limit", 100)),
    )

    st.markdown('<div class="section-hdr">Run Defaults</div>', unsafe_allow_html=True)
    rc1, rc2 = st.columns(2)
    default_calls   = rc1.number_input("Default max API calls per run", min_value=1,
                                        max_value=500, value=int(cfg.get("max_calls_default", 10)))
    default_timeout_min = rc2.number_input("Default timeout (minutes)", min_value=1,
                                        max_value=60, value=int(cfg.get("timeout_default", 60)) // 60 or 1)

    if st.button("Save", type="primary", use_container_width=True):
        results = [
            set_setting("rpm_limit",         str(rpm),            db_name=db_name),
            set_setting("daily_run_limit",   str(daily),          db_name=db_name),
            set_setting("max_calls_default", str(default_calls),  db_name=db_name),
            set_setting("timeout_default",   str(int(default_timeout_min) * 60),db_name=db_name),
        ]
        if all(ok for ok, _ in results):
            show_result(True, "Settings saved.")
        else:
            show_result(False, "Some settings failed: " + "; ".join(m for ok,m in results if not ok))

# ════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Model Registry
# ════════════════════════════════════════════════════════════════════════════
with tab_registry:
    st.markdown("## Model Registry")
    st.markdown(
        "<span style='color:#6B7A99;font-size:0.9rem;'>"
        "Configure LLM models for Auto Mode. Rank 1 = most intelligent. "
        "Free-tier models are tried first by the master agent unless you specify otherwise."
        "</span>", unsafe_allow_html=True,
    )
    st.divider()

    PROVIDERS = ["openai", "google", "groq", "xai", "deepseek", "ollama", "other"]
    PROVIDER_LABELS = {
        "openai":   "OpenAI",
        "google":   "Google (Gemini)",
        "groq":     "Groq",
        "xai":      "xAI (Grok)",
        "deepseek": "DeepSeek",
        "ollama":   "Ollama (local)",
        "other":    "Other (OpenAI-compatible)",
    }

    # ── Add Model ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Add Model</div>', unsafe_allow_html=True)

    _init("reg_provider", "openai")

    with st.form("add_model_form"):
        fc1, fc2 = st.columns(2)
        display_name = fc1.text_input("Display Name",
                                       placeholder="e.g. Gemini 1.5 Flash (Free)")
        provider     = fc2.selectbox("Provider", PROVIDERS,
                                      format_func=lambda x: PROVIDER_LABELS[x],
                                      key="reg_provider_sel")

        # Auto-fill API URL from provider
        default_url = PROVIDER_BASE_URLS.get(provider, "")
        api_url = st.text_input("API Base URL", value=default_url,
                                 placeholder="https://api.openai.com/v1")
        model_id = st.text_input("Model ID",
                                  placeholder="e.g. gemini-1.5-flash, gpt-4o-mini, grok-3-mini")

        st.markdown("**API Keys** *(one per line — all will be rotated)*")
        keys_raw = st.text_area(
            "API Keys", height=90,
            placeholder="sk-key1\nsk-key2\nsk-key3",
            help="Enter multiple keys (one per line). They will be rotated round-robin "
                 "with automatic cooldown on rate-limit errors.",
            label_visibility="collapsed",
        )
        st.caption(
            "Tip: name your .env variables OPENAI_API_KEY, OPENAI_API_KEY_2, etc. — "
            "the system reads them automatically for fallback even without registry entries."
        )

        rc1, rc2, rc3 = st.columns(3)
        rank      = rc1.number_input("Intelligence Rank", min_value=1, max_value=999,
                                      value=50, help="1 = best. Used by Auto Mode to pick the smartest available model.")
        free_tier = rc2.checkbox("Free Tier", value=True,
                                  help="Auto Mode will try free-tier models first.")
        notes     = fc2.text_input("Notes (optional)", placeholder="Rate limits, context window, etc.")

        submitted = st.form_submit_button("Add Model", type="primary", use_container_width=True)

    if submitted:
        api_keys = [k.strip() for k in keys_raw.splitlines() if k.strip()]
        ok, msg  = create_model(
            display_name=display_name, provider=provider, model_id=model_id,
            api_url=api_url, api_keys=api_keys, intelligence_rank=rank,
            is_free_tier=free_tier, notes=notes, db_name=db_name,
        )
        show_result(ok, msg)
        if ok: st.rerun()

    st.divider()

    # ── Model List ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Registered Models</div>', unsafe_allow_html=True)
    models = list_models(db_name=db_name)

    # Up/down reorder helpers
    def _move_rank(model_id: int, direction: int):
        """Swap this model's rank with the next (direction=+1) or prev (direction=-1)."""
        current = [m for m in list_models(db_name=db_name)]
        idx = next((i for i, m in enumerate(current) if m["id"] == model_id), None)
        if idx is None: return
        swap_idx = idx + direction
        if not (0 <= swap_idx < len(current)): return
        r1 = current[idx]["intelligence_rank"]
        r2 = current[swap_idx]["intelligence_rank"]
        # If ranks are equal, force a gap
        if r1 == r2:
            r2 = r1 + direction
        update_model(model_id,                   intelligence_rank=r2, db_name=db_name)
        update_model(current[swap_idx]["id"],    intelligence_rank=r1, db_name=db_name)

    if not models:
        st.info(
            "No models registered yet. Add models above to enable Auto Mode "
            "and multi-provider key rotation."
        )
        with st.expander("📖 Quick start — free tier model suggestions"):
            st.markdown("""
| Provider | Model ID | API URL | Free? |
|---|---|---|---|
| Google | `gemini-1.5-flash` | `https://generativelanguage.googleapis.com/v1beta/openai/` | ✅ |
| Google | `gemini-1.5-pro` | `https://generativelanguage.googleapis.com/v1beta/openai/` | Limited |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com/v1` | Limited |
| xAI | `grok-3-mini` | `https://api.x.ai/v1` | Limited |
| Ollama | `llama3` | `http://localhost:11434/v1` | ✅ (local) |

Get keys at:
- Google: [aistudio.google.com](https://aistudio.google.com)
- xAI: [console.x.ai](https://console.x.ai)
- DeepSeek: [platform.deepseek.com](https://platform.deepseek.com)
            """)
    else:
        st.caption(f"{len(models)} model(s) — sorted by Intelligence Rank (best first). Use ↑ ↓ to reorder.")
        for m_idx, mc in enumerate(models):
            _init(f"reg_edit_{mc['id']}", False)
            status_icon = "🟢" if mc["is_active"] else "🔴"
            free_badge  = " · 🆓 Free" if mc["is_free_tier"] else ""
            key_count   = len(mc["api_keys"])

            rank_c, exp_c = st.columns([1, 12])
            with rank_c:
                st.markdown(f"**#{m_idx+1}**")
                if m_idx > 0 and st.button("↑", key=f"rank_up_{mc['id']}", help="Make smarter (rank higher)"):
                    _move_rank(mc["id"], -1)
                    st.rerun()
                if m_idx < len(models)-1 and st.button("↓", key=f"rank_dn_{mc['id']}", help="Lower rank"):
                    _move_rank(mc["id"], +1)
                    st.rerun()

            with exp_c:
             with st.expander(
                f"{status_icon} **{mc['display_name']}** · "
                f"`{mc['model_id']}`{free_badge} · "
                f"{key_count} key(s)",
                expanded=st.session_state.get(f"reg_edit_{mc['id']}", False),
             ):
                if not st.session_state[f"reg_edit_{mc['id']}"]:
                    # View mode
                    st.markdown(f"**Provider:** {PROVIDER_LABELS.get(mc['provider'], mc['provider'])}")
                    st.markdown(f"**API URL:** `{mc['api_url']}`")
                    st.markdown(f"**Keys stored:** {key_count} (shown masked)")
                    for i, k in enumerate(mc["api_keys"]):
                        masked = k[:6] + "…" + k[-4:] if len(k) > 10 else "…"
                        st.caption(f"  Key {i+1}: `{masked}`")
                    if mc["notes"]:
                        st.caption(f"Notes: {mc['notes']}")

                    ve, vt, vd = st.columns(3)
                    if ve.button("✏️ Edit", key=f"reg_edit_btn_{mc['id']}", type="primary"):
                        st.session_state[f"reg_edit_{mc['id']}"] = True
                        st.rerun()
                    # Toggle active/inactive
                    toggle_label = "🔴 Disable" if mc["is_active"] else "🟢 Enable"
                    if vt.button(toggle_label, key=f"reg_toggle_{mc['id']}"):
                        ok, msg = update_model(mc["id"], is_active=not mc["is_active"], db_name=db_name)
                        show_result(ok, msg)
                        if ok: st.rerun()
                    if vd.button("🗑 Delete", key=f"reg_del_{mc['id']}"):
                        st.session_state[f"reg_confirm_{mc['id']}"] = True

                    if st.session_state.get(f"reg_confirm_{mc['id']}"):
                        st.warning(f"Delete **{mc['display_name']}**?")
                        cy, cn = st.columns(2)
                        if cy.button("Confirm", key=f"reg_yes_{mc['id']}", type="primary"):
                            ok, msg = delete_model(mc["id"], db_name=db_name)
                            show_result(ok, msg)
                            if ok:
                                del st.session_state[f"reg_confirm_{mc['id']}"]
                                st.rerun()
                        if cn.button("Cancel", key=f"reg_no_{mc['id']}"):
                            del st.session_state[f"reg_confirm_{mc['id']}"]
                            st.rerun()
                else:
                    # Edit mode
                    ec1, ec2 = st.columns(2)
                    e_name = ec1.text_input("Display Name", value=mc["display_name"],
                                             key=f"re_name_{mc['id']}")
                    e_prov = ec2.selectbox("Provider", PROVIDERS,
                                           index=PROVIDERS.index(mc["provider"]) if mc["provider"] in PROVIDERS else 0,
                                           format_func=lambda x: PROVIDER_LABELS[x],
                                           key=f"re_prov_{mc['id']}")
                    e_url  = st.text_input("API URL", value=mc["api_url"],
                                            key=f"re_url_{mc['id']}")
                    e_mid  = st.text_input("Model ID", value=mc["model_id"],
                                            key=f"re_mid_{mc['id']}")
                    st.markdown("**API Keys** *(one per line — replaces existing keys)*")
                    e_keys = st.text_area("Keys", value="\n".join(mc["api_keys"]),
                                           height=80, label_visibility="collapsed",
                                           key=f"re_keys_{mc['id']}")
                    er1, er2 = st.columns(2)
                    e_rank = er1.number_input("Rank", min_value=1, max_value=999,
                                               value=mc["intelligence_rank"],
                                               key=f"re_rank_{mc['id']}")
                    e_free = er2.checkbox("Free Tier", value=mc["is_free_tier"],
                                          key=f"re_free_{mc['id']}")
                    e_notes = st.text_input("Notes", value=mc["notes"],
                                             key=f"re_notes_{mc['id']}")
                    sb, cb = st.columns(2)
                    if sb.button("💾 Save", key=f"re_save_{mc['id']}", type="primary"):
                        new_keys = [k.strip() for k in e_keys.splitlines() if k.strip()]
                        ok, msg  = update_model(
                            mc["id"], db_name=db_name,
                            display_name=e_name, provider=e_prov, api_url=e_url,
                            model_id=e_mid, api_keys=new_keys,
                            intelligence_rank=int(e_rank), is_free_tier=e_free, notes=e_notes,
                        )
                        show_result(ok, msg)
                        if ok:
                            st.session_state[f"reg_edit_{mc['id']}"] = False
                            st.rerun()
                    if cb.button("Cancel", key=f"re_cancel_{mc['id']}"):
                        st.session_state[f"reg_edit_{mc['id']}"] = False
                        st.rerun()
