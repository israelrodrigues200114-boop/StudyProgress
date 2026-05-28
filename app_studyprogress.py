import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(
    page_title="StudyProgress",
    layout="wide",
    initial_sidebar_state="collapsed"
)


SPREADSHEET_NAME = "FutureEng_V4"
WORKSHEET_NAME = "Registros"

subjects = [
    "Matemática", "Física", "Química", "Português",
    "História", "Filosofia", "Sociologia",
    "Literatura", "Redação"
]

columns = [
    "Data", "Matéria", "Conteúdo", "Tempo (h)",
    "Exercícios", "Acertos", "Pendência", "Observações"
]

subject_themes = {
    "Home": {"main": "#2F80ED", "soft": "#EAF3FF", "medium": "#D6E9FF"},
    "Adicionar": {"main": "#2563EB", "soft": "#EFF6FF", "medium": "#DBEAFE"},
    "Matemática": {"main": "#2F80ED", "soft": "#EAF3FF", "medium": "#D6E9FF"},
    "Física": {"main": "#8B5CF6", "soft": "#F1ECFF", "medium": "#E1D6FF"},
    "Química": {"main": "#10B981", "soft": "#E9FBF4", "medium": "#D4F8E8"},
    "Português": {"main": "#EF5DA8", "soft": "#FFF0F7", "medium": "#FFD9EA"},
    "História": {"main": "#F59E0B", "soft": "#FFF7E8", "medium": "#FFE6B8"},
    "Filosofia": {"main": "#14B8A6", "soft": "#E9FBF8", "medium": "#CFF7F1"},
    "Sociologia": {"main": "#F97316", "soft": "#FFF1E8", "medium": "#FFDCC7"},
    "Literatura": {"main": "#7C6EE6", "soft": "#F0EEFF", "medium": "#DDD8FF"},
    "Redação": {"main": "#EC4899", "soft": "#FFF0F8", "medium": "#FFD8EC"},
}

icons = {
    "Home": "🏠",
    "Adicionar": "➕",
    "Matemática": "√x",
    "Física": "⚛",
    "Química": "⚗",
    "Português": "📖",
    "História": "🏛",
    "Filosofia": "💡",
    "Sociologia": "👥",
    "Literatura": "📚",
    "Redação": "✎",
}


@st.cache_resource
def connect_to_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)


@st.cache_data(ttl=10)
def load_data():
    worksheet = connect_to_sheet()
    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Tempo (h)"] = pd.to_numeric(df["Tempo (h)"], errors="coerce").fillna(0)
    df["Exercícios"] = pd.to_numeric(df["Exercícios"], errors="coerce").fillna(0)
    df["Acertos"] = pd.to_numeric(df["Acertos"], errors="coerce").fillna(0)
    df["Pendência"] = df["Pendência"].astype(str).str.strip()

    return df


def save_record(data, subject, content, time_hours, exercises, hits, pending, observations):
    worksheet = connect_to_sheet()

    worksheet.append_row(
        [
            data.strftime("%d/%m/%Y"),
            subject,
            content,
            float(time_hours),
            int(exercises),
            int(hits),
            pending,
            observations
        ],
        value_input_option="USER_ENTERED"
    )

    load_data.clear()


