import streamlit as st
from utils.db import save_feedback
from utils.translations import T


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
        f'<div style="background:linear-gradient(135deg,#0f2942,#1a3a5c);'
        f'border-radius:16px;padding:2.5rem 2rem;margin-bottom:2rem;'
        f'border-left:6px solid #c9a84c;">'
        f'<h1 style="color:#c9a84c;margin:0;font-size:2rem;">{t("about_title")}</h1>'
        f'<p style="color:#a8c0d6;margin:0.5rem 0 0;font-size:0.95rem;">'
        f'{t("about_subtitle")}</p></div>',
        unsafe_allow_html=True,
    )

    # ── Mission ───────────────────────────────────────────────────────────────
    st.subheader(t("about_mission_h"))
    st.markdown(t("about_mission"))
    st.divider()

    # ── Four pillar cards ─────────────────────────────────────────────────────
    pillars = [
        ("#f0f6ff", "#1a3a5c",
         "🌍 " + ("Accessible to All"         if lang == "English" else "سب کے لیے قابل رسائی"),
         ("Voice input (Groq Whisper) and bilingual output in English and Urdu ensure citizens can get help regardless of literacy level."
          if lang == "English" else
          "Groq Whisper سے آواز ان پٹ اور انگریزی اور اردو میں دو لسانی آؤٹ پٹ یقینی بناتے ہیں کہ ہر شہری مدد لے سکے۔")),
        ("#fff8ee", "#c9a84c",
         "🇵🇰 " + ("Grounded in Pakistani Law"  if lang == "English" else "پاکستانی قانون پر مبنی"),
         ("The RAG system retrieves from 43 real Pakistani legal texts including the Constitution, PPC, CrPC, Family Laws, Labour Laws, and Contract Act."
          if lang == "English" else
          "RAG سسٹم 23 اصل پاکستانی قانونی متن سے معلومات لیتا ہے جس میں آئین، PPC، CrPC، خاندانی قوانین، محنت کے قوانین شامل ہیں۔")),
        ("#f0fff4", "#1d6b3a",
         "🔍 " + ("RAG Architecture"            if lang == "English" else "RAG آرکیٹیکچر"),
         ("Retrieval-Augmented Generation: FAISS searches thousands of law chunks for your query, then Groq LLM generates a context-aware legal response — no hallucination."
          if lang == "English" else
          "FAISS آپ کے سوال کے لیے ہزاروں قانونی حصوں میں تلاش کرتا ہے، پھر Groq LLM اس تناظر میں جواب تیار کرتا ہے — کوئی غلط معلومات نہیں۔")),
        ("#fff0f5", "#7b2d5e",
         "🔒 " + ("Privacy & Security"          if lang == "English" else "رازداری اور سیکیورٹی"),
         ("API keys stored in .env, never exposed. Input is sanitised and prompt-injection protected. Queries are anonymised in SQLite."
          if lang == "English" else
          "API کلیدیں .env میں محفوظ ہیں، کبھی ظاہر نہیں۔ ان پٹ صاف اور محفوظ ہے۔ سوالات SQLite میں گمنام ہیں۔")),
    ]
    c1, c2 = st.columns(2, gap="large")
    for i, (bg, bc, title, desc) in enumerate(pillars):
        col = c1 if i % 2 == 0 else c2
        with col:
            st.markdown(
                f'<div style="background:{bg};border-radius:12px;padding:1.4rem;'
                f'border-left:4px solid {bc};margin-bottom:1rem;">'
                f'<h4 style="color:{bc};margin-top:0;">{title}</h4>'
                f'<p style="color:#333;font-size:0.9rem;margin:0;">{desc}</p></div>',
                unsafe_allow_html=True,
            )

    # ── Dataset coverage ──────────────────────────────────────────────────────
    st.divider()
    st.subheader(t("about_dataset_h"))

    if lang == "English":
        dataset_info = [
            ("⚖️", "Constitutional Law",    "Constitution of Pakistan 2025"),
            ("🚔", "Criminal Law",           "Pakistan Penal Code 1860 + CrPC 1898"),
            ("🏛️", "Civil Law / Procedure", "Code of Civil Procedure, Specific Relief, Limitation, Court-Fees, Conciliation"),
            ("📝", "Contract Law",           "The Contract Act 1872"),
            ("🏠", "Property Law",           "Transfer of Property Act 1882"),
            ("👩", "Family Law",             "Muslim Family Laws, Dissolution of Marriage, Guardians & Wards, Child Marriage, Dowry Act"),
            ("💼", "Labour Law",             "Industrial Relations Act, Payment of Wages, Factories Act, EOBI, Workmen's Compensation, Employment of Children, Minimum Wages"),
        ]
    else:
        dataset_info = [
            ("⚖️", "آئینی قانون",        "پاکستان کا آئین 2025"),
            ("🚔", "فوجداری قانون",       "Pakistan Penal Code 1860 + CrPC 1898"),
            ("🏛️", "دیوانی قانون",       "ضابطہ دیوانی، خصوصی ریلیف، حد مدت، عدالتی فیس، مصالحت"),
            ("📝", "معاہدہ قانون",        "معاہدہ ایکٹ 1872"),
            ("🏠", "جائیداد قانون",       "منتقلی جائیداد ایکٹ 1882"),
            ("👩", "خاندانی قانون",       "مسلم فیملی لاز، تحلیل نکاح، سرپرست و وارڈ، بچوں کی شادی، جہیز ایکٹ"),
            ("💼", "محنت کا قانون",       "صنعتی تعلقات ایکٹ، تنخواہ ادائیگی، فیکٹریز ایکٹ، EOBI، کارکن معاوضہ، بچوں کا روزگار، کم از کم اجرت"),
        ]

    for icon, cat, laws in dataset_info:
        st.markdown(
            f'<div style="background:#f8fbff;border-left:4px solid #1a3a5c;'
            f'border-radius:8px;padding:0.7rem 1rem;margin-bottom:0.5rem;">'
            f'<strong style="color:#1a3a5c;">{icon} {cat}</strong>'
            f'<div style="color:#555;font-size:0.85rem;margin-top:2px;">{laws}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Roadmap ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader(t("about_roadmap_h"))

    if lang == "English":
        stages = [
            ("Stage 1 — Foundation",           t("about_complete"), "#1d6b3a",
             "Streamlit UI, SQLite DB, emergency page, NGO directory, bilingual selector (English + Urdu), sidebar navigation."),
            ("Stage 2 — RAG + AI Analysis",    t("about_complete"), "#1d6b3a",
             "FAISS vector index over 23 Pakistani laws, Groq LLM context-aware legal analysis, Groq Whisper voice input, PDF report export, application submission system, NGO & lawyer routing."),
            ("Stage 3 — Admin Portal & Quality", t("about_complete"), "#1d6b3a",
             "Admin dashboard with case management, NGO registry, lawyer registry, assignment overrides, routing analytics, full Urdu UI, context-aware legal intent detection, improved retrieval accuracy."),
            ("Stage 4 — Deployment & Eval",    t("about_upcoming"), "#999",
             "Public deployment, user testing, FYP evaluation and thesis submission."),
        ]
    else:
        stages = [
            ("مرحلہ 1 — بنیاد",                    t("about_complete"), "#1d6b3a",
             "Streamlit UI، SQLite DB، ہنگامی صفحہ، NGO ڈائریکٹری، دو لسانی سلیکٹر (انگریزی + اردو)، سائڈ بار نیویگیشن۔"),
            ("مرحلہ 2 — RAG + AI تجزیہ",           t("about_complete"), "#1d6b3a",
             "23 پاکستانی قوانین پر FAISS ویکٹر انڈیکس، Groq LLM قانونی تجزیہ، Groq Whisper آواز ان پٹ، PDF رپورٹ، درخواست جمع کرانے کا نظام، NGO اور وکیل روٹنگ۔"),
            ("مرحلہ 3 — ایڈمن پورٹل اور معیار",    t("about_complete"), "#1d6b3a",
             "کیس مینجمنٹ ڈیش بورڈ، NGO اور وکیل رجسٹری، اسائنمنٹ اوور رائیڈ، مکمل اردو UI، قانونی مقصد کی شناخت، بہتر بازیافت درستگی۔"),
            ("مرحلہ 4 — تعیناتی اور تشخیص",        t("about_upcoming"), "#999",
             "عوامی تعیناتی، صارف ٹیسٹنگ، FYP تشخیص اور مقالہ جمع۔"),
        ]

    for stage, status, bc, desc in stages:
        bg   = "#f0fff4" if "Complete" in status or "مکمل" in status else "#fafafa"
        icon = "✅" if bg == "#f0fff4" else "🔲"
        st.markdown(
            f'<div style="background:{bg};border-radius:10px;padding:0.9rem 1.2rem;'
            f'border-left:4px solid {bc};margin-bottom:0.6rem;">'
            f'<span style="font-size:1rem;">{icon}</span> '
            f'<strong style="color:#1a3a5c;">{stage}</strong> '
            f'<span style="background:{bc};color:#fff;border-radius:20px;'
            f'padding:1px 10px;font-size:0.72rem;margin-left:6px;">{status}</span>'
            f'<p style="margin:0.3rem 0 0 1.6rem;color:#555;font-size:0.88rem;">{desc}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── At a Glance ───────────────────────────────────────────────────────────
    st.divider()
    st.subheader(t("about_glance_h"))

    try:
        from utils.rag_engine import index_ready, index_stats
        _idx_ok = index_ready()
        _idx_s  = index_stats() if _idx_ok else {}
    except Exception:
        _idx_ok, _idx_s = False, {}

    _at_glance = [
        ("📚", str(_idx_s.get("laws", 23)),                                 t("about_laws_indexed")),
        ("🧩", f'{_idx_s.get("vectors", 7659):,}' if _idx_ok else "7,659", t("about_chunks")),
        ("🌐", "2",                                                          t("about_languages")),
        ("🤖", "Groq LLM",                                                   t("about_ai_engine")),
        ("🔍", "FAISS RAG",                                                  t("about_retrieval")),
    ]
    cols = st.columns(5)
    for col, (icon, val, label) in zip(cols, _at_glance):
        with col:
            st.markdown(
                f'<div style="text-align:center;background:#ffffff;border-radius:12px;'
                f'padding:1rem 0.6rem;border:1px solid #dce8f5;border-top:3px solid #1a3a5c;'
                f'box-shadow:0 3px 14px rgba(15,41,66,0.07);margin-bottom:0.8rem;">'
                f'<div style="font-size:1.6rem;margin-bottom:0.25rem;">{icon}</div>'
                f'<div style="color:#1a3a5c;font-weight:700;font-size:1.2rem;line-height:1.2;">{val}</div>'
                f'<div style="color:#5a7a8a;font-size:0.74rem;font-weight:600;'
                f'letter-spacing:0.3px;text-transform:uppercase;margin-top:0.2rem;">{label}</div></div>',
                unsafe_allow_html=True,
            )

    # ── Tech Stack ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader(t("about_tech_h"))

    techs = [
        ("🐍", "Python 3.12",          t("about_core_lang")),
        ("🖥️", "Streamlit",           t("about_frontend")),
        ("🤖", "Groq LLM",             "llama-3.3-70b"),
        ("🎤", "Groq Whisper",         t("about_voice")),
        ("🔍", "FAISS",                t("about_vector")),
        ("🧠", "Sentence-Transformers", t("about_embeddings")),
        ("📄", "PyPDF",                t("about_pdf")),
        ("🗄️", "SQLite",              t("about_db")),
    ]
    cols = st.columns(4)
    for i, (icon, name, role) in enumerate(techs):
        with cols[i % 4]:
            st.markdown(
                f'<div style="text-align:center;background:#f4f7fb;border-radius:10px;'
                f'padding:0.9rem 0.5rem;border-top:3px solid #1a3a5c;margin-bottom:0.8rem;">'
                f'<div style="font-size:1.6rem;">{icon}</div>'
                f'<strong style="color:#1a3a5c;font-size:0.82rem;">{name}</strong>'
                f'<div style="color:#7a96ad;font-size:0.72rem;">{role}</div></div>',
                unsafe_allow_html=True,
            )

    st.info(t("about_fyp_note"))

    # ── Rate This Tool ────────────────────────────────────────────────────────
    st.divider()
    with st.expander(t("feedback_label"), expanded=False):
        rating  = st.slider(t("feedback_slider"), 1, 5, 4, format="%d ⭐")
        comment = st.text_input(t("feedback_comment"))
        if st.button(t("feedback_submit"), key="about_fb_btn"):
            save_feedback(rating=rating, comment=comment)
            st.success(t("feedback_thanks"))