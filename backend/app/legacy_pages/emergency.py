import streamlit as st
import json
from app.utils.config import EMERGENCY_CONTACTS, NGO_FILE
from app.utils.translations import T


def show() -> None:
    lang = st.session_state.get("language", "English")
    t    = T(lang)

    # Apply RTL layout when Urdu
    if lang == "Urdu":
        st.markdown("""<style>
        .main input[type="text"], .main input[type="email"],
        .main input[type="number"], .main textarea {
            direction: rtl !important; text-align: right !important;
        }
        .main .stSelectbox [data-baseweb="select"] > div,
        .main .stSelectbox [data-baseweb="menu"] li,
        .main .stSelectbox [data-baseweb="popover"] li {
            direction: rtl !important; text-align: right !important;
        }
        .main div[data-testid="stWidgetLabel"] p,
        .main .stTextInput label, .main .stTextArea label,
        .main .stSelectbox label, .main .stRadio label p,
        .main div[data-testid="stCaptionContainer"],
        .main p, .main li, .main h1, .main h2,
        .main h3, .main h4, .main h5 {
            direction: rtl !important; text-align: right !important;
        }
        </style>""", unsafe_allow_html=True)

    # ── Hero banner ───────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#9b2335,#c0392b);'
        f'border-radius:16px;padding:2.5rem 2rem;margin-bottom:2rem;'
        f'border-left:6px solid #f9ca24;">'
        f'<h1 style="color:#fff;margin:0;font-size:2rem;">{t("emg_title")}</h1>'
        f'<p style="color:#ffd7d7;margin:0.5rem 0 0;">{t("emg_subtitle")}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.warning(t("emg_danger"), icon="🚨")

    # ── Emergency helpline cards ──────────────────────────────────────────────
    st.subheader(t("emg_helplines_h"))

    # Map English label → translation key (label stays a proper noun but localised)
    _contact_label_map = {
        "Police":            t("emg_contact_police"),
        "Edhi Foundation":   t("emg_contact_edhi"),
        "Women Helpline":    t("emg_contact_women"),
        "Cyber Crime (FIA)": t("emg_contact_cyber"),
        "Rescue":            t("emg_contact_rescue"),
    }

    contacts = EMERGENCY_CONTACTS
    c1, c2, c3 = st.columns(3)
    cols_map = [c1, c2, c3, c1, c2]
    for col, contact in zip(cols_map, contacts):
        display_label = _contact_label_map.get(contact["label"], contact["label"])
        with col:
            st.markdown(
                f'<div style="background:{contact["color"]};border-radius:14px;'
                f'padding:1.4rem 1rem;text-align:center;margin-bottom:1rem;'
                f'box-shadow:0 4px 14px rgba(0,0,0,0.15);">'
                f'<div style="font-size:2.2rem;">{contact["icon"]}</div>'
                f'<div style="color:#fff;font-weight:700;font-size:0.95rem;margin-top:4px;">'
                f'{display_label}</div>'
                f'<div style="color:#fff;font-size:2rem;font-weight:900;letter-spacing:2px;'
                f'background:rgba(255,255,255,0.15);border-radius:8px;padding:2px 8px;'
                f'display:inline-block;margin-top:4px;">{contact["number"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── NGO directory ─────────────────────────────────────────────────────────
    st.subheader(t("emg_ngo_h"))
    try:
        with open(NGO_FILE, "r", encoding="utf-8") as f:
            ngos = json.load(f)
    except Exception:
        ngos = []

    type_colors = {
        "Women Rights":                "#7b2d5e",
        "Emergency / Social Services": "#9b2335",
        "Legal Aid":                   "#1a3a5c",
        "Human Rights":                "#1d6b3a",
        "Women & Child Rights":        "#c0392b",
        "Child & Family Protection":   "#e67e22",
        "Gender Violence":             "#8e44ad",
        "Labour Rights":               "#2c5282",
        "Youth & Labour Rights":       "#2b6cb0",
        "Cybercrime / Digital Rights": "#2d3748",
    }

    for ngo in ngos:
        bc  = type_colors.get(ngo.get("type", ""), "#555")
        ws  = (f'<a href="{ngo["website"]}" target="_blank" '
               f'style="color:#1a73e8;font-size:0.82rem;">🔗 {t("emg_website_link")}</a>'
               if ngo.get("website") else "")
        svc = (f'<div style="color:#555;font-size:0.83rem;margin-top:3px;">'
               f'🛎️ {ngo["services"]}</div>'
               if ngo.get("services") else "")
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e0e0e0;'
            f'border-left:5px solid {bc};border-radius:12px;'
            f'padding:0.9rem 1.2rem;margin-bottom:0.7rem;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.05);">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'<div><strong style="color:#1a3a5c;">{ngo["name"]}</strong>'
            f'<span style="background:{bc};color:#fff;border-radius:20px;'
            f'padding:1px 10px;font-size:0.72rem;margin-left:8px;">{ngo.get("type","")}</span>'
            f'<div style="color:#555;margin-top:4px;font-size:0.9rem;">'
            f'📍 {ngo.get("city","")} &nbsp;|&nbsp; '
            f'📞 <strong>{ngo.get("phone","")}</strong></div>{svc}</div>'
            f'<div>{ws}</div></div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Safety tips ───────────────────────────────────────────────────────────
    st.subheader(t("emg_safety_h"))
    tips = [
        ("📝", t("emg_tip1_t"), t("emg_tip1_d")),
        ("⏰", t("emg_tip2_t"), t("emg_tip2_d")),
        ("📚", t("emg_tip3_t"), t("emg_tip3_d")),
        ("🏛️", t("emg_tip4_t"), t("emg_tip4_d")),
        ("🏠", t("emg_tip5_t"), t("emg_tip5_d")),
    ]
    tip_cols = st.columns(5)
    for col, (icon, title, desc) in zip(tip_cols, tips):
        with col:
            st.markdown(
                f'<div style="background:#f8f9fa;border-radius:12px;padding:1rem 0.7rem;'
                f'text-align:center;border-top:3px solid #1a3a5c;">'
                f'<div style="font-size:1.8rem;">{icon}</div>'
                f'<strong style="color:#1a3a5c;font-size:0.85rem;">{title}</strong>'
                f'<p style="color:#666;font-size:0.78rem;margin-top:4px;">{desc}</p></div>',
                unsafe_allow_html=True,
            )