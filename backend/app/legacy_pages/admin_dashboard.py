"""
pages/admin_dashboard.py — Admin Portal for Legal Aid Case Management.

Five-tab layout:
    Tab 1: Dashboard    — KPIs, NGO distribution, applications table (original)
    Tab 2: NGO Registry — add / edit / deactivate DB-registered NGOs
    Tab 3: Lawyers      — add / edit / availability for DB-registered lawyers
    Tab 4: Case Routing — routing confidence + NGO/lawyer assignment overrides
    Tab 5: Analytics    — charts: urgency, case types, lawyer workload

Architecture: no SQL here — all data via service functions.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from app.utils.application_service import (
    get_all_applications,
    get_stats,
    update_status,
    assign_lawyer,
    assign_ngo,
    get_routing_explanation,
)

from app.utils.legal_taxonomy import (
    LEGAL_CASE_TYPES as CASE_TYPES,
    URGENCY_LEVELS,
    NGO_CATEGORIES,
    LAWYER_EXPERTISE_AREAS,
    EXPERTISE_SUBAREAS,
)
from app.utils.ngo_service import (
    add_ngo, update_ngo, deactivate_ngo, reactivate_ngo,
    get_all_ngos, get_ngo, get_ngo_stats,
)
from app.utils.lawyer_service import (
    add_lawyer, update_lawyer, set_availability,
    get_all_lawyers, get_lawyer, get_lawyers_for_ngo,
    get_lawyer_stats,
)
from app.utils.config import PAKISTAN_CITIES


# ─────────────────────────────────────────────────────────────────────────────
# Shared styling helpers (unchanged from Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

_URGENCY_COLOR = {
    "Critical": ("#ffffff", "#7a0000"),
    "High":     ("#c62828", "#fdecea"),
    "Medium":   ("#e65100", "#fff3e0"),
    "Low":      ("#1b5e20", "#e8f5e9"),
}
_STATUS_COLOR = {
    "pending":   ("#78909c", "#eceff1"),
    "in_review": ("#1565c0", "#e3f2fd"),
    "assigned":  ("#6a1b9a", "#f3e5f5"),
    "resolved":  ("#2e7d32", "#e8f5e9"),
    "closed":    ("#4e342e", "#efebe9"),
}
_STATUS_LABELS = {
    "pending":   "⏳ Pending",
    "in_review": "🔍 In Review",
    "assigned":  "📋 Assigned",
    "resolved":  "✅ Resolved",
    "closed":    "🔒 Closed",
}
_CONF_COLOR = {
    "High":   ("#1b5e20", "#e8f5e9", "🟢"),
    "Medium": ("#e65100", "#fff3e0", "🟡"),
    "Low":    ("#c62828", "#fdecea", "🔴"),
}


def _badge(text: str, fg: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'border-radius:6px;padding:2px 10px;font-size:0.75rem;'
        f'font-weight:600;white-space:nowrap;">{text}</span>'
    )


def _urgency_badge(u: str) -> str:
    fg, bg = _URGENCY_COLOR.get(u, ("#333", "#eee"))
    icons  = {"Critical": "🚨", "High": "🔴", "Medium": "🟡", "Low": "🟢"}
    return _badge(f"{icons.get(u, '')} {u}", fg, bg)


def _status_badge(s: str) -> str:
    fg, bg = _STATUS_COLOR.get(s, ("#333", "#eee"))
    return _badge(_STATUS_LABELS.get(s, s), fg, bg)


def _confidence_badge(c: str) -> str:
    fg, bg, icon = _CONF_COLOR.get(c, ("#333", "#eee", "⚪"))
    src = "DB" if c in ("High", "Medium") else "Static"
    return _badge(f"{icon} {c} ({src})", fg, bg)


def _kpi(icon: str, value: str, label: str, color: str = "#1a3a5c") -> str:
    return (
        f'<div style="background:#fff;border:1px solid #e2e8f0;'
        f'border-top:4px solid {color};border-radius:10px;'
        f'padding:1.1rem 1rem;text-align:center;">'
        f'<div style="font-size:1.8rem;">{icon}</div>'
        f'<div style="font-size:1.6rem;font-weight:700;color:{color};'
        f'line-height:1.1;">{value}</div>'
        f'<div style="font-size:0.78rem;color:#64748b;margin-top:2px;">{label}</div>'
        f'</div>'
    )


def _section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<h4 style="margin:0.2rem 0 0;color:#1a3a5c;">{title}</h4>'
        + (f'<p style="color:#64748b;font-size:0.82rem;margin:0 0 0.8rem;">{subtitle}</p>'
           if subtitle else '<div style="margin-bottom:0.8rem;"></div>'),
        unsafe_allow_html=True,
    )


def _card(html: str) -> None:
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:1rem 1.1rem;margin-bottom:0.6rem;">{html}</div>',
        unsafe_allow_html=True,
    )


def _info_row(label: str, value: str) -> str:
    return (
        f'<div style="margin-bottom:4px;">'
        f'<span style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;'
        f'letter-spacing:0.4px;">{label}</span><br>'
        f'<span style="font-size:0.85rem;color:#1e293b;font-weight:500;">{value}</span>'
        f'</div>'
    )


def _cities() -> list[str]:
    return [c for c in PAKISTAN_CITIES if c != "Any City"]


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def show() -> None:
    """Render the full admin portal."""

    st.markdown(
        '<h2 style="margin:0;padding:0;color:#1a3a5c;font-family:serif;">'
        '🛡️ Admin Portal</h2>'
        '<p style="color:#5a7a8a;font-size:0.85rem;margin:0.2rem 0 1rem;">'
        'Case management · NGO registry · Lawyer management · Analytics</p>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🏢 NGO Registry",
        "⚖️ Lawyers",
        "🔀 Case Routing",
        "📈 Analytics",
    ])

    with tab1:
        _tab_dashboard()
    with tab2:
        _tab_ngos()
    with tab3:
        _tab_lawyers()
    with tab4:
        _tab_routing()
    with tab5:
        _tab_analytics()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Dashboard (original functionality, fully preserved)
# ─────────────────────────────────────────────────────────────────────────────

def _tab_dashboard() -> None:
    # Scoped CSS for the applications table
    st.markdown(
        """<style>
        .app-table-header > div[data-testid="column"] > div {
            background: #f1f5f9;
            border-bottom: 2px solid #cbd5e1;
            padding: 7px 6px;
            font-size: 0.72rem;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        .app-table-row > div[data-testid="column"] > div {
            padding: 6px 6px;
            font-size: 0.8rem;
            color: #1e293b;
            border-bottom: 1px solid #f1f5f9;
            display: flex;
            align-items: center;
            min-height: 36px;
        }
        .app-table-row:hover > div[data-testid="column"] > div {
            background: #f8fafc;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    stats = get_stats()
    apps  = get_all_applications(order_by_priority=True)

    total      = stats["total"]
    by_urgency = stats.get("by_urgency", {})
    by_status  = stats.get("by_status",  {})
    by_ngo     = stats.get("by_ngo",     {})

    # KPI row
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    for col, icon, val, label, color in [
        (k1, "📋", str(total),                          "Total Applications", "#1a3a5c"),
        (k2, "🚨", str(by_urgency.get("Critical", 0)), "Critical",           "#7a0000"),
        (k3, "🔴", str(by_urgency.get("High",     0)), "High Urgency",       "#c62828"),
        (k4, "🟡", str(by_urgency.get("Medium",   0)), "Medium Urgency",     "#e65100"),
        (k5, "🟢", str(by_urgency.get("Low",      0)), "Low Urgency",        "#1b5e20"),
        (k6, "✅", str(by_status.get("resolved",  0)), "Resolved",           "#2e7d32"),
    ]:
        with col:
            st.markdown(_kpi(icon, val, label, color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # NGO distribution
    if by_ngo:
        with st.expander("📊 NGO Distribution", expanded=True):
            ngo_df = (
                pd.DataFrame(by_ngo.items(), columns=["NGO", "Applications"])
                  .sort_values("Applications", ascending=False)
            )
            fig = px.bar(
                ngo_df, x="NGO", y="Applications",
                color="Applications",
                color_continuous_scale=["#a8c4e0", "#1a3a5c"],
                text="Applications",
            )
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_layout(
                height=260, margin=dict(t=20, b=20, l=0, r=0),
                coloraxis_showscale=False,
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(title="", tickangle=-20, gridcolor="#f0f0f0"),
                yaxis=dict(title="Cases", gridcolor="#f0f0f0"),
                font=dict(family="Arial", size=12),
            )
            st.plotly_chart(fig, use_container_width=True)

            ngo_cols = st.columns(min(3, len(by_ngo)))
            for i, (ngo_name, cnt) in enumerate(
                sorted(by_ngo.items(), key=lambda x: x[1], reverse=True)
            ):
                with ngo_cols[i % 3]:
                    
                    st.markdown(
                        f'<div style="background:#f8fafc;border:1px solid #cbd5e1;'
                        f'border-radius:8px;padding:0.7rem;margin-top:4px;">'
                        f'<strong style="color:#1a3a5c;font-size:0.88rem;">{ngo_name}</strong><br>'
                        f'<span style="font-size:0.75rem;color:#475569;">'
                        f'📋 {cnt} case{"s" if cnt != 1 else ""}'
                        f'</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    st.divider()

    # Filters
    st.markdown("**🔍 Filter Applications**")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        all_ngos = sorted(set(a["assigned_ngo"] for a in apps)) if apps else []
        f_ngo = st.selectbox("NGO", ["All NGOs"] + all_ngos,
                             key="d_f_ngo", label_visibility="collapsed")
    with fc2:
        f_case = st.selectbox("Case Type", ["All Types"] + CASE_TYPES,
                              key="d_f_case", label_visibility="collapsed")
    with fc3:
        f_urgency = st.selectbox("Urgency", ["All Urgency"] + URGENCY_LEVELS,
                                 key="d_f_urgency", label_visibility="collapsed")
    with fc4:
        f_status = st.selectbox(
            "Status",
            ["All Status", "pending", "in_review", "assigned", "resolved", "closed"],
            key="d_f_status", label_visibility="collapsed",
        )

    filtered = get_all_applications(
        order_by_priority=True,
        filter_ngo=None       if f_ngo     == "All NGOs"    else f_ngo,
        filter_case_type=None if f_case    == "All Types"   else f_case,
        filter_urgency=None   if f_urgency == "All Urgency" else f_urgency,
        filter_status=None    if f_status  == "All Status"  else f_status,
    )

    st.caption(
        f"Showing **{len(filtered)}** of **{total}** applications"
        + (" (filtered)" if len(filtered) != total else "")
    )

    if not filtered:
        st.info("No applications match the current filters.")
    else:
        # ── Column proportions shared by header AND every data row ────────────
        # Identical ratios = perfect alignment at any viewport width.
        _COLS = [1.1, 1.0, 1.1, 1.6, 0.85, 1.0, 0.95, 0.55]

        # ── Header row ────────────────────────────────────────────────────────
        _TH = (
            "background:#f1f5f9;border-bottom:2px solid #cbd5e1;"
            "padding:7px 6px;font-size:0.72rem;font-weight:700;"
            "color:#475569;text-transform:uppercase;letter-spacing:0.4px;"
        )
        with st.container():
            hc = st.columns(_COLS)
            for col, lbl in zip(hc, [
                "App ID", "Name", "Case Type", "NGO Assigned",
                "Urgency", "Status", "Submitted", "Detail",
            ]):
                col.markdown(f'<div style="{_TH}">{lbl}</div>',
                             unsafe_allow_html=True)

        # ── Data rows ─────────────────────────────────────────────────────────
        _TD = (
            "padding:7px 6px;font-size:0.8rem;color:#1e293b;"
            "border-bottom:1px solid #f1f5f9;min-height:36px;"
        )
        for i, app in enumerate(filtered):
            row_bg  = "#ffffff" if i % 2 == 0 else "#f8fafc"
            td      = _TD + f"background:{row_bg};"
            app_id  = app["application_id"]

            # Session-state key that controls whether the detail panel is open
            detail_key = f"detail_open_{app_id}"
            if detail_key not in st.session_state:
                st.session_state[detail_key] = False

            # Row
            with st.container():
                rc = st.columns(_COLS)
                rc[0].markdown(
                    f'<div style="{td}font-family:monospace;font-size:0.75rem;">'
                    f'{app_id}</div>', unsafe_allow_html=True)
                rc[1].markdown(
                    f'<div style="{td}">{app["name"]}</div>',
                    unsafe_allow_html=True)
                rc[2].markdown(
                    f'<div style="{td}">{app["case_type"]}</div>',
                    unsafe_allow_html=True)
                rc[3].markdown(
                    f'<div style="{td}">{app["assigned_ngo"] or "—"}</div>',
                    unsafe_allow_html=True)
                with rc[4]:
                    st.markdown(
                        f'<div style="{td}">{_urgency_badge(app["urgency"])}</div>',
                        unsafe_allow_html=True)
                with rc[5]:
                    st.markdown(
                        f'<div style="{td}">{_status_badge(app["status"])}</div>',
                        unsafe_allow_html=True)
                rc[6].markdown(
                    f'<div style="{td}">{app["timestamp"][:10]}</div>',
                    unsafe_allow_html=True)
                with rc[7]:
                    btn_lbl = "▲ Hide" if st.session_state[detail_key] else "▼ View"
                    if st.button(btn_lbl, key=f"detail_btn_{app_id}",
                                 use_container_width=True):
                        st.session_state[detail_key] = not st.session_state[detail_key]
                        st.rerun()

            # Detail panel — shown below the row when toggled open
            if st.session_state[detail_key]:
                with st.container():
                    st.markdown(
                        '<div style="border:1px solid #cbd5e1;border-radius:8px;'
                        'padding:1rem;margin:2px 0 6px;background:#fff;">',
                        unsafe_allow_html=True,
                    )
                    _render_application_detail(app)
                    st.markdown('</div>', unsafe_allow_html=True)

    if filtered:
        st.divider()
        csv = pd.DataFrame(filtered).to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export filtered results as CSV", data=csv,
            file_name=f"applications_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", key="d_export_csv",
        )


def _render_application_detail(app: dict) -> None:
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown(
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
            f'border-radius:8px;padding:1rem;">'
            f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:4px;">APPLICATION ID</div>'
            f'<div style="font-weight:700;color:#1a3a5c;font-size:1rem;margin-bottom:0.8rem;">'
            f'{app["application_id"]}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
            + _info_row("Name",      app["name"])
            + _info_row("Contact",   app["contact"])
            + _info_row("Email",     app["email"] or "—")
            + _info_row("City",      app["city"])
            + _info_row("Case Type", app["case_type"])
            + _info_row("Submitted", app["timestamp"][:19])
            + f'</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("**📝 Case Description**")
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:6px;'
            f'padding:0.7rem;font-size:0.83rem;color:#334155;max-height:160px;'
            f'overflow-y:auto;">{app["description"]}</div>',
            unsafe_allow_html=True,
        )

    with col_r:
        ug_fc, ug_bg = _URGENCY_COLOR.get(app["urgency"], ("#333", "#eee"))
        lawyer_lines = "".join(
            f"⚖️ {l.strip()}<br>"
            for l in app["suggested_lawyer"].split(",") if l.strip()
        ) or "—"
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e2e8f0;'
            f'border-radius:8px;padding:0.9rem;">'
            f'<div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">URGENCY</div>'
            f'<div style="background:{ug_bg};color:{ug_fc};border-radius:5px;'
            f'padding:3px 10px;display:inline-block;font-weight:700;'
            f'font-size:0.82rem;margin-bottom:0.7rem;">{app["urgency"]}</div><br>'
            f'<div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">ASSIGNED NGO</div>'
            f'<div style="font-weight:600;color:#1a3a5c;font-size:0.85rem;'
            f'margin-bottom:0.7rem;">🏢 {app["assigned_ngo"]}</div>'
            f'<div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">SUGGESTED LAWYERS</div>'
            f'<div style="font-size:0.83rem;color:#334155;margin-bottom:0.7rem;">'
            f'{lawyer_lines}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Only show notes that were manually written by admin (not system-generated routing notes)
        _admin_note = app.get("notes", "") or ""
        if _admin_note and not _admin_note.startswith("DB-assigned"):
            st.markdown(
                f'<div style="margin-top:6px;background:#fffbeb;border:1px solid #fcd34d;'
                f'border-radius:6px;padding:0.5rem;font-size:0.78rem;color:#78350f;">'
                f'📌 <strong>Notes:</strong> {_admin_note}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**✏️ Update Status**")
        statuses = ["pending", "in_review", "assigned", "resolved", "closed"]
        new_status = st.selectbox(
            "Status", statuses,
            index=statuses.index(app["status"]) if app["status"] in statuses else 0,
            key=f"status_sel_{app['application_id']}", label_visibility="collapsed",
        )
        new_notes = st.text_input(
            "Admin notes",
            value="" if (app.get("notes", "") or "").startswith("DB-assigned") else (app.get("notes", "") or ""),
            key=f"notes_{app['application_id']}",
            placeholder="Add admin notes…", label_visibility="collapsed",
        )
        if st.button("💾 Save", key=f"save_{app['application_id']}",
                     type="primary", use_container_width=True):
            if update_status(app["application_id"], new_status, new_notes):
                st.success(f"Status → **{new_status.replace('_',' ').title()}**")
                st.rerun()
            else:
                st.error("Update failed.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — NGO Registry
# ─────────────────────────────────────────────────────────────────────────────

def _tab_ngos() -> None:
    _section("🏢 NGO Registry",
             "Manage database-registered NGOs used for case routing.")

    # ── Add NGO form ──────────────────────────────────────────────────────────
    with st.expander("➕ Register New NGO", expanded=False):
        with st.form("ngo_add_form", clear_on_submit=True):
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                n_name = st.text_input("NGO Name *",
                                       placeholder="e.g. Lahore Family Law Centre")
                n_cat  = st.selectbox("Category *", NGO_CATEGORIES)
                n_email = st.text_input("Contact Email",
                                        placeholder="info@ngo.org.pk")
            with r1c2:
                n_city  = st.selectbox("City *", _cities())
                n_phone = st.text_input("Contact Phone",
                                        placeholder="e.g. 0300-1234567")
                st.markdown("<br>", unsafe_allow_html=True)
                n_all = st.checkbox(
                    "Handles all case types",
                    help="Check if this NGO accepts referrals for any case category.",
                )

            if st.form_submit_button("💾 Register NGO", type="primary",
                                     use_container_width=True):
                if not n_name.strip():
                    st.error("NGO Name is required.")
                else:
                    try:
                        rec = add_ngo({
                            "ngo_name":          n_name.strip(),
                            "category":          n_cat,
                            "city":              n_city,
                            "contact_phone":     n_phone.strip(),
                            "contact_email":     n_email.strip(),
                            "handles_all_cases": n_all,
                        })
                        st.success(f"✅ NGO registered: **{rec['ngo_name']}** "
                                   f"(`{rec['ngo_id']}`)")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── NGO list ──────────────────────────────────────────────────────────────
    show_inactive = st.checkbox("Show inactive NGOs", key="ngo_show_inactive")
    ngos = get_all_ngos(active_only=not show_inactive)

    if not ngos:
        st.info("No NGOs registered yet. Use the form above to add your first NGO.")
        return

    # Summary strip
    ngo_stats = get_ngo_stats()
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col, icon, val, label, color in [
        (sc1, "🏢", str(ngo_stats["total"]),       "Total NGOs",     "#1a3a5c"),
        (sc2, "✅", str(ngo_stats["active"]),      "Active",         "#2e7d32"),
        (sc3, "⛔", str(ngo_stats["inactive"]),    "Inactive",       "#78909c"),
        (sc4, "🌐", str(ngo_stats["handles_all"]), "Handles All",    "#1565c0"),
    ]:
        with col:
            st.markdown(_kpi(icon, val, label, color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"**{len(ngos)} NGO{'s' if len(ngos) != 1 else ''} found**")

    for ngo in ngos:
        active      = bool(ngo.get("active", 1))
        all_cases   = bool(ngo.get("handles_all_cases", 0))
        border_col  = "#1a3a5c" if active else "#cbd5e1"
        opacity     = "1" if active else "0.6"

        with st.expander(
            f"{'🟢' if active else '⚫'} {ngo['ngo_name']}  ·  {ngo['category']}  ·  {ngo['city']}",
            expanded=False,
        ):
            lc, rc = st.columns([3, 2])

            with lc:
                st.markdown(
                    f'<div style="opacity:{opacity};background:#f8fafc;'
                    f'border:1px solid {border_col};border-left:4px solid {border_col};'
                    f'border-radius:8px;padding:0.9rem;">'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
                    + _info_row("NGO ID",     ngo["ngo_id"])
                    + _info_row("Category",   ngo["category"])
                    + _info_row("City",       ngo["city"] or "—")
                    + _info_row("Phone",      ngo.get("contact_phone") or "—")
                    + _info_row("Email",      ngo.get("contact_email") or "—")
                    + _info_row("Registered", ngo["created_at"][:10])
                    + f'</div>'
                    + (f'<div style="margin-top:6px;">'
                       f'<span style="background:#dbeafe;color:#1e40af;border-radius:4px;'
                       f'padding:2px 8px;font-size:0.72rem;font-weight:600;">'
                       f'🌐 Handles all case types</span></div>'
                       if all_cases else "")
                    + f'</div>',
                    unsafe_allow_html=True,
                )

            with rc:
                st.markdown("**✏️ Edit Details**")
                with st.form(f"ngo_edit_{ngo['ngo_id']}", clear_on_submit=False):
                    e_name  = st.text_input("Name",  value=ngo["ngo_name"],
                                            key=f"ne_name_{ngo['ngo_id']}")
                    e_cat   = st.selectbox("Category", NGO_CATEGORIES,
                                           index=NGO_CATEGORIES.index(ngo["category"])
                                           if ngo["category"] in NGO_CATEGORIES else 0,
                                           key=f"ne_cat_{ngo['ngo_id']}")
                    e_city  = st.selectbox("City", _cities(),
                                           index=_cities().index(ngo["city"])
                                           if ngo["city"] in _cities() else 0,
                                           key=f"ne_city_{ngo['ngo_id']}")
                    e_phone = st.text_input("Phone",
                                            value=ngo.get("contact_phone", ""),
                                            key=f"ne_phone_{ngo['ngo_id']}")
                    e_all   = st.checkbox("Handles all case types",
                                          value=all_cases,
                                          key=f"ne_all_{ngo['ngo_id']}")
                    s1, s2 = st.columns(2)
                    with s1:
                        if st.form_submit_button("💾 Save", type="primary",
                                                 use_container_width=True):
                            try:
                                update_ngo(ngo["ngo_id"], {
                                    "ngo_name":          e_name.strip(),
                                    "category":          e_cat,
                                    "city":              e_city,
                                    "contact_phone":     e_phone.strip(),
                                    "handles_all_cases": e_all,
                                })
                                st.success("Saved")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    with s2:
                        lbl = "✅ Reactivate" if not active else "⛔ Deactivate"
                        if st.form_submit_button(lbl, use_container_width=True):
                            if active:
                                deactivate_ngo(ngo["ngo_id"])
                            else:
                                reactivate_ngo(ngo["ngo_id"])
                            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Lawyers
# ─────────────────────────────────────────────────────────────────────────────

def _tab_lawyers() -> None:
    _section("⚖️ Lawyer Registry",
             "Manage lawyers for deterministic case assignment.")

    # ── Add lawyer form ───────────────────────────────────────────────────────
    
    with st.expander("➕ Register New Lawyer", expanded=False):

        r1c1, r1c2, r1c3 = st.columns(3)

        with r1c1:
            l_name = st.text_input(
                "Full Name *",
                placeholder="e.g. Fatima Noor"
            )

            l_lic = st.text_input(
                "Bar License No. *",
                placeholder="e.g. LHC-1056"
            )

        with r1c2:
            l_city = st.selectbox(
                "City *",
                _cities(),
                key="law_add_city"
            )

            l_main = st.selectbox(
                "Main Expertise *",
                LAWYER_EXPERTISE_AREAS,
                key="law_add_main"
            )

        with r1c3:
            sub_options = EXPERTISE_SUBAREAS.get(l_main, [])

            l_sub = st.multiselect(
                "Sub-Specializations",
                sub_options,
                key="law_add_sub",
                help="Select specific areas within the main expertise.",
            )

            if not sub_options:
                st.caption("No sub-specializations for this expertise.")

            st.markdown("<br>", unsafe_allow_html=True)
            l_avail = st.checkbox(
                "✅ Available for new cases",
                value=True,
                key="law_add_avail"
            )

        # NGO assignment
        all_ngos_list = get_all_ngos(active_only=True)

        ngo_opts = ["(No NGO)"] + [
            n["ngo_name"] for n in all_ngos_list
        ]

        l_ngo_name = st.selectbox(
            "Assign to NGO (optional)",
            ngo_opts,
            key="law_add_ngo"
        )

        l_ngo_id = ""

        if l_ngo_name != "(No NGO)":
            match = next(
                (n for n in all_ngos_list
                if n["ngo_name"] == l_ngo_name),
                None,
            )

            if match:
                l_ngo_id = match["ngo_id"]

        if st.button(
            "💾 Register Lawyer",
            type="primary",
            use_container_width=True
        ):

            if not l_name.strip() or not l_lic.strip():
                st.error("Full name and bar license are required.")

            else:
                try:
                    rec = add_lawyer({
                        "full_name":      l_name.strip(),
                        "bar_license":    l_lic.strip(),
                        "city":           l_city,
                        "expertise_main": l_main,
                        "expertise_sub":  l_sub,
                        "available":      l_avail,
                        "ngo_id":         l_ngo_id,
                    })

                    st.success(
                        f"✅ Registered: **{rec['full_name']}** "
                        f"(`{rec['lawyer_id']}`) — {rec['expertise_main']}"
                    )

                    st.rerun()

                except ValueError as e:
                    st.error(str(e))
                
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Lawyer list ───────────────────────────────────────────────────────────
    lc1, lc2 = st.columns([2, 1])
    with lc1:
        filter_exp = st.selectbox(
            "Filter by expertise",
            ["All Expertise"] + LAWYER_EXPERTISE_AREAS,
            key="law_filter_exp",
            label_visibility="collapsed",
        )
    with lc2:
        show_unavail = st.checkbox("Show unavailable", key="law_show_unavail")

    lawyers = get_all_lawyers(available_only=not show_unavail)
    if filter_exp != "All Expertise":
        lawyers = [l for l in lawyers if l["expertise_main"] == filter_exp]

    if not lawyers:
        st.info("No lawyers registered yet. Use the form above to add your first lawyer.")
        return

    # Stats strip
    l_stats = get_lawyer_stats()
    ls1, ls2, ls3, ls4 = st.columns(4)
    for col, icon, val, label, color in [
        (ls1, "⚖️", str(l_stats["total"]),     "Total Lawyers",     "#1a3a5c"),
        (ls2, "🟢", str(l_stats["available"]),  "Available",         "#2e7d32"),
        (ls3, "🔴", str(l_stats["busy"]),       "Unavailable",       "#c62828"),
        (ls4, "📋", str(l_stats["avg_active_cases"]), "Avg Cases",   "#e65100"),
    ]:
        with col:
            st.markdown(_kpi(icon, str(val), label, color), unsafe_allow_html=True)

    st.markdown(f"<br>**{len(lawyers)} lawyer{'s' if len(lawyers) != 1 else ''} found**",
                unsafe_allow_html=True)

    for lawyer in lawyers:
        avail      = bool(lawyer.get("available", True))
        load       = lawyer.get("active_cases", 0)
        load_color = "#c62828" if load >= 8 else "#e65100" if load >= 4 else "#2e7d32"
        sub_tags   = "".join(
            f'<span style="background:#e0e7ff;color:#3730a3;border-radius:4px;'
            f'padding:1px 7px;font-size:0.7rem;margin-right:3px;">{s}</span>'
            for s in (lawyer.get("expertise_sub") or [])
        )

        with st.expander(
            f"{'🟢' if avail else '🔴'} {lawyer['full_name']}  ·  "
            f"{lawyer['expertise_main']}  ·  {lawyer['city']}  ·  "
            f"{load} active case{'s' if load != 1 else ''}",
            expanded=False,
        ):
            dl, dr = st.columns([3, 2])

            with dl:
                st.markdown(
                    f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                    f'border-left:4px solid {"#1a3a5c" if avail else "#94a3b8"};'
                    f'border-radius:8px;padding:0.9rem;">'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
                    + _info_row("Lawyer ID",    lawyer["lawyer_id"])
                    + _info_row("Bar License",  lawyer["bar_license"])
                    + _info_row("City",         lawyer["city"])
                    + _info_row("NGO",          lawyer.get("ngo_id") or "—")
                    + _info_row("Registered",   lawyer["created_at"][:10])
                    + f'</div>'
                    f'<div style="margin-top:8px;">'
                    f'<span style="font-size:0.7rem;color:#94a3b8;">EXPERTISE</span><br>'
                    f'<span style="font-weight:600;color:#1a3a5c;">'
                    f'{lawyer["expertise_main"]}</span>'
                    f'</div>'
                    + (f'<div style="margin-top:6px;">{sub_tags}</div>'
                       if sub_tags else "")
                    + f'<div style="margin-top:8px;">'
                    f'<span style="font-size:0.7rem;color:#94a3b8;">ACTIVE CASES</span><br>'
                    f'<span style="font-weight:700;color:{load_color};">{load}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with dr:
                st.markdown("**✏️ Edit**")
                with st.form(f"law_edit_{lawyer['lawyer_id']}", clear_on_submit=False):
                    e_main = st.selectbox(
                        "Main Expertise",
                        LAWYER_EXPERTISE_AREAS,
                        index=LAWYER_EXPERTISE_AREAS.index(lawyer["expertise_main"])
                        if lawyer["expertise_main"] in LAWYER_EXPERTISE_AREAS else 0,
                        key=f"le_main_{lawyer['lawyer_id']}",
                    )
                    e_sub = st.multiselect(
                        "Sub-Specializations",
                        EXPERTISE_SUBAREAS.get(e_main, []),
                        default=[s for s in (lawyer.get("expertise_sub") or [])
                                 if s in EXPERTISE_SUBAREAS.get(e_main, [])],
                        key=f"le_sub_{lawyer['lawyer_id']}",
                    )
                    e_city = st.selectbox(
                        "City", _cities(),
                        index=_cities().index(lawyer["city"])
                        if lawyer["city"] in _cities() else 0,
                        key=f"le_city_{lawyer['lawyer_id']}",
                    )
                    # NGO reassignment
                    all_ngos_list = get_all_ngos(active_only=True)
                    ngo_opts_e    = ["(No NGO)"] + [n["ngo_name"] for n in all_ngos_list]
                    cur_ngo_name  = next(
                        (n["ngo_name"] for n in all_ngos_list
                         if n["ngo_id"] == lawyer.get("ngo_id")), "(No NGO)"
                    )
                    e_ngo_sel = st.selectbox(
                        "NGO", ngo_opts_e,
                        index=ngo_opts_e.index(cur_ngo_name)
                        if cur_ngo_name in ngo_opts_e else 0,
                        key=f"le_ngo_{lawyer['lawyer_id']}",
                    )
                    e_ngo_id = ""
                    if e_ngo_sel != "(No NGO)":
                        match = next(
                            (n for n in all_ngos_list if n["ngo_name"] == e_ngo_sel),
                            None,
                        )
                        if match:
                            e_ngo_id = match["ngo_id"]

                    avail_chk = st.checkbox(
                        "Available",
                        value=avail,
                        key=f"le_avail_{lawyer['lawyer_id']}",
                    )

                    s1, s2 = st.columns(2)
                    with s1:
                        if st.form_submit_button("💾 Save", type="primary",
                                                 use_container_width=True):
                            try:
                                update_lawyer(lawyer["lawyer_id"], {
                                    "expertise_main": e_main,
                                    "expertise_sub": e_sub,
                                    "city":           e_city,
                                    "ngo_id":         e_ngo_id,
                                    "available":      avail_chk,
                                })
                                st.success("Saved")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    with s2:
                        toggle_lbl = "🟢 Set Available" if not avail else "🔴 Set Unavailable"
                        if st.form_submit_button(toggle_lbl, use_container_width=True):
                            set_availability(lawyer["lawyer_id"], not avail)
                            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Case Routing
# ─────────────────────────────────────────────────────────────────────────────

def _tab_routing() -> None:
    _section("🔀 Case Routing",
             "Review routing decisions and override NGO or lawyer assignments.")

    apps = get_all_applications(order_by_priority=True)
    if not apps:
        st.info("No applications yet.")
        return

    # Filter to show only un-resolved for routing review
    rt1, rt2 = st.columns([2, 1])
    with rt1:
        conf_filter = st.selectbox(
            "Filter by routing confidence",
            ["All", "High", "Medium", "Low"],
            key="rt_conf_filter",
            label_visibility="collapsed",
        )
    with rt2:
        hide_closed = st.checkbox("Hide resolved/closed", value=True,
                                  key="rt_hide_closed")

    # Build routing view
    rows = []
    for app in apps:
        if hide_closed and app["status"] in ("resolved", "closed"):
            continue
        try:
            expl = get_routing_explanation(app["application_id"])
        except Exception:
            continue
        if conf_filter != "All" and expl["confidence"] != conf_filter:
            continue
        rows.append((app, expl))

    if not rows:
        st.info("No applications match the current filters.")
        return

    st.caption(f"Showing **{len(rows)}** application{'s' if len(rows) != 1 else ''}")

    # Confidence summary
    conf_counts = {"High": 0, "Medium": 0, "Low": 0}
    for _, e in rows:
        conf_counts[e["confidence"]] = conf_counts.get(e["confidence"], 0) + 1

    cc1, cc2, cc3 = st.columns(3)
    for col, c, icon, color in [
        (cc1, "High",   "🟢", "#2e7d32"),
        (cc2, "Medium", "🟡", "#e65100"),
        (cc3, "Low",    "🔴", "#c62828"),
    ]:
        with col:
            st.markdown(
                _kpi(icon, str(conf_counts[c]), f"{c} Confidence", color),
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    for app, expl in rows:
        conf    = expl["confidence"]
        fg, bg, icon = _CONF_COLOR.get(conf, ("#333", "#eee", "⚪"))

        with st.expander(
            f"{icon} {app['application_id']}  ·  {app['name']}  ·  "
            f"{app['case_type']}  ·  Confidence: {conf}",
            expanded=False,
        ):
            rc1, rc2 = st.columns([3, 2])

            with rc1:
                # Routing explanation card
                ngo_src    = "🗄️ Database" if expl["ngo_source"]    == "database" else "📋 Static"
                law_src    = "🗄️ Database" if expl["lawyer_source"] == "database" else "📋 Static"
                note_html  = (
                    f'<div style="margin-top:8px;background:#fffbeb;'
                    f'border:1px solid #fcd34d;border-radius:6px;'
                    f'padding:0.4rem 0.6rem;font-size:0.75rem;color:#78350f;">'
                    f'📌 {expl["routing_note"]}</div>'
                    if expl["routing_note"] else ""
                )
                st.markdown(
                    f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                    f'border-left:4px solid {fg};border-radius:8px;padding:0.9rem;">'
                    f'<div style="margin-bottom:4px;">'
                    f'<span style="background:{bg};color:{fg};border-radius:4px;'
                    f'padding:2px 10px;font-size:0.75rem;font-weight:700;">'
                    f'{icon} {conf} Confidence</span></div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;">'
                    + _info_row("Case Type",         expl["case_type"])
                    + _info_row("City",              expl["city"])
                    + _info_row("Urgency",           expl["urgency"])
                    + _info_row("Expertise Mapped",  expl["expertise_mapped"])
                    + _info_row("NGO Category",      expl["ngo_category_mapped"])
                    + _info_row("Status",            app["status"].replace("_", " ").title())
                    + f'</div>'
                    f'<div style="margin-top:10px;border-top:1px solid #e2e8f0;padding-top:8px;">'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
                    + _info_row(f"Assigned NGO ({ngo_src})",
                                expl["assigned_ngo"] or "—")
                    + _info_row(f"Assigned Lawyer ({law_src})",
                                expl["assigned_lawyer"] or "—")
                    + f'</div></div>'
                    + note_html
                    + f'</div>',
                    unsafe_allow_html=True,
                )

            with rc2:
                st.markdown("**🔧 Override Assignment**")

                # NGO override
                all_ngos_list = get_all_ngos(active_only=True)
                ngo_opts_r    = ["(keep current)"] + [n["ngo_name"] for n in all_ngos_list]
                sel_ngo = st.selectbox(
                    "Reassign NGO",
                    ngo_opts_r,
                    key=f"rt_ngo_{app['application_id']}",
                    label_visibility="collapsed",
                )
                if st.button("🏢 Apply NGO Override",
                             key=f"rt_ngo_btn_{app['application_id']}",
                             use_container_width=True):
                    if sel_ngo == "(keep current)":
                        st.warning("Select an NGO first.")
                    else:
                        ngo_rec = next(
                            (n for n in all_ngos_list if n["ngo_name"] == sel_ngo),
                            None,
                        )
                        if ngo_rec:
                            try:
                                assign_ngo(app["application_id"], ngo_rec["ngo_id"])
                                st.success(f"NGO reassigned → **{sel_ngo}**")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

                st.markdown("---")

                # Lawyer override
                all_lawyers_r = get_all_lawyers(available_only=False)
                law_opts_r    = ["(keep current)"] + [
                    f"{l['full_name']} ({l['bar_license']})" for l in all_lawyers_r
                ]
                sel_law = st.selectbox(
                    "Reassign Lawyer",
                    law_opts_r,
                    key=f"rt_law_{app['application_id']}",
                    label_visibility="collapsed",
                )
                if st.button("⚖️ Apply Lawyer Override",
                             key=f"rt_law_btn_{app['application_id']}",
                             use_container_width=True):
                    if sel_law == "(keep current)":
                        st.warning("Select a lawyer first.")
                    else:
                        bar = sel_law.split("(")[-1].rstrip(")")
                        law_rec = next(
                            (l for l in all_lawyers_r if l["bar_license"] == bar),
                            None,
                        )
                        if law_rec:
                            try:
                                assign_lawyer(app["application_id"],
                                              law_rec["lawyer_id"])
                                st.success(f"Lawyer reassigned → **{law_rec['full_name']}**")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — Analytics
# ─────────────────────────────────────────────────────────────────────────────

def _tab_analytics() -> None:
    _section("📈 Analytics", "Case trends, distribution, and lawyer workload.")

    stats    = get_stats()
    l_stats  = get_lawyer_stats()
    ngo_st   = get_ngo_stats()

    # ── Headline KPIs ─────────────────────────────────────────────────────────
    a1, a2, a3, a4 = st.columns(4)
    for col, icon, val, label, color in [
        (a1, "📋", str(stats["total"]),          "Total Cases",    "#1a3a5c"),
        (a2, "⚖️", str(l_stats["total"]),        "Lawyers",        "#1565c0"),
        (a3, "🏢", str(ngo_st["active"]),         "Active NGOs",    "#2e7d32"),
        (a4, "📊", str(l_stats["avg_active_cases"]),
                                                  "Avg Cases/Lawyer","#e65100"),
    ]:
        with col:
            st.markdown(_kpi(icon, str(val), label, color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ── Charts row ────────────────────────────────────────────────────────────
    ch1, ch2 = st.columns(2)

    def _bar(df, x, y, color_scale, title):
        """Helper: consistent plotly bar chart style."""
        fig = px.bar(df, x=x, y=y, color=y,
                     color_continuous_scale=color_scale, text=y)
        fig.update_traces(textposition="outside", marker_line_width=0)
        fig.update_layout(
            height=280, margin=dict(t=30, b=40, l=0, r=0),
            coloraxis_showscale=False,
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(title="", tickangle=-25, gridcolor="#f0f0f0"),
            yaxis=dict(title=y, gridcolor="#f0f0f0", dtick=1),
            font=dict(family="Arial", size=12),
            title=dict(text=title, font=dict(size=13, color="#1a3a5c")),
        )
        return fig

    with ch1:
        by_type = stats.get("by_case_type", {})
        if by_type:
            df_type = (
                pd.DataFrame(by_type.items(), columns=["Case Type", "Count"])
                  .sort_values("Count", ascending=False)
            )
            st.plotly_chart(
                _bar(df_type, "Case Type", "Count",
                     ["#a8c4e0", "#1a3a5c"], "📁 Cases by Type"),
                use_container_width=True
            )
        else:
            st.info("No case data yet.")

    with ch2:
        by_urg = stats.get("by_urgency", {})
        if by_urg:
            ordered = {k: by_urg.get(k, 0)
                       for k in ["Critical", "High", "Medium", "Low"]}
            df_urg = pd.DataFrame(ordered.items(), columns=["Urgency", "Count"])
            _urg_colors = {"Critical": "#7a0000", "High": "#c62828",
                           "Medium": "#e65100", "Low": "#2e7d32"}
            fig_urg = px.bar(df_urg, x="Urgency", y="Count",
                             color="Urgency",
                             color_discrete_map=_urg_colors,
                             text="Count")
            fig_urg.update_traces(textposition="outside", marker_line_width=0)
            fig_urg.update_layout(
                height=280, margin=dict(t=30, b=40, l=0, r=0),
                showlegend=False,
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(title="", gridcolor="#f0f0f0"),
                yaxis=dict(title="Count", gridcolor="#f0f0f0", dtick=1),
                font=dict(family="Arial", size=12),
                title=dict(text="🚦 Cases by Urgency",
                           font=dict(size=13, color="#1a3a5c")),
            )
            st.plotly_chart(fig_urg, use_container_width=True)
        else:
            st.info("No urgency data yet.")

    st.divider()

    ch3, ch4 = st.columns(2)

    with ch3:
        by_ngo = stats.get("by_ngo", {})
        if by_ngo:
            df_ngo = (
                pd.DataFrame(by_ngo.items(), columns=["NGO", "Cases"])
                  .sort_values("Cases", ascending=False)
            )
            st.plotly_chart(
                _bar(df_ngo, "NGO", "Cases",
                     ["#bbdefb", "#1565c0"], "🏢 Cases by NGO"),
                use_container_width=True
            )
        else:
            st.info("No NGO assignment data yet.")

    with ch4:
        by_exp = l_stats.get("by_expertise", {})
        if by_exp:
            df_exp = (
                pd.DataFrame(by_exp.items(), columns=["Expertise", "Lawyers"])
                  .sort_values("Lawyers", ascending=False)
            )
            st.plotly_chart(
                _bar(df_exp, "Expertise", "Lawyers",
                     ["#c8e6c9", "#2e7d32"], "⚖️ Lawyer Expertise Distribution"),
                use_container_width=True
            )
        else:
            st.info("No lawyer expertise data yet.")

    st.divider()

    # ── Status breakdown table ────────────────────────────────────────────────
    st.markdown("**📋 Application Status Breakdown**")
    by_status = stats.get("by_status", {})
    if by_status:
        status_data = []
        total = stats["total"] or 1
        for s in ["pending", "in_review", "assigned", "resolved", "closed"]:
            cnt  = by_status.get(s, 0)
            pct  = round(cnt / total * 100, 1)
            fg, bg = _STATUS_COLOR.get(s, ("#333", "#eee"))
            status_data.append({
                "Status":  _STATUS_LABELS.get(s, s),
                "Count":   cnt,
                "Percent": f"{pct}%",
            })
        df_stat = pd.DataFrame(status_data)
        st.dataframe(df_stat, use_container_width=True, hide_index=True)
    else:
        st.info("No status data yet.")

    st.divider()

    # ── Top-loaded lawyers ────────────────────────────────────────────────────
    st.markdown("**📋 Top Loaded Lawyers**")
    top = l_stats.get("top_loaded", [])
    if top:
        top_data = []
        for l in top:
            top_data.append({
                "Name":        l["full_name"],
                "Expertise":   l["expertise_main"],
                "City":        l["city"],
                "Active Cases": l["active_cases"],
                "Available":   "🟢 Yes" if l.get("available") else "🔴 No",
            })
        st.dataframe(pd.DataFrame(top_data), use_container_width=True,
                     hide_index=True)
    else:
        st.info("No lawyer workload data yet.")

    # ── NGO registry summary ──────────────────────────────────────────────────
    if ngo_st.get("by_category"):
        st.divider()
        df_ngo_cat = (
            pd.DataFrame(ngo_st["by_category"].items(),
                         columns=["Category", "NGOs"])
              .sort_values("NGOs", ascending=False)
        )
        fig_cat = px.bar(df_ngo_cat, x="Category", y="NGOs",
                         color="NGOs",
                         color_continuous_scale=["#e0e7ff", "#3730a3"],
                         text="NGOs",
                         title="🏢 NGOs by Category")
        fig_cat.update_traces(textposition="outside", marker_line_width=0)
        fig_cat.update_layout(
            height=280, margin=dict(t=40, b=40, l=0, r=0),
            coloraxis_showscale=False,
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(title="", tickangle=-20, gridcolor="#f0f0f0"),
            yaxis=dict(title="NGOs", gridcolor="#f0f0f0", dtick=1),
            font=dict(family="Arial", size=12),
        )
        st.plotly_chart(fig_cat, use_container_width=True)