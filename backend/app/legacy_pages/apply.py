"""
pages/apply.py — Legal Aid Application Page (dedicated tab).

Pre-fills from the latest AI analysis result when available:
  - Case description ← result.summary
  - Case type        ← result.category  
  - Urgency          ← result.risk_level
  - City             ← sidebar city selection

Clears the pre-fill whenever the analysis changes or is cleared,
so the form always reflects the current case.
"""
import streamlit as st
from app.utils.translations import T
from app.utils.config import PAKISTAN_CITIES
from app.utils.application_service import submit_application
from app.utils.legal_taxonomy import (
    LEGAL_CASE_TYPES as CASE_TYPES,
    URGENCY_LEVELS,
)


def show() -> None:
    lang = st.session_state.get("language", "English")
    t    = T(lang)

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
        f'<div style="background:linear-gradient(135deg,#0f2942,#1a3a5c);'
        f'border-radius:16px;padding:2rem 2rem 1.5rem;margin-bottom:1.5rem;'
        f'border-left:6px solid #c9a84c;">'
        f'<h2 style="color:#c9a84c;margin:0;">📋 {t("application_label")}</h2>'
        f'<p style="color:#a8c0d6;margin:0.4rem 0 0;font-size:0.92rem;">'
        f'{t("application_subtitle")}</p></div>',
        unsafe_allow_html=True,
    )

    # ── Pull latest analysis result from session state ────────────────────────
    result = st.session_state.get("analysis_result")
    has_result = result is not None and not getattr(result, "error", True)

    # Use the last query as a stable fingerprint — it only changes when the
    # user runs a new analysis or clears the page. id(result) is unreliable
    # across reruns because Streamlit may recreate objects.
    current_result_key = st.session_state.get("last_query", "") if has_result else ""
    last_filled_key    = st.session_state.get("_apply_last_result_key", "")

    if current_result_key != last_filled_key:
        # Analysis changed — mark that we should re-derive description
        st.session_state["_apply_last_result_key"] = current_result_key

    # ── Derive pre-fill values from result ────────────────────────────────────
    if has_result:
        prefill_desc     = result.summary or ""
        prefill_category = result.category  if result.category  in CASE_TYPES    else CASE_TYPES[0]
        prefill_urgency  = result.risk_level.capitalize() \
                           if result.risk_level.capitalize() in URGENCY_LEVELS   else "Medium"
    else:
        prefill_desc     = ""
        prefill_category = CASE_TYPES[0]
        prefill_urgency  = "Medium"

    # After a successful submission the form clears via clear_on_submit=True.
    # We also blank the description so it doesn't re-appear on next render.
    if st.session_state.get("_apply_submitted_ok"):
        prefill_desc = ""
        prefill_category = CASE_TYPES[0]
        prefill_urgency  = "Medium"
        st.session_state["_apply_submitted_ok"] = False
        # Reset result key so next analysis will re-fill
        st.session_state["_apply_last_result_key"] = ""

    # ── Callout when no analysis yet ─────────────────────────────────────────
    if not has_result:
        st.info(
            "💡 Run an AI analysis on the **Home** tab first to auto-fill your case details here."
            if lang == "English" else
            "💡 پہلے **مرکزی صفحہ** پر AI تجزیہ کریں تاکہ آپ کے کیس کی تفصیل یہاں خودکار بھر جائے۔"
        )

    # ── Label maps ────────────────────────────────────────────────────────────
    _city_opts = [c for c in PAKISTAN_CITIES if c != "Any City"]
    _city_labels = {
        "Karachi":    t("city_karachi"),   "Lahore":     t("city_lahore"),
        "Islamabad":  t("city_islamabad"), "Rawalpindi": t("city_rawalpindi"),
        "Peshawar":   t("city_peshawar"),  "Quetta":     t("city_quetta"),
        "Multan":     t("city_multan"),    "Faisalabad": t("city_faisalabad"),
    }
    _case_labels = {
        "Property / Tenant":  t("case_property"),
        "Family Law":         t("case_family"),
        "Employment":         t("case_employment"),
        "Criminal":           t("case_criminal"),
        "Harassment / Abuse": t("case_harassment"),
        "Other":              t("case_other"),
    }
    _urg_labels = {
        "Low":      t("urgency_low"),
        "Medium":   t("urgency_medium"),
        "High":     t("urgency_high"),
        "Critical": t("urgency_critical"),
    }

    # City: prefer sidebar city over default
    _sidebar_city = st.session_state.get("city_select", "")
    _city_default = _sidebar_city if _sidebar_city in _city_opts else _city_opts[0]

    # ── Form ─────────────────────────────────────────────────────────────────
    with st.form("apply_page_form", clear_on_submit=True):
        fa1, fa2 = st.columns(2)

        with fa1:
            app_name    = st.text_input(t("app_full_name"),
                                        placeholder=t("app_name_placeholder"))
            app_contact = st.text_input(t("app_contact"),
                                        placeholder=t("app_contact_placeholder"))
            app_city    = st.selectbox(
                t("app_city_field"), _city_opts,
                index=_city_opts.index(_city_default),
                format_func=lambda x: _city_labels.get(x, x),
            )

        with fa2:
            app_email   = st.text_input(t("app_email"),
                                        placeholder=t("app_email_placeholder"))
            app_case    = st.selectbox(
                t("app_case_type"), CASE_TYPES,
                index=CASE_TYPES.index(prefill_category),
                format_func=lambda x: _case_labels.get(x, x),
            )
            app_urgency = st.selectbox(
                t("app_urgency"), URGENCY_LEVELS,
                index=URGENCY_LEVELS.index(prefill_urgency),
                format_func=lambda x: _urg_labels.get(x, x),
            )

        # Case description — pre-filled from AI analysis summary.
        # The key includes the result fingerprint so Streamlit treats it as
        # a new widget when the analysis changes, forcing value= to apply.
        _desc_key = f"apply_desc_{current_result_key[:16] if current_result_key else 'empty'}"
        app_desc = st.text_area(
            t("app_description"),
            value=prefill_desc,
            height=150,
            key=_desc_key,
            placeholder=(
                "Describe your legal issue in detail..."
                if lang == "English" else
                "اپنے قانونی مسئلے کی تفصیل یہاں لکھیں..."
            ),
            help=t("app_description_help"),
        )

        if has_result:
            st.caption(
                "✨ Case details pre-filled from your AI analysis. Edit as needed."
                if lang == "English" else
                "✨ کیس کی تفصیل آپ کے AI تجزیے سے خودکار بھری گئی ہے۔ ضرورت کے مطابق ترمیم کریں۔"
            )

        submitted = st.form_submit_button(
            t("app_submit_btn"), type="primary", use_container_width=True,
        )

    # ── Validation + submission ───────────────────────────────────────────────
    if submitted:
        _errors = []
        if not app_name.strip():
            _errors.append(t("field_required", field=t("app_full_name")))
        if not app_contact.strip():
            _errors.append(t("field_required", field=t("app_contact")))
        if not app_desc.strip():
            _errors.append(t("field_required", field=t("app_description")))

        if _errors:
            st.warning(t("form_fix_warning") + "\n\n" +
                       "\n".join(f"- {e}" for e in _errors))
        else:
            try:
                saved = submit_application({
                    "name":        app_name.strip(),
                    "contact":     app_contact.strip(),
                    "email":       app_email.strip(),
                    "city":        app_city,
                    "case_type":   app_case,
                    "urgency":     app_urgency,
                    "description": app_desc.strip(),
                })
                # Signal that the description should clear on next render
                st.session_state["_apply_submitted_ok"] = True

                st.success(t("app_success"))
                st.markdown(
                    f'<div style="background:#f0fff4;border:1px solid #86efac;'
                    f'border-radius:10px;padding:0.9rem 1.1rem;margin-top:0.4rem;">'
                    f'<div style="font-size:0.88rem;line-height:1.9;">'
                    f'<strong>{t("app_id_label")}:</strong> '
                    f'<code style="background:#d1fae5;padding:2px 7px;border-radius:4px;">'
                    f'{saved["application_id"]}</code><br>'
                    f'<strong>{t("app_case_type")}:</strong> {saved["case_type"]}<br>'
                    f'<strong>{t("app_urgency")}:</strong> {saved["urgency"]}<br>'
                    f'<strong>{t("app_city_field")}:</strong> {saved["city"]}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                st.info(t("app_track_note"))
            except ValueError as ve:
                st.error(f"⚠️ {ve}")

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:#fffbeb;border:1px solid #fcd34d;'
        f'border-left:4px solid #f59e0b;border-radius:8px;'
        f'padding:0.8rem 1rem;font-size:0.85rem;color:#78350f;">'
        f'⚠️ {"This tool provides legal information only and does not replace a licensed lawyer. Your application will be reviewed by a specialist NGO." if lang == "English" else "یہ ٹول صرف قانونی معلومات فراہم کرتا ہے اور کسی لائسنس یافتہ وکیل کا متبادل نہیں ہے۔ آپ کی درخواست ایک ماہر این جی او کی جانب سے جائزہ لی جائے گی۔"}'
        f'</div>',
        unsafe_allow_html=True,
    )