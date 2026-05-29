import uuid
from datetime import date

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="StudyProgress", layout="wide", initial_sidebar_state="collapsed")

SPREADSHEET_NAME = "FutureEng_V4"
WORKSHEET_NAME = "Registros"
REVIEW_INTERVAL_DAYS = 40

subjects = [
    "Matemática", "Física", "Química", "Biologia", "Português", "História",
    "Geografia", "Filosofia", "Sociologia", "Literatura", "Redação",
]

columns = [
    "Data", "Matéria", "Conteúdo", "Tempo (h)", "Exercícios", "Acertos",
    "Pendência", "Observações", "ID", "Última revisão", "Revisão feita", "Pendência feita",
]

subject_themes = {
    "Home": {"main": "#2F80ED", "soft": "#EAF3FF", "medium": "#D6E9FF"},
    "Adicionar": {"main": "#2563EB", "soft": "#EFF6FF", "medium": "#DBEAFE"},
    "Matemática": {"main": "#2F80ED", "soft": "#EAF3FF", "medium": "#D6E9FF"},
    "Física": {"main": "#8B5CF6", "soft": "#F1ECFF", "medium": "#E1D6FF"},
    "Química": {"main": "#10B981", "soft": "#E9FBF4", "medium": "#D4F8E8"},
    "Biologia": {"main": "#22C55E", "soft": "#F0FDF4", "medium": "#DCFCE7"},
    "Português": {"main": "#EF5DA8", "soft": "#FFF0F7", "medium": "#FFD9EA"},
    "História": {"main": "#F59E0B", "soft": "#FFF7E8", "medium": "#FFE6B8"},
    "Geografia": {"main": "#0EA5E9", "soft": "#F0F9FF", "medium": "#E0F2FE"},
    "Filosofia": {"main": "#14B8A6", "soft": "#E9FBF8", "medium": "#CFF7F1"},
    "Sociologia": {"main": "#F97316", "soft": "#FFF1E8", "medium": "#FFDCC7"},
    "Literatura": {"main": "#7C6EE6", "soft": "#F0EEFF", "medium": "#DDD8FF"},
    "Redação": {"main": "#EC4899", "soft": "#FFF0F8", "medium": "#FFD8EC"},
}

icons = {
    "Home": "🏠", "Adicionar": "➕", "Matemática": "√x", "Física": "⚛",
    "Química": "⚗", "Biologia": "🧬", "Português": "📖", "História": "🏛",
    "Geografia": "🌎", "Filosofia": "💡", "Sociologia": "👥",
    "Literatura": "📚", "Redação": "✎",
}


@st.cache_resource
def connect_to_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)


def clear_data_cache():
    load_data.clear()


def new_id():
    return uuid.uuid4().hex[:10].upper()