def clean_number(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def show_metric_card(title, value, desc):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def read_subject(df, subject):
    if df.empty or "Matéria" not in df.columns:
        return pd.DataFrame(columns=columns)

    return df[df["Matéria"].astype(str).str.strip() == subject].copy()


def get_totals(df):
    total_hours = clean_number(df["Tempo (h)"]).sum() if "Tempo (h)" in df.columns else 0
    total_exercises = clean_number(df["Exercícios"]).sum() if "Exercícios" in df.columns else 0

    if "Pendência" in df.columns:
        total_pending = (
            df["Pendência"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("sim")
            .sum()
        )
    else:
        total_pending = 0

    return total_hours, total_exercises, total_pending


def get_reviews(df):
    if df.empty or "Data" not in df.columns or "Conteúdo" not in df.columns:
        return pd.DataFrame(columns=["Matéria", "Conteúdo", "Dias sem revisar"])

    today = pd.Timestamp(datetime.today().date())

    review_df = df.dropna(subset=["Data"]).copy()
    review_df["Dias sem revisar"] = (today - review_df["Data"]).dt.days
    review_df = review_df[review_df["Dias sem revisar"] >= 40]

    return review_df[["Matéria", "Conteúdo", "Dias sem revisar"]].sort_values(
        "Dias sem revisar",
        ascending=False
    )


def get_pending(df):
    if df.empty or "Pendência" not in df.columns:
        return pd.DataFrame(columns=columns)

    pending_df = df[
        df["Pendência"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("sim")
    ].copy()

    return pending_df


try:
    all_data = load_data()
except Exception as e:
    st.error("Não consegui conectar na Google Planilhas. Confira o secrets.toml, o nome da planilha e a aba Registros.")
    st.exception(e)
    st.stop()


nav_items = ["Home", "Adicionar"] + subjects

page = st.radio(
    "Menu",
    nav_items,
    horizontal=True,
    label_visibility="collapsed",
    format_func=lambda x: f"{icons[x]} {'Início' if x == 'Home' else x}"
)

theme = subject_themes[page]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* {{
    font-family: 'Inter', sans-serif;
}}

.stApp {{
    background: linear-gradient(180deg, #FFFFFF 0%, {theme['soft']} 100%);
    color: #14345F;
}}

.block-container {{
    padding-top: 1.6rem;
    padding-left: 3rem;
    padding-right: 3rem;
}}

header[data-testid="stHeader"] {{
    background: transparent;
}}

#MainMenu, footer {{
    visibility: hidden;
}}

/* MENU SUPERIOR */
div[data-testid="stRadio"] {{
    background: rgba(255,255,255,0.92);
    padding: 10px 14px;
    border-radius: 18px;
    border: 1px solid #DDE8F7;
    box-shadow: 0 8px 24px rgba(47,128,237,0.08);
    margin-bottom: 28px;
}}

div[role="radiogroup"] {{
    display: flex;
    gap: 10px;
    overflow-x: auto;
    flex-wrap: wrap;
}}

div[data-testid="stRadio"] label {{
    background: transparent;
    border-radius: 14px;
    padding: 9px 14px !important;
    transition: all .2s ease;
    white-space: nowrap;
}}

div[data-testid="stRadio"] label:hover {{
    background: {theme['soft']};
}}

div[data-testid="stRadio"] label p {{
    color: #36618F !important;
    font-weight: 800 !important;
    font-size: 15px !important;
}}

div[data-testid="stRadio"] input:checked + div p {{
    color: {theme['main']} !important;
}}

/* REMOVE AS BOLINHAS DO MENU */
div[data-testid="stRadio"] label > div:first-child {{
    display: none !important;
}}

div[data-testid="stRadio"] [role="radio"] {{
    display: none !important;
}}

h1 {{
    color: {theme['main']} !important;
    font-size: 38px !important;
    font-weight: 800 !important;
    margin-bottom: 4px !important;
}}

h2, h3 {{
    color: #0B356A !important;
    font-weight: 800 !important;
}}

p, span, label, div {{
    color: #14345F;
}}

.subtitle {{
    color: #54739A;
    font-size: 16px;
    margin-bottom: 24px;
}}

.logo-title {{
    color: {theme['main']};
    font-size: 26px;
    font-weight: 800;
    margin-bottom: 8px;
}}

.metric-card {{
    background: linear-gradient(135deg, {theme['soft']}, #FFFFFF);
    border: 1px solid {theme['medium']};
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 12px 30px rgba(47,128,237,0.08);
    min-height: 128px;
}}

.metric-title {{
    color: {theme['main']};
    font-weight: 800;
    font-size: 16px;
    margin-bottom: 10px;
}}

.metric-value {{
    color: {theme['main']};
    font-size: 34px;
    font-weight: 800;
    line-height: 1;
}}

.metric-desc {{
    color: #5A7498;
    font-size: 14px;
    margin-top: 12px;
}}

.stDataFrame {{
    background: white;
    border: 1px solid {theme['medium']};
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 12px 30px rgba(47,128,237,0.07);
}}

[data-testid="stLineChart"] {{
    background: white;
    border: 1px solid {theme['medium']};
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 12px 30px rgba(47,128,237,0.07);
}}

hr {{
    border-color: #DDE8F7;
}}

div[data-testid="stAlert"] {{
    border-radius: 16px;
}}

button {{
    border-radius: 14px !important;
}}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='logo-title'>StudyProgress</div>", unsafe_allow_html=True)


if page == "Home":
    total_hours, total_exercises, total_pending = get_totals(all_data)
    review_df = get_reviews(all_data)
    pend_df = get_pending(all_data)

    st.markdown("<h1>Painel de Estudos</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>Olá! 👋<br>Acompanhe seu progresso e organize seus estudos.</div>",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        show_metric_card("Dados", "100%", "Sistema conectado")
    with c2:
        show_metric_card("Pendências", int(total_pending), "Itens para revisar")
    with c3:
        show_metric_card("Revisão", len(review_df), "Itens com 40+ dias")
    with c4:
        show_metric_card("Horas Estudadas", f"{round(total_hours, 1)}h", "Total registrado")
    with c5:
        show_metric_card("Questões", int(total_exercises), "Respondidas")

    st.write("")

    left, right = st.columns(2)

    with left:
        st.markdown("### Pendências atuais")
        if not pend_df.empty:
            st.dataframe(pend_df, use_container_width=True, height=300)
        else:
            st.success("Nenhuma pendência encontrada.")

    with right:
        st.markdown("### Revisões de 40 dias")
        if not review_df.empty:
            st.dataframe(review_df, use_container_width=True, height=300)
        else:
            st.success("Nenhuma revisão pendente.")

    st.write("")

    left2, right2 = st.columns(2)

    with left2:
        st.markdown("### Evolução de estudos")
        if not all_data.empty and "Data" in all_data.columns and "Tempo (h)" in all_data.columns:
            evo_df = all_data.dropna(subset=["Data"]).copy()
            evo_df = evo_df.groupby("Data", as_index=False)["Tempo (h)"].sum()

            if not evo_df.empty:
                st.line_chart(evo_df, x="Data", y="Tempo (h)", height=300)
            else:
                st.info("Sem dados suficientes para gráfico.")
        else:
            st.info("Sem dados suficientes para gráfico.")

    with right2:
        st.markdown("### Questões por matéria")
        if not all_data.empty:
            rows = (
                all_data
                .groupby("Matéria", as_index=False)["Exercícios"]
                .sum()
                .rename(columns={"Exercícios": "Respondidas"})
            )
            rows["Respondidas"] = rows["Respondidas"].astype(int)
            st.dataframe(rows, use_container_width=True, height=300)
        else:
            st.info("Sem registros de questões.")

    st.markdown("### Todos os registros")
    st.dataframe(all_data, use_container_width=True, height=350)


elif page == "Adicionar":
    st.markdown("<h1>➕ Adicionar estudo</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>Cadastre seus estudos direto pelo site. Os dados serão salvos na Google Planilhas.</div>",
        unsafe_allow_html=True
    )

    with st.form("form_adicionar_estudo", clear_on_submit=True):
        c1, c2 = st.columns(2)

        with c1:
            data = st.date_input("Data", value=datetime.today())
            subject = st.selectbox("Matéria", subjects)
            content = st.text_input("Conteúdo estudado")

        with c2:
            time_hours = st.number_input("Tempo (h)", min_value=0.0, step=0.5)
            exercises = st.number_input("Exercícios", min_value=0, step=1)
            hits = st.number_input("Acertos", min_value=0, step=1)

        pending = st.selectbox("Pendência", ["Não", "Sim"])
        observations = st.text_area("Observações")

        submitted = st.form_submit_button("Salvar estudo")

        if submitted:
            if not content.strip():
                st.warning("Preencha o conteúdo estudado antes de salvar.")
            else:
                save_record(data, subject, content, time_hours, exercises, hits, pending, observations)
                st.success("Estudo salvo com sucesso na Google Planilhas!")
                st.rerun()


else:
    df = read_subject(all_data, page)

    st.markdown(f"<h1>{icons[page]} {page}</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='subtitle'>Tema de {page} aplicado em toda a interface.</div>",
        unsafe_allow_html=True
    )

    if df.empty:
        st.warning(f"Não encontrei registros de {page} na Google Planilhas.")
    else:
        total_hours_subject = clean_number(df["Tempo (h)"]).sum()
        total_ex_subject = clean_number(df["Exercícios"]).sum()
        total_pending_subject = (
            df["Pendência"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("sim")
            .sum()
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            show_metric_card("Horas na matéria", round(total_hours_subject, 1), "Tempo registrado")
        with c2:
            show_metric_card("Exercícios resolvidos", int(total_ex_subject), "Questões feitas")
        with c3:
            show_metric_card("Pendências", int(total_pending_subject), "Itens marcados")

        st.write("")
        st.markdown("### Evolução")

        chart_df = df.dropna(subset=["Data"]).copy()

        if not chart_df.empty:
            chart_df = chart_df.groupby("Data", as_index=False)["Tempo (h)"].sum()
            st.line_chart(chart_df, x="Data", y="Tempo (h)", height=340)
        else:
            st.info("Sem datas válidas para gerar evolução.")

        st.markdown("### Registros")
        st.dataframe(df, use_container_width=True, height=450)