def format_date_br(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")


def check_sheet_structure(worksheet):
    headers = worksheet.row_values(1)
    if headers[:len(columns)] != columns:
        raise ValueError("A aba Registros deve ter as colunas nesta ordem: " + " | ".join(columns))


@st.cache_data(ttl=10)
def load_data():
    worksheet = connect_to_sheet()
    check_sheet_structure(worksheet)
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=columns + ["_sheet_row"])

    id_col = columns.index("ID") + 1
    changed = False
    active_records = []

    for sheet_row, record in enumerate(records, start=2):
        # Ignora linhas vazias da planilha, mesmo que tenham recebido um ID anteriormente.
        is_empty = not any(
            str(record.get(col, "")).strip()
            for col in ["Data", "Matéria", "Conteúdo"]
        )
        if is_empty:
            continue

        if not str(record.get("ID", "")).strip():
            record_id = new_id()
            worksheet.update_cell(sheet_row, id_col, record_id)
            record["ID"] = record_id
            changed = True

        record["_sheet_row"] = sheet_row
        active_records.append(record)

    if not active_records:
        return pd.DataFrame(columns=columns + ["_sheet_row"])

    if changed:
        records = worksheet.get_all_records()
        active_records = []
        for sheet_row, record in enumerate(records, start=2):
            is_empty = not any(
                str(record.get(col, "")).strip()
                for col in ["Data", "Matéria", "Conteúdo"]
            )
            if not is_empty:
                record["_sheet_row"] = sheet_row
                active_records.append(record)

    df = pd.DataFrame(active_records)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns + ["_sheet_row"]]
    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df["Última revisão"] = pd.to_datetime(df["Última revisão"], dayfirst=True, errors="coerce")
    df["Tempo (h)"] = pd.to_numeric(df["Tempo (h)"], errors="coerce").fillna(0)
    df["Exercícios"] = pd.to_numeric(df["Exercícios"], errors="coerce").fillna(0).astype(int)
    df["Acertos"] = pd.to_numeric(df["Acertos"], errors="coerce").fillna(0).astype(int)
    text_cols = ["Matéria", "Conteúdo", "Pendência", "Observações", "ID", "Revisão feita", "Pendência feita"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def build_row_values(study_date, subject, content, time_hours, exercises, hits, pending, observations,
                     record_id, last_review="", review_done="", pending_done=""):
    return [
        format_date_br(study_date), subject, content.strip(), float(time_hours), int(exercises), int(hits),
        pending, observations.strip(), record_id,
        format_date_br(last_review) if str(last_review).strip() not in ("", "NaT") else "",
        review_done, pending_done,
    ]


def save_record(study_date, subject, content, time_hours, exercises, hits, pending, observations):
    worksheet = connect_to_sheet()
    worksheet.append_row(
        build_row_values(study_date, subject, content, time_hours, exercises, hits, pending, observations, new_id()),
        value_input_option="USER_ENTERED",
    )
    clear_data_cache()


def update_record(sheet_row, values):
    worksheet = connect_to_sheet()
    worksheet.update(range_name=f"A{int(sheet_row)}:L{int(sheet_row)}", values=[values], value_input_option="USER_ENTERED")
    clear_data_cache()


def delete_record(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.delete_rows(int(sheet_row))
    clear_data_cache()


def mark_pending_done(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.update_cell(int(sheet_row), columns.index("Pendência feita") + 1, "Sim")
    clear_data_cache()


def mark_review_done(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.update(
        range_name=f"J{int(sheet_row)}:K{int(sheet_row)}",
        values=[[date.today().strftime("%d/%m/%Y"), "Sim"]],
        value_input_option="USER_ENTERED",
    )
    clear_data_cache()


def show_metric_card(title, value, desc):
    st.markdown(
        f'''<div class="metric-card"><div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div><div class="metric-desc">{desc}</div></div>''',
        unsafe_allow_html=True,
    )


def read_subject(df, subject):
    return df[df["Matéria"] == subject].copy() if not df.empty else pd.DataFrame(columns=columns + ["_sheet_row"])


def open_pending_mask(df):
    return df["Pendência"].str.lower().eq("sim") & ~df["Pendência feita"].str.lower().eq("sim")


def get_totals(df):
    if df.empty:
        return 0, 0, 0
    return df["Tempo (h)"].sum(), df["Exercícios"].sum(), int(open_pending_mask(df).sum())


def get_pending(df):
    return df[open_pending_mask(df)].copy() if not df.empty else pd.DataFrame(columns=columns + ["_sheet_row"])


def get_reviews(df):
    if df.empty:
        return pd.DataFrame(columns=columns + ["_sheet_row", "Dias sem revisar"])
    review_df = df.dropna(subset=["Data"]).copy()
    review_df["Data base da revisão"] = review_df["Última revisão"].fillna(review_df["Data"])
    review_df["Dias sem revisar"] = (pd.Timestamp(date.today()) - review_df["Data base da revisão"]).dt.days
    return review_df[review_df["Dias sem revisar"] >= REVIEW_INTERVAL_DAYS].sort_values("Dias sem revisar", ascending=False)


def display_table(df):
    if df.empty:
        return df.copy()
    shown = df.copy()
    for date_col in ["Data", "Última revisão"]:
        shown[date_col] = shown[date_col].apply(format_date_br)
    return shown.drop(columns=["_sheet_row", "ID", "Revisão feita", "Pendência feita"], errors="ignore")


try:
    all_data = load_data()
except Exception as error:
    st.error("Não consegui carregar os dados. Confira se a aba Registros possui todas as 12 colunas na ordem correta.")
    st.exception(error)
    st.stop()

nav_items = ["Home", "Adicionar"] + subjects
page = st.radio("Menu", nav_items, horizontal=True, label_visibility="collapsed",
                format_func=lambda item: f"{icons[item]} {'Início' if item == 'Home' else item}")
theme = subject_themes[page]

st.markdown(f'''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: linear-gradient(180deg, #FFFFFF 0%, {theme['soft']} 100%); color: #14345F; }}
.block-container {{ padding-top: 1.6rem; padding-left: 3rem; padding-right: 3rem; }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
div[data-testid="stRadio"] {{ background: rgba(255,255,255,0.92); padding: 10px 14px; border-radius: 18px; border: 1px solid #DDE8F7; box-shadow: 0 8px 24px rgba(47,128,237,0.08); margin-bottom: 28px; }}
div[role="radiogroup"] {{ display: flex; gap: 10px; overflow-x: auto; flex-wrap: wrap; }}
div[data-testid="stRadio"] label {{ background: transparent; border-radius: 14px; padding: 9px 14px !important; transition: all .2s ease; white-space: nowrap; }}
div[data-testid="stRadio"] label:hover {{ background: {theme['soft']}; }}
div[data-testid="stRadio"] label p {{ color: #36618F !important; font-weight: 800 !important; font-size: 15px !important; }}
div[data-testid="stRadio"] input:checked + div p {{ color: {theme['main']} !important; }}
div[data-testid="stRadio"] label > div:first-child, div[data-testid="stRadio"] [role="radio"] {{ display: none !important; }}
h1 {{ color: {theme['main']} !important; font-size: 38px !important; font-weight: 800 !important; margin-bottom: 4px !important; }}
h2, h3 {{ color: #0B356A !important; font-weight: 800 !important; }}
p, span, label, div {{ color: #14345F; }}
.subtitle {{ color: #54739A; font-size: 16px; margin-bottom: 24px; }}
.logo-title {{ color: {theme['main']}; font-size: 26px; font-weight: 800; margin-bottom: 8px; }}
.metric-card {{ background: linear-gradient(135deg, {theme['soft']}, #FFFFFF); border: 1px solid {theme['medium']}; border-radius: 18px; padding: 24px; box-shadow: 0 12px 30px rgba(47,128,237,0.08); min-height: 128px; }}
.metric-title {{ color: {theme['main']}; font-weight: 800; font-size: 16px; margin-bottom: 10px; }}
.metric-value {{ color: {theme['main']}; font-size: 34px; font-weight: 800; line-height: 1; }}
.metric-desc {{ color: #5A7498; font-size: 14px; margin-top: 12px; }}
.stDataFrame, [data-testid="stLineChart"] {{ background: white; border: 1px solid {theme['medium']}; border-radius: 18px; overflow: hidden; box-shadow: 0 12px 30px rgba(47,128,237,0.07); }}
[data-testid="stLineChart"] {{ padding: 18px; }}
div[data-testid="stAlert"] {{ border-radius: 16px; }}
button {{ border-radius: 14px !important; }}
</style>
''', unsafe_allow_html=True)

st.markdown("<div class='logo-title'>StudyProgress</div>", unsafe_allow_html=True)

if page == "Home":
    total_hours, total_exercises, total_pending = get_totals(all_data)
    review_df, pending_df = get_reviews(all_data), get_pending(all_data)
    st.markdown("<h1>Painel de Estudos</h1>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Olá! 👋<br>Acompanhe seu progresso e organize seus estudos.</div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: show_metric_card("Dados", "100%", "Sistema conectado")
    with c2: show_metric_card("Pendências", int(total_pending), "Em aberto")
    with c3: show_metric_card("Revisão", len(review_df), "Itens com 40+ dias")
    with c4: show_metric_card("Horas Estudadas", f"{round(total_hours, 1)}h", "Total registrado")
    with c5: show_metric_card("Questões", int(total_exercises), "Respondidas")
    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("### Pendências atuais")
        if pending_df.empty:
            st.success("Nenhuma pendência encontrada.")
        for _, row in pending_df.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Matéria']} — {row['Conteúdo']}**")
                st.caption(f"Data: {format_date_br(row['Data'])}")
                if row["Observações"]: st.write(row["Observações"])
                if st.button("✓ Marcar pendência como feita", key=f"pending_{row['ID']}"):
                    mark_pending_done(row["_sheet_row"]); st.rerun()
    with right:
        st.markdown(f"### Revisões de {REVIEW_INTERVAL_DAYS} dias")
        if review_df.empty:
            st.success("Nenhuma revisão pendente.")
        for _, row in review_df.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Matéria']} — {row['Conteúdo']}**")
                st.caption(f"{int(row['Dias sem revisar'])} dias sem revisar")
                if st.button("✓ Revisei hoje", key=f"review_{row['ID']}"):
                    mark_review_done(row["_sheet_row"]); st.rerun()
    st.write("")
    left2, right2 = st.columns(2)
    with left2:
        st.markdown("### Evolução de estudos")
        evo_df = all_data.dropna(subset=["Data"]).groupby("Data", as_index=False)["Tempo (h)"].sum() if not all_data.empty else pd.DataFrame()
        if not evo_df.empty: st.line_chart(evo_df, x="Data", y="Tempo (h)", height=300)
        else: st.info("Sem dados suficientes para gráfico.")
    with right2:
        st.markdown("### Questões por matéria")
        if not all_data.empty:
            rows = all_data.groupby("Matéria", as_index=False)["Exercícios"].sum().rename(columns={"Exercícios": "Respondidas"})
            st.dataframe(rows, use_container_width=True, hide_index=True, height=300)
        else: st.info("Sem registros de questões.")
elif page == "Adicionar":
    st.markdown("<h1>➕ Adicionar estudo</h1>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Cadastre seus estudos direto pelo site.</div>", unsafe_allow_html=True)
    with st.form("form_adicionar_estudo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            study_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
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
            if not content.strip(): st.warning("Preencha o conteúdo estudado antes de salvar.")
            elif hits > exercises: st.warning("O número de acertos não pode ser maior que o número de exercícios.")
            else:
                save_record(study_date, subject, content, time_hours, exercises, hits, pending, observations)
                st.success("Estudo salvo com sucesso!"); st.rerun()

else:
    df = read_subject(all_data, page)
    st.markdown(f"<h1>{icons[page]} {page}</h1>", unsafe_allow_html=True)
    st.markdown(f"<div class='subtitle'>Acompanhe e gerencie seus registros de {page}.</div>", unsafe_allow_html=True)
    if df.empty:
        st.warning(f"Não encontrei registros de {page} na Google Planilhas.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: show_metric_card("Horas na matéria", round(df["Tempo (h)"].sum(), 1), "Tempo registrado")
        with c2: show_metric_card("Exercícios resolvidos", int(df["Exercícios"].sum()), "Questões feitas")
        with c3: show_metric_card("Pendências", int(open_pending_mask(df).sum()), "Em aberto")
        st.write(""); st.markdown("### Evolução")
        chart_df = df.dropna(subset=["Data"]).groupby("Data", as_index=False)["Tempo (h)"].sum()
        if not chart_df.empty: st.line_chart(chart_df, x="Data", y="Tempo (h)", height=340)
        else: st.info("Sem datas válidas para gerar evolução.")
        st.markdown("### Registros")
        st.dataframe(display_table(df), use_container_width=True, hide_index=True, height=300)
        st.markdown("### Editar ou excluir registro")
        options = {row["ID"]: f"{format_date_br(row['Data'])} — {row['Conteúdo']}" for _, row in df.iterrows()}
        selected_id = st.selectbox("Escolha um registro", list(options), format_func=lambda rid: options[rid])
        selected = df[df["ID"] == selected_id].iloc[0]
        with st.form(f"edit_{selected_id}"):
            e1, e2 = st.columns(2)
            with e1:
                edit_date = st.date_input("Data do estudo", value=selected["Data"].date() if pd.notna(selected["Data"]) else date.today(), format="DD/MM/YYYY")
                edit_subject = st.selectbox("Matéria", subjects, index=subjects.index(selected["Matéria"]) if selected["Matéria"] in subjects else 0)
                edit_content = st.text_input("Conteúdo estudado", value=selected["Conteúdo"])
            with e2:
                edit_time = st.number_input("Tempo (h)", min_value=0.0, value=float(selected["Tempo (h)"]), step=0.5)
                edit_exercises = st.number_input("Exercícios", min_value=0, value=int(selected["Exercícios"]), step=1)
                edit_hits = st.number_input("Acertos", min_value=0, value=int(selected["Acertos"]), step=1)
            edit_pending = st.selectbox("Pendência", ["Não", "Sim"], index=1 if selected["Pendência"].lower() == "sim" else 0)
            edit_obs = st.text_area("Observações", value=selected["Observações"])
            if st.form_submit_button("💾 Salvar alterações"):
                if not edit_content.strip(): st.warning("Preencha o conteúdo estudado.")
                elif edit_hits > edit_exercises: st.warning("Acertos não podem ser maiores que exercícios.")
                else:
                    pending_done = selected["Pendência feita"] if edit_pending == "Sim" and selected["Pendência"].lower() == "sim" else ""
                    values = build_row_values(edit_date, edit_subject, edit_content, edit_time, edit_exercises, edit_hits, edit_pending, edit_obs, selected["ID"], selected["Última revisão"], selected["Revisão feita"], pending_done)
                    update_record(selected["_sheet_row"], values); st.success("Registro atualizado!"); st.rerun()
        with st.expander("🗑️ Excluir este registro"):
            st.warning("Esta ação apaga a linha da planilha e não poderá ser desfeita.")
            confirm = st.checkbox("Confirmo que quero excluir este registro.", key=f"confirm_{selected_id}")
            if st.button("Excluir definitivamente", type="primary", disabled=not confirm, key=f"delete_{selected_id}"):
                delete_record(selected["_sheet_row"]); st.rerun()
