import uuid
from datetime import date, datetime, timedelta

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ============================================================
# StudyProgress — versão com menu lateral + Cronograma/Simulados/Banco de Erros
# Mantém a aba antiga Registros e adiciona abas novas sem apagar seus dados.
# ============================================================

st.set_page_config(
    page_title="StudyProgress",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPREADSHEET_NAME = "FutureEng_V4"
WORKSHEET_NAME = "Registros"

# --------- Sistema antigo: Registros ---------
REVIEW_INTERVALS = {
    0: {"label": "1 dia após adicionar", "days": 1},
    1: {"label": "1 semana depois", "days": 7},
    2: {"label": "mais 1 semana depois", "days": 7},
}
REVIEW_TYPE_OPTIONS = ["Espaçada", "Mensal", "Sem revisão"]
REVIEW_TYPE_CODES = {"Espaçada": "E", "Mensal": "M", "Sem revisão": "N"}
REVIEW_TYPE_LABELS = {value: key for key, value in REVIEW_TYPE_CODES.items()}

SUBJECTS = [
    "Matemática", "Física", "Química", "Biologia", "Português", "História",
    "Geografia", "Filosofia", "Sociologia", "Literatura", "Redação",
]
REGISTROS_COLUMNS = [
    "Data", "Matéria", "Conteúdo", "Tempo (h)", "Exercícios", "Acertos",
    "Pendência", "Observações", "ID", "Última revisão", "Revisão feita", "Pendência feita",
]

# --------- Abas novas ---------
SHEET_HEADERS = {
    "Cronograma_Provas": [
        "ID_Atividade", "Data", "Dia", "Semana", "Tipo", "Área", "Atividade", "Prova",
        "Questões", "Status", "Tempo_Estimado", "Meta_Acertos", "Observações",
    ],
    "Provas_Cadastradas": [
        "ID_Prova", "Nome_Prova", "Área", "Ano", "Tipo", "Total_Questões", "Data_Prevista", "Status",
    ],
    "Respostas_Simulados": [
        "ID_Resposta", "ID_Prova", "Prova", "Área", "Questão", "Sua_Resposta", "Data_Resposta",
    ],
    "Correcoes_Simulados": [
        "ID_Correcao", "ID_Prova", "Prova", "Área", "Questão", "Sua_Resposta", "Gabarito",
        "Resultado", "Tipo_Erro", "Conteúdo", "Comentário", "Data_Correção",
    ],
    "Banco_Erros": [
        "ID_Erro", "ID_Prova", "Prova", "Área", "Questão", "Sua_Resposta", "Gabarito",
        "Resultado", "Tipo_Erro", "Conteúdo", "Comentário", "Revisao_Etapa", "Proxima_Revisao",
        "Status_Revisao", "Data_Criacao", "Ultima_Revisao",
    ],
    "Gabaritos": ["ID_Prova", "Prova", "Área", "Questão", "Gabarito", "Conteúdo"],
}

STATUS_OPTIONS = ["Pendente", "Fazendo", "Feito", "Corrigido", "Pulado"]
ALT_OPTIONS = ["", "A", "B", "C", "D", "E"]
TIPO_ERRO_OPTIONS = ["", "Conteúdo", "Interpretação", "Conta", "Atenção", "Tempo", "Chute", "Outro"]

MENU_ITEMS = [
    "Início", "Semana", "Simulados", "Correção", "Banco de Erros", "Pendências",
    "Desempenho", "Adicionar", "Provas Cadastradas",
] + SUBJECTS

MENU_ICONS = {
    "Início": "🏠", "Semana": "📅", "Simulados": "✅", "Correção": "📝", "Banco de Erros": "🎯",
    "Pendências": "🔔", "Desempenho": "📊", "Adicionar": "➕", "Provas Cadastradas": "🗂️",
    "Matemática": "√x", "Física": "⚛️", "Química": "⚗️", "Biologia": "🌿", "Português": "📚",
    "História": "🏛️", "Geografia": "🌎", "Filosofia": "💭", "Sociologia": "👥",
    "Literatura": "📖", "Redação": "✎",
}

# ============================================================
# CSS — design baseado no protótipo com menu lateral azul/roxo
# ============================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1320px; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1D4ED8 0%, #312E81 100%);
        border-right: 0;
    }
    section[data-testid="stSidebar"] * { color: white !important; }
    section[data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 14px;
        padding: 8px 10px;
        margin-bottom: 4px;
        transition: 0.18s ease;
    }
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(255,255,255,.14);
    }
    section[data-testid="stSidebar"] [aria-checked="true"] {
        background: rgba(255,255,255,.23) !important;
        box-shadow: inset 4px 0 0 #FFFFFF;
    }
    .sidebar-title {
        font-size: 23px; font-weight: 800; margin: 10px 0 20px 0; color: #fff;
        letter-spacing: -.4px;
    }
    .sidebar-profile {
        margin-top: 24px; padding: 14px; border-radius: 18px;
        background: rgba(255,255,255,.12); font-size: 13px; line-height: 1.35;
    }

    .page-title { font-size: 30px; font-weight: 800; color: #0F172A; margin-bottom: 2px; }
    .page-subtitle { color: #64748B; margin-top: 0; margin-bottom: 18px; }
    .topbar {
        display:flex; justify-content:space-between; align-items:center; gap:16px;
        padding: 14px 18px; border: 1px solid #E5E7EB; border-radius: 20px; background:#FFFFFF;
        box-shadow: 0 10px 30px rgba(15,23,42,.05); margin-bottom: 18px;
    }
    .date-pill { padding: 10px 14px; border-radius: 14px; background:#F8FAFC; border:1px solid #E2E8F0; color:#334155; font-weight:600; }

    .hero {
        padding: 26px; border-radius: 28px; background: linear-gradient(135deg, #EFF6FF 0%, #F5F3FF 55%, #FFF7ED 100%);
        border: 1px solid #E5E7EB; margin-bottom:18px; box-shadow: 0 16px 40px rgba(2,6,23,.06);
    }
    .hero h1 { margin:0; font-size:32px; color:#0F172A; letter-spacing:-.6px; }
    .hero p { color:#475569; margin:8px 0 0 0; }

    .card {
        background:#FFFFFF; border:1px solid #E5E7EB; border-radius:22px; padding:20px;
        box-shadow: 0 12px 32px rgba(15,23,42,.06); height:100%;
    }
    .metric-card {
        background:#FFFFFF; border:1px solid #E5E7EB; border-radius:20px; padding:18px;
        box-shadow: 0 10px 24px rgba(15,23,42,.05);
    }
    .metric-title { color:#64748B; font-size:13px; font-weight:700; margin-bottom:6px; }
    .metric-value { color:#0F172A; font-size:28px; font-weight:800; line-height:1; }
    .metric-desc { color:#94A3B8; font-size:12px; margin-top:6px; }

    .week-grid { display:grid; grid-template-columns: repeat(7, minmax(105px, 1fr)); gap:12px; }
    .day-card {
        border:1px solid #E5E7EB; border-radius:18px; padding:14px; min-height:136px; background:#FFFFFF;
        box-shadow: 0 8px 22px rgba(15,23,42,.04);
    }
    .day-card.today { border:2px solid #7C3AED; background:#F5F3FF; }
    .day-name { font-size:12px; font-weight:800; color:#475569; text-transform:uppercase; }
    .day-num { font-size:22px; font-weight:800; color:#0F172A; margin:2px 0 8px 0; }
    .day-activity { font-size:13px; color:#334155; line-height:1.3; min-height:40px; }
    .status-dot { display:inline-block; width:8px; height:8px; border-radius:99px; background:#7C3AED; margin-right:6px; }
    .status-text { color:#64748B; font-size:12px; }

    .badge { display:inline-block; padding:5px 10px; border-radius:999px; font-size:12px; font-weight:800; }
    .badge-blue { background:#DBEAFE; color:#1D4ED8; }
    .badge-purple { background:#EDE9FE; color:#6D28D9; }
    .badge-green { background:#DCFCE7; color:#15803D; }
    .badge-red { background:#FEE2E2; color:#DC2626; }
    .badge-orange { background:#FFEDD5; color:#EA580C; }
    .badge-gray { background:#F1F5F9; color:#475569; }

    .error-card { border:1px solid #FECACA; background:#FFF7F7; border-radius:20px; padding:16px; margin-bottom:12px; }
    .success-card { border:1px solid #BBF7D0; background:#F0FDF4; border-radius:20px; padding:16px; margin-bottom:12px; }

    div[data-testid="stButton"] button, div[data-testid="stFormSubmitButton"] button {
        border-radius: 14px; border: 0; background: linear-gradient(135deg,#2563EB,#7C3AED); color:#FFFFFF;
        font-weight: 800; padding: 0.58rem 1rem;
    }
    div[data-testid="stButton"] button:hover, div[data-testid="stFormSubmitButton"] button:hover {
        filter: brightness(1.03); border:0; color:#FFFFFF;
    }
    .small-muted { color:#64748B; font-size:13px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 14px; padding: 8px 16px; background: #F8FAFC; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Utilidades
# ============================================================
@st.cache_resource
def get_spreadsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME)


def connect_to_sheet():
    return get_spreadsheet().worksheet(WORKSHEET_NAME)


def get_or_create_ws(name, headers):
    spreadsheet = get_spreadsheet()
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(headers), 10))
        ws.update("A1", [headers])
        return ws
    current = ws.row_values(1)
    if current[: len(headers)] != headers:
        if not any(current):
            ws.update("A1", [headers])
        else:
            st.warning(f"A aba {name} existe, mas o cabeçalho não está igual ao esperado. Confira antes de usar.")
    return ws


def new_id(prefix="ID"):
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"


def format_date_br(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    parsed = parse_google_sheet_date(value)
    return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")


def parse_date(value):
    return parse_google_sheet_date(value)


def parse_google_sheet_date(value):
    """Converte datas vindas do Google Sheets, inclusive número serial do Excel/Sheets."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    text = str(value).strip()
    # Quando a data vem como número serial, ex.: 46236
    try:
        if text.replace(".", "", 1).isdigit() and len(text) <= 6:
            serial = float(text)
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(serial, unit="D")
    except Exception:
        pass
    return pd.to_datetime(value, dayfirst=True, errors="coerce")


def today_ts():
    return pd.Timestamp(date.today()).normalize()


def clear_all_cache():
    load_data.clear()
    load_sheet_df.clear()


@st.cache_data(ttl=10)
def load_sheet_df(sheet_name):
    headers = SHEET_HEADERS[sheet_name]
    ws = get_or_create_ws(sheet_name, headers)
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=headers)
    for col in headers:
        if col not in df.columns:
            df[col] = ""
    df = df[headers]
    return df


def append_rows(sheet_name, rows):
    if not rows:
        return
    ws = get_or_create_ws(sheet_name, SHEET_HEADERS[sheet_name])
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    clear_all_cache()


def update_status_by_id(sheet_name, id_col, item_id, new_status):
    ws = get_or_create_ws(sheet_name, SHEET_HEADERS[sheet_name])
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    try:
        id_index = headers.index(id_col) + 1
        status_index = headers.index("Status") + 1
    except ValueError:
        return False
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) >= id_index and row[id_index - 1] == item_id:
            ws.update_cell(row_idx, status_index, new_status)
            clear_all_cache()
            return True
    return False


def week_bounds(any_day=None):
    base = pd.Timestamp(any_day or date.today()).normalize()
    monday = base - pd.Timedelta(days=base.weekday())
    sunday = monday + pd.Timedelta(days=6)
    return monday, sunday


def nice_day_name(dt):
    nomes = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    return nomes[pd.Timestamp(dt).weekday()]


def status_badge(status):
    status = str(status or "Pendente")
    cls = {
        "Feito": "badge-green", "Corrigido": "badge-green", "Pendente": "badge-purple",
        "Fazendo": "badge-blue", "Pulado": "badge-gray", "Revisar hoje": "badge-red",
        "Agendada": "badge-orange", "Concluída": "badge-green",
    }.get(status, "badge-gray")
    return f'<span class="badge {cls}">{status}</span>'


def area_badge(area):
    area = str(area or "")
    if "Matemática" in area:
        cls = "badge-blue"
    elif "Natureza" in area or area in ["Biologia", "Química", "Física"]:
        cls = "badge-green"
    elif "Linguagens" in area or "Português" in area:
        cls = "badge-orange"
    elif "Fuvest" in area:
        cls = "badge-purple"
    else:
        cls = "badge-gray"
    return f'<span class="badge {cls}">{area}</span>'

# ============================================================
# Sistema antigo — Registros
# ============================================================
def check_sheet_structure(worksheet):
    headers = worksheet.row_values(1)
    if headers[: len(REGISTROS_COLUMNS)] != REGISTROS_COLUMNS:
        raise ValueError("A aba Registros deve ter as colunas nesta ordem: " + " | ".join(REGISTROS_COLUMNS))


@st.cache_data(ttl=10)
def load_data():
    worksheet = connect_to_sheet()
    check_sheet_structure(worksheet)
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=REGISTROS_COLUMNS + ["_sheet_row"])
    id_col = REGISTROS_COLUMNS.index("ID") + 1
    changed = False
    active_records = []
    for sheet_row, record in enumerate(records, start=2):
        is_empty = not any(str(record.get(col, "")).strip() for col in ["Data", "Matéria", "Conteúdo"])
        if is_empty:
            continue
        if not str(record.get("ID", "")).strip():
            record_id = uuid.uuid4().hex[:10].upper()
            worksheet.update_cell(sheet_row, id_col, record_id)
            record["ID"] = record_id
            changed = True
        record["_sheet_row"] = sheet_row
        active_records.append(record)
    if changed:
        records = worksheet.get_all_records()
        active_records = []
        for sheet_row, record in enumerate(records, start=2):
            is_empty = not any(str(record.get(col, "")).strip() for col in ["Data", "Matéria", "Conteúdo"])
            if not is_empty:
                record["_sheet_row"] = sheet_row
                active_records.append(record)
    df = pd.DataFrame(active_records) if active_records else pd.DataFrame(columns=REGISTROS_COLUMNS + ["_sheet_row"])
    for col in REGISTROS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[REGISTROS_COLUMNS + ["_sheet_row"]]
    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df["Última revisão"] = pd.to_datetime(df["Última revisão"], dayfirst=True, errors="coerce")
    df["Tempo (h)"] = pd.to_numeric(df["Tempo (h)"], errors="coerce").fillna(0)
    df["Exercícios"] = pd.to_numeric(df["Exercícios"], errors="coerce").fillna(0).astype(int)
    df["Acertos"] = pd.to_numeric(df["Acertos"], errors="coerce").fillna(0).astype(int)
    text_cols = ["Matéria", "Conteúdo", "Pendência", "Observações", "ID", "Revisão feita", "Pendência feita"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def build_row_values(study_date, subject, content, time_hours, exercises, hits, pending, observations, record_id, last_review="", review_done="", pending_done=""):
    return [
        format_date_br(study_date), subject, content.strip(), float(time_hours), int(exercises), int(hits),
        pending, observations.strip(), record_id,
        format_date_br(last_review) if str(last_review).strip() not in ("", "NaT") else "",
        review_done, pending_done,
    ]


def make_review_state(review_type, stage=0):
    code = REVIEW_TYPE_CODES.get(review_type, "E")
    return f"{code}|{int(stage)}"


def parse_review_state(value):
    text_value = str(value).strip()
    if "|" in text_value:
        code, stage_text = text_value.split("|", 1)
        code = code.strip().upper()
        if code not in REVIEW_TYPE_LABELS:
            code = "E"
        stage = int(stage_text) if stage_text.strip().isdigit() else 0
        return REVIEW_TYPE_LABELS[code], stage
    if text_value.isdigit():
        return "Espaçada", int(text_value)
    if text_value.lower() == "sim":
        return "Espaçada", 1
    return "Espaçada", 0


def get_next_review_info(row):
    review_type, stage = parse_review_state(row.get("Revisão feita", ""))
    if review_type == "Sem revisão":
        return pd.NaT, stage, "Sem revisão", make_review_state(review_type, stage)
    base_date = row.get("Última revisão") if stage > 0 and pd.notna(row.get("Última revisão")) else row.get("Data")
    if pd.isna(base_date):
        return pd.NaT, stage, "Sem data base", make_review_state(review_type, stage)
    if review_type == "Mensal":
        next_review = pd.Timestamp(base_date) + pd.DateOffset(months=1)
        label = "mensal"
    elif stage in REVIEW_INTERVALS:
        interval = REVIEW_INTERVALS[stage]
        next_review = pd.Timestamp(base_date) + pd.Timedelta(days=interval["days"])
        label = interval["label"]
    else:
        next_review = pd.Timestamp(base_date) + pd.DateOffset(months=1)
        label = "mensal"
    return next_review, stage, label, make_review_state(review_type, stage)


def save_record(study_date, subject, content, time_hours, exercises, hits, pending, observations, review_type):
    worksheet = connect_to_sheet()
    worksheet.append_row(
        build_row_values(study_date, subject, content, time_hours, exercises, hits, pending, observations, uuid.uuid4().hex[:10].upper(), review_done=make_review_state(review_type, 0)),
        value_input_option="USER_ENTERED",
    )
    clear_all_cache()


def update_record(sheet_row, values):
    worksheet = connect_to_sheet()
    worksheet.update(range_name=f"A{int(sheet_row)}:L{int(sheet_row)}", values=[values], value_input_option="USER_ENTERED")
    clear_all_cache()


def delete_record(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.delete_rows(int(sheet_row))
    clear_all_cache()


def mark_pending_done(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.update_cell(int(sheet_row), REGISTROS_COLUMNS.index("Pendência feita") + 1, "Sim")
    clear_all_cache()


def mark_review_done(sheet_row, current_state):
    worksheet = connect_to_sheet()
    review_type, current_stage = parse_review_state(current_state)
    if review_type == "Sem revisão":
        clear_all_cache(); return
    next_stage = current_stage + 1
    worksheet.update(
        range_name=f"J{int(sheet_row)}:K{int(sheet_row)}",
        values=[[date.today().strftime("%d/%m/%Y"), make_review_state(review_type, next_stage)]],
        value_input_option="USER_ENTERED",
    )
    clear_all_cache()


def open_pending_mask(df):
    return df["Pendência"].str.lower().eq("sim") & ~df["Pendência feita"].str.lower().eq("sim")


def get_pending(df):
    return df[open_pending_mask(df)].copy() if not df.empty else pd.DataFrame(columns=REGISTROS_COLUMNS + ["_sheet_row"])


def get_reviews(df):
    if df.empty:
        return pd.DataFrame(columns=REGISTROS_COLUMNS + ["_sheet_row", "Próxima revisão", "Etapa revisão", "Tipo revisão", "Estado revisão", "Dias de atraso"])
    review_df = df.dropna(subset=["Data"]).copy()
    review_info = review_df.apply(get_next_review_info, axis=1, result_type="expand")
    review_info.columns = ["Próxima revisão", "Etapa revisão", "Tipo revisão", "Estado revisão"]
    review_df = pd.concat([review_df, review_info], axis=1)
    today = today_ts()
    review_df["Próxima revisão"] = pd.to_datetime(review_df["Próxima revisão"], errors="coerce")
    review_df["Dias de atraso"] = (today - review_df["Próxima revisão"]).dt.days
    return review_df[review_df["Próxima revisão"].notna() & (review_df["Próxima revisão"] <= today)].sort_values("Dias de atraso", ascending=False)


def display_table(df):
    if df.empty:
        return df.copy()
    shown = df.copy()
    for date_col in ["Data", "Última revisão"]:
        if date_col in shown.columns:
            shown[date_col] = shown[date_col].apply(format_date_br)
    return shown.drop(columns=["_sheet_row", "ID", "Revisão feita", "Pendência feita"], errors="ignore")

# ============================================================
# Novas funções — cronograma, simulado, correção, erros
# ============================================================
def load_cronograma():
    df = load_sheet_df("Cronograma_Provas")
    if not df.empty:
        df["Data_dt"] = df["Data"].apply(parse_google_sheet_date)
    else:
        df["Data_dt"] = pd.NaT
    return df


def load_provas():
    df = load_sheet_df("Provas_Cadastradas")
    if not df.empty:
        df["Total_Questões"] = pd.to_numeric(df["Total_Questões"], errors="coerce").fillna(45).astype(int)
        df["Data_dt"] = df["Data_Prevista"].apply(parse_google_sheet_date)
    return df


def load_respostas():
    df = load_sheet_df("Respostas_Simulados")
    if not df.empty:
        df["Questão"] = pd.to_numeric(df["Questão"], errors="coerce").fillna(0).astype(int)
    return df


def load_correcoes():
    df = load_sheet_df("Correcoes_Simulados")
    if not df.empty:
        df["Questão"] = pd.to_numeric(df["Questão"], errors="coerce").fillna(0).astype(int)
    return df


def load_erros():
    df = load_sheet_df("Banco_Erros")
    if not df.empty:
        df["Questão"] = pd.to_numeric(df["Questão"], errors="coerce").fillna(0).astype(int)
        df["Proxima_Revisao_dt"] = df["Proxima_Revisao"].apply(parse_google_sheet_date)
    else:
        df["Proxima_Revisao_dt"] = pd.NaT
    return df


def proxima_revisao_por_etapa(etapa):
    etapa = int(etapa or 0)
    dias = {0: 1, 1: 7, 2: 30, 3: 60}.get(etapa, 30)
    return date.today() + timedelta(days=dias)


def salvar_respostas(prova_row, respostas_dict):
    old = load_respostas()
    id_prova = prova_row["ID_Prova"]
    # Não apaga as antigas. Mantém histórico. A correção sempre pega a última resposta por questão.
    rows = []
    for questao, alt in respostas_dict.items():
        if str(alt).strip():
            rows.append([
                new_id("RESP"), id_prova, prova_row["Nome_Prova"], prova_row["Área"], int(questao), alt,
                date.today().strftime("%d/%m/%Y"),
            ])
    append_rows("Respostas_Simulados", rows)


def salvar_correcoes_e_erros(prova_row, correcao_rows):
    append_rows("Correcoes_Simulados", correcao_rows)
    error_rows = []
    for row in correcao_rows:
        # [ID_Correcao, ID_Prova, Prova, Área, Questão, Sua_Resposta, Gabarito, Resultado, Tipo_Erro, Conteúdo, Comentário, Data_Correção]
        resultado = row[7]
        if resultado in ["Errei", "Chutei/dúvida"]:
            etapa = 0
            prox = proxima_revisao_por_etapa(etapa)
            error_rows.append([
                new_id("ERR"), row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10],
                etapa, prox.strftime("%d/%m/%Y"), "Agendada", date.today().strftime("%d/%m/%Y"), "",
            ])
    append_rows("Banco_Erros", error_rows)


def avancar_revisao_erro(id_erro, acertou=True):
    ws = get_or_create_ws("Banco_Erros", SHEET_HEADERS["Banco_Erros"])
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    idx = {h: i + 1 for i, h in enumerate(headers)}
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) >= idx["ID_Erro"] and row[idx["ID_Erro"] - 1] == id_erro:
            etapa_atual = 0
            try:
                etapa_atual = int(row[idx["Revisao_Etapa"] - 1])
            except Exception:
                etapa_atual = 0
            nova_etapa = etapa_atual + 1 if acertou else etapa_atual
            status = "Concluída" if nova_etapa >= 4 and acertou else "Agendada"
            prox = proxima_revisao_por_etapa(nova_etapa)
            ws.update_cell(row_idx, idx["Revisao_Etapa"], str(nova_etapa))
            ws.update_cell(row_idx, idx["Proxima_Revisao"], prox.strftime("%d/%m/%Y"))
            ws.update_cell(row_idx, idx["Status_Revisao"], status)
            ws.update_cell(row_idx, idx["Ultima_Revisao"], date.today().strftime("%d/%m/%Y"))
            clear_all_cache()
            return True
    return False

# ============================================================
# Componentes visuais
# ============================================================
def show_topbar(title, subtitle=""):
    st.markdown(
        f"""
        <div class="topbar">
            <div>
                <div class="page-title">{title}</div>
                <div class="page-subtitle">{subtitle}</div>
            </div>
            <div class="date-pill">📅 {date.today().strftime('%d/%m/%Y')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(title, value, desc=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_week_cards(cronograma, selected_day=None):
    """Renderiza a semana usando componentes nativos do Streamlit.
    Isso evita o erro de aparecer <div class=...> na tela, que acontece em alguns deploys/mobile.
    """
    monday, sunday = week_bounds(selected_day)
    week_df = cronograma[(cronograma["Data_dt"] >= monday) & (cronograma["Data_dt"] <= sunday)].copy()
    cols = st.columns(7)
    for i, col in enumerate(cols):
        d = monday + pd.Timedelta(days=i)
        day_rows = week_df[week_df["Data_dt"] == d]
        activity = "Livre"
        status = "Livre"
        area = ""
        prova = ""
        questoes = ""
        if not day_rows.empty:
            first = day_rows.iloc[0]
            activity = str(first.get("Atividade", "")) or str(first.get("Tipo", "")) or "Atividade"
            status = str(first.get("Status", "Pendente")) or "Pendente"
            area = str(first.get("Área", ""))
            prova = str(first.get("Prova", ""))
            questoes = str(first.get("Questões", ""))
        with col:
            border_color = "#7C3AED" if d.normalize() == today_ts() else "#E5E7EB"
            bg = "#F5F3FF" if d.normalize() == today_ts() else "#FFFFFF"
            st.markdown(
                f"""
                <div style="border:1px solid {border_color}; background:{bg}; border-radius:18px; padding:14px; min-height:160px; box-shadow:0 8px 20px rgba(15,23,42,.05);">
                    <div style="font-size:12px;font-weight:800;color:#475569;text-transform:uppercase;">{nice_day_name(d)[:3]}</div>
                    <div style="font-size:24px;font-weight:800;color:#0F172A;margin:2px 0 8px 0;">{d.strftime('%d')}</div>
                    <div style="font-size:13px;color:#334155;line-height:1.35;min-height:46px;">{activity}</div>
                    <div style="font-size:11px;color:#64748B;margin-top:8px;">{area}</div>
                    <div style="font-size:11px;color:#64748B;">{prova}</div>
                    <div style="font-size:11px;color:#64748B;">{questoes}</div>
                    <div style="margin-top:10px;font-size:12px;color:#64748B;">● {status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption(f"Semana de {format_date_br(monday)} a {format_date_br(sunday)}")


def sidebar_menu():
    with st.sidebar:
        st.markdown('<div class="sidebar-title">📘 StudyProgress</div>', unsafe_allow_html=True)
        default_page = st.session_state.get("menu_page", "Início")
        default_index = MENU_ITEMS.index(default_page) if default_page in MENU_ITEMS else 0
        page = st.radio(
            "Menu",
            MENU_ITEMS,
            index=default_index,
            label_visibility="collapsed",
            format_func=lambda item: f"{MENU_ICONS.get(item, '')} {item}",
            key="menu_page",
        )
        st.markdown(
            """
            <div class="sidebar-profile">
                <b>Israel Rodrigues</b><br>
                Foco • Disciplina • Resultado
            </div>
            """,
            unsafe_allow_html=True,
        )
    return page


# ============================================================
# Páginas
# ============================================================
def page_inicio(all_data):
    show_topbar("Olá, Israel! 👋", "Vamos continuar evoluindo hoje.")
    cron = load_cronograma()
    erros = load_erros()
    reviews_antigas = get_reviews(all_data)
    pend_antigas = get_pending(all_data)

    today_activities = cron[cron["Data_dt"] == today_ts()].copy() if not cron.empty else pd.DataFrame()
    lembrete = today_activities.iloc[0] if not today_activities.empty else None

    st.markdown('<div class="hero"><h1>Lembrete de hoje</h1><p>Veja o que precisa ser feito agora e o restante da semana.</p></div>', unsafe_allow_html=True)

    left, right = st.columns([1, 2])
    with left:
        with st.container(border=True):
            st.markdown("### 🎯 Lembrete de hoje")
            if lembrete is not None:
                st.markdown(area_badge(lembrete.get("Área", "")), unsafe_allow_html=True)
                st.markdown(f"#### {lembrete.get('Atividade', '')}")
                if str(lembrete.get("Observações", "")).strip():
                    st.write(lembrete.get("Observações", ""))
                st.caption(f"Prova: {lembrete.get('Prova', '')} • Questões: {lembrete.get('Questões', '')}")
                if st.button("Começar agora", key="start_today"):
                    st.session_state["menu_page"] = "Simulados"
                    st.rerun()
            else:
                st.success("Hoje não tem atividade cadastrada no cronograma.")
    with right:
        with st.container(border=True):
            st.markdown("### 📅 Visão da semana")
            render_week_cards(cron)

    st.write("")
    pend_erros_total = len(erros[(erros["Status_Revisao"] != "Concluída")]) if not erros.empty else 0
    rev_erros_hoje = len(erros[(erros["Status_Revisao"] != "Concluída") & (erros["Proxima_Revisao_dt"] <= today_ts())]) if not erros.empty else 0
    revisoes_total = len(reviews_antigas) + rev_erros_hoje
    pendencias_total = len(pend_antigas) + pend_erros_total

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        concluidas = int((cron["Status"].astype(str).str.lower().isin(["feito", "corrigido"])).sum()) if not cron.empty else 0
        metric_card("Atividades concluídas", concluidas, "no cronograma")
    with c2:
        metric_card("Revisões", revisoes_total, "vencidas/para hoje")
    with c3:
        metric_card("Pendências", pendencias_total, "itens em aberto")
    with c4:
        total_ex = all_data["Exercícios"].sum() if not all_data.empty else 0
        total_hits = all_data["Acertos"].sum() if not all_data.empty else 0
        taxa = round((total_hits / total_ex) * 100) if total_ex else 0
        metric_card("Taxa de acertos", f"{taxa}%", "média geral")

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("### 🔔 Próximas pendências")
            proximas = cron[cron["Status"].astype(str).str.lower().isin(["pendente", "fazendo"])] if not cron.empty else pd.DataFrame()
            proximas = proximas.sort_values("Data_dt").head(6) if not proximas.empty else proximas
            if proximas.empty and pend_antigas.empty:
                st.success("Nada pendente no cronograma.")
            else:
                for _, row in proximas.iterrows():
                    st.markdown(f"- **{format_date_br(row['Data_dt'])}** — {row['Atividade']} {status_badge(row['Status'])}", unsafe_allow_html=True)
                for _, row in pend_antigas.head(3).iterrows():
                    st.markdown(f"- **{row['Matéria']} — {row['Conteúdo']}** • pendência antiga")
    with right:
        with st.container(border=True):
            st.markdown("### 🔁 Revisões para hoje")
            due = erros[(erros["Status_Revisao"] != "Concluída") & (erros["Proxima_Revisao_dt"] <= today_ts())] if not erros.empty else pd.DataFrame()
            if due.empty and reviews_antigas.empty:
                st.success("Nenhuma revisão vencida.")
            for _, row in due.head(5).iterrows():
                st.markdown(f"- **Questão {row['Questão']} — {row['Prova']}** • {row['Tipo_Erro']} {status_badge('Revisar hoje')}", unsafe_allow_html=True)
            for _, row in reviews_antigas.head(3).iterrows():
                st.markdown(f"- **{row['Matéria']} — {row['Conteúdo']}** • revisão antiga")


def page_semana():
    show_topbar("Semana", "Cronograma horizontal com o que fazer hoje e nos próximos dias.")
    cron = load_cronograma()
    if cron.empty:
        st.warning("A aba Cronograma_Provas está vazia. Cole o cronograma que eu enviei na planilha.")
        return
    selected = st.date_input("Escolha uma semana", value=date.today(), format="DD/MM/YYYY")
    render_week_cards(cron, selected)
    monday, sunday = week_bounds(selected)
    week_df = cron[(cron["Data_dt"] >= monday) & (cron["Data_dt"] <= sunday)].sort_values("Data_dt").copy()
    st.write("")
    st.markdown("### Detalhes da semana")
    if week_df.empty:
        st.info("Sem atividades cadastradas nessa semana.")
        return
    for _, row in week_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.3, 2.2, 1, 1])
            with c1:
                st.markdown(f"**{nice_day_name(row['Data_dt'])} — {format_date_br(row['Data_dt'])}**")
                st.markdown(area_badge(row.get("Área", "")), unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{row.get('Atividade', '')}**")
                st.caption(f"Prova: {row.get('Prova', '')} • Questões: {row.get('Questões', '')} • {row.get('Tempo_Estimado', '')}")
            with c3:
                st.markdown(status_badge(row.get("Status", "Pendente")), unsafe_allow_html=True)
            with c4:
                if row.get("Status") != "Feito":
                    if st.button("Marcar feito", key=f"feito_{row['ID_Atividade']}"):
                        update_status_by_id("Cronograma_Provas", "ID_Atividade", row["ID_Atividade"], "Feito")
                        st.rerun()


def page_simulados():
    show_topbar("Simulados", "Você só precisa marcar a alternativa e o número da questão.")
    provas = load_provas()
    if provas.empty:
        st.warning("A aba Provas_Cadastradas está vazia. Cole as provas na planilha.")
        return
    tab1, tab2 = st.tabs(["Responder", "Histórico de respostas"])
    with tab1:
        prova_nome = st.selectbox("Escolha a prova", provas["Nome_Prova"].tolist())
        prova = provas[provas["Nome_Prova"] == prova_nome].iloc[0]
        total = int(prova.get("Total_Questões", 45) or 45)
        st.markdown(f"### {prova_nome}")
        st.caption(f"Área: {prova['Área']} • Questões: 1 a {total}")
        with st.form(f"respostas_{prova['ID_Prova']}"):
            respostas = {}
            cols = st.columns(5)
            for q in range(1, total + 1):
                with cols[(q - 1) % 5]:
                    respostas[q] = st.selectbox(f"Q{q}", ALT_OPTIONS, key=f"resp_{prova['ID_Prova']}_{q}")
            submitted = st.form_submit_button("Salvar respostas")
            if submitted:
                preenchidas = {q: alt for q, alt in respostas.items() if alt}
                if not preenchidas:
                    st.warning("Marque pelo menos uma alternativa antes de salvar.")
                else:
                    salvar_respostas(prova, preenchidas)
                    st.success(f"Salvei {len(preenchidas)} resposta(s).")
                    st.rerun()
    with tab2:
        resp = load_respostas()
        if resp.empty:
            st.info("Nenhuma resposta salva ainda.")
        else:
            st.dataframe(resp.sort_values(["Data_Resposta", "Prova", "Questão"], ascending=[False, True, True]), use_container_width=True, hide_index=True)


def page_correcao():
    show_topbar("Correção do simulado", "Informe o gabarito. O app identifica erros e manda para o Banco de Erros.")
    provas = load_provas()
    respostas = load_respostas()
    if provas.empty or respostas.empty:
        st.warning("Você precisa ter provas cadastradas e respostas salvas antes de corrigir.")
        return
    provas_com_resp = respostas["Prova"].dropna().unique().tolist()
    prova_nome = st.selectbox("Escolha a prova para corrigir", provas_com_resp)
    prova = provas[provas["Nome_Prova"] == prova_nome].iloc[0] if prova_nome in provas["Nome_Prova"].values else None
    if prova is None:
        st.warning("Não encontrei essa prova em Provas_Cadastradas.")
        return
    resp = respostas[respostas["Prova"] == prova_nome].copy()
    # pega a última resposta por questão
    resp = resp.drop_duplicates(subset=["Questão"], keep="last").sort_values("Questão")
    st.caption(f"{len(resp)} resposta(s) encontradas para corrigir.")
    with st.form(f"corrigir_{prova['ID_Prova']}"):
        rows_corr = []
        for _, r in resp.iterrows():
            q = int(r["Questão"])
            c1, c2, c3, c4, c5 = st.columns([.8, .8, .8, 1.4, 2])
            with c1: st.write(f"**Q{q}**")
            with c2: st.write(f"Sua: **{r['Sua_Resposta']}**")
            with c3: gab = st.selectbox("Gab.", ALT_OPTIONS[1:], key=f"gab_{prova['ID_Prova']}_{q}")
            resultado_auto = "Acertei" if str(r["Sua_Resposta"]).strip().upper() == str(gab).strip().upper() else "Errei"
            with c4: tipo = st.selectbox("Tipo do erro", TIPO_ERRO_OPTIONS, key=f"tipo_{prova['ID_Prova']}_{q}", disabled=(resultado_auto == "Acertei"))
            with c5: conteudo = st.text_input("Conteúdo/comentário", key=f"cont_{prova['ID_Prova']}_{q}")
            comentario = conteudo
            rows_corr.append([
                new_id("COR"), prova["ID_Prova"], prova_nome, prova["Área"], q, r["Sua_Resposta"], gab,
                resultado_auto, tipo if resultado_auto == "Errei" else "", conteudo, comentario, date.today().strftime("%d/%m/%Y"),
            ])
        submitted = st.form_submit_button("Salvar correção e criar pendências")
        if submitted:
            salvar_correcoes_e_erros(prova, rows_corr)
            st.success("Correção salva. O que você errou entrou no Banco de Erros.")
            st.rerun()


def page_banco_erros():
    show_topbar("Banco de Erros", "As questões erradas voltam como pendência para revisão.")
    erros = load_erros()
    if erros.empty:
        st.info("Ainda não existem erros registrados. Corrija um simulado para aparecer aqui.")
        return
    tab1, tab2, tab3 = st.tabs(["Para revisar", "Todas", "Revisadas"])
    with tab1:
        due = erros[(erros["Status_Revisao"] != "Concluída") & (erros["Proxima_Revisao_dt"] <= today_ts())].sort_values("Proxima_Revisao_dt")
        if due.empty:
            st.success("Nenhuma questão vencida para revisar hoje.")
        for _, row in due.iterrows():
            st.markdown('<div class="error-card">', unsafe_allow_html=True)
            st.markdown(f"### Questão {row['Questão']} — {row['Prova']}")
            st.markdown(area_badge(row["Área"]), unsafe_allow_html=True)
            st.write(f"**Sua resposta:** {row['Sua_Resposta']} • **Gabarito:** {row['Gabarito']}")
            st.write(f"**Tipo de erro:** {row['Tipo_Erro']} • **Conteúdo:** {row['Conteúdo']}")
            if row.get("Comentário"):
                st.caption(row["Comentário"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Acertei agora", key=f"ok_err_{row['ID_Erro']}"):
                    avancar_revisao_erro(row["ID_Erro"], acertou=True); st.rerun()
            with c2:
                if st.button("Ainda tenho dúvida", key=f"duv_err_{row['ID_Erro']}"):
                    avancar_revisao_erro(row["ID_Erro"], acertou=False); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        show = erros.copy()
        show["Proxima_Revisao"] = show["Proxima_Revisao_dt"].apply(format_date_br)
        st.dataframe(show.drop(columns=["Proxima_Revisao_dt"], errors="ignore"), use_container_width=True, hide_index=True)
    with tab3:
        rev = erros[erros["Status_Revisao"] == "Concluída"]
        if rev.empty:
            st.info("Nenhuma questão concluída ainda.")
        else:
            st.dataframe(rev.drop(columns=["Proxima_Revisao_dt"], errors="ignore"), use_container_width=True, hide_index=True)


def page_pendencias(all_data):
    show_topbar("Pendências", "Junta pendências antigas, revisões antigas e erros de simulado.")
    pend = get_pending(all_data)
    rev = get_reviews(all_data)
    erros = load_erros()
    due = erros[(erros["Status_Revisao"] != "Concluída") & (erros["Proxima_Revisao_dt"] <= today_ts())] if not erros.empty else pd.DataFrame()
    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Pendências antigas", len(pend), "aba Registros")
    with c2: metric_card("Revisões antigas", len(rev), "conteúdos")
    with c3: metric_card("Erros para revisar", len(due), "simulados")
    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("### Pendências da aba Registros")
        if pend.empty: st.success("Sem pendências antigas.")
        for _, row in pend.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Matéria']} — {row['Conteúdo']}**")
                st.caption(format_date_br(row["Data"]))
                if st.button("Marcar como feita", key=f"pend_antiga_{row['ID']}"):
                    mark_pending_done(row["_sheet_row"]); st.rerun()
    with right:
        st.markdown("### Revisões antigas")
        if rev.empty: st.success("Sem revisões antigas.")
        for _, row in rev.head(10).iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Matéria']} — {row['Conteúdo']}**")
                st.caption(f"Próxima revisão: {format_date_br(row['Próxima revisão'])}")
                if st.button("Revisei hoje", key=f"rev_antiga_{row['ID']}"):
                    mark_review_done(row["_sheet_row"], row["Estado revisão"]); st.rerun()


def page_desempenho(all_data):
    show_topbar("Desempenho", "Resumo dos estudos e simulados.")
    correcoes = load_correcoes()
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Horas", f"{round(all_data['Tempo (h)'].sum(), 1)}h" if not all_data.empty else "0h", "registradas")
    with c2: metric_card("Questões", int(all_data["Exercícios"].sum()) if not all_data.empty else 0, "registros")
    with c3:
        if not correcoes.empty:
            acertos = int((correcoes["Resultado"] == "Acertei").sum())
            total = len(correcoes)
            metric_card("Acertos simulados", f"{round(acertos/total*100)}%", f"{acertos}/{total}")
        else:
            metric_card("Acertos simulados", "0%", "sem correções")
    with c4: metric_card("Erros no banco", len(load_erros()), "para revisar")
    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("### Horas por data")
        evo = all_data.dropna(subset=["Data"]).groupby("Data", as_index=False)["Tempo (h)"].sum() if not all_data.empty else pd.DataFrame()
        if evo.empty: st.info("Sem dados suficientes.")
        else: st.line_chart(evo, x="Data", y="Tempo (h)", height=300)
    with right:
        st.markdown("### Erros por tipo")
        erros = load_erros()
        if erros.empty: st.info("Sem erros registrados.")
        else:
            grp = erros.groupby("Tipo_Erro", as_index=False).size().rename(columns={"size": "Total"})
            st.bar_chart(grp, x="Tipo_Erro", y="Total", height=300)


def page_adicionar():
    show_topbar("Adicionar estudo", "Cadastro antigo mantido do jeito que já funciona.")
    with st.form("form_adicionar_estudo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            study_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            subject = st.selectbox("Matéria", SUBJECTS)
            content = st.text_input("Conteúdo estudado")
        with c2:
            time_hours = st.number_input("Tempo (h)", min_value=0.0, step=0.5)
            exercises = st.number_input("Exercícios", min_value=0, step=1)
            hits = st.number_input("Acertos", min_value=0, step=1)
        pending = st.selectbox("Pendência", ["Não", "Sim"])
        review_type = st.selectbox("Tipo de revisão", REVIEW_TYPE_OPTIONS)
        observations = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar estudo")
        if submitted:
            if not content.strip():
                st.warning("Preencha o conteúdo estudado antes de salvar.")
            elif hits > exercises:
                st.warning("O número de acertos não pode ser maior que o número de exercícios.")
            else:
                save_record(study_date, subject, content, time_hours, exercises, hits, pending, observations, review_type)
                st.success("Estudo salvo com sucesso!")
                st.rerun()


def page_provas_cadastradas():
    show_topbar("Provas Cadastradas", "Lista das provas em ordem para você não precisar pensar no dia.")
    provas = load_provas()
    if provas.empty:
        st.info("Aba Provas_Cadastradas vazia.")
    else:
        show = provas.drop(columns=["Data_dt"], errors="ignore").copy()
        if "Data_Prevista" in show.columns:
            show["Data_Prevista"] = show["Data_Prevista"].apply(format_date_br)
        st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("### Cadastrar prova manualmente")
    with st.form("nova_prova"):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome da prova")
            area = st.selectbox("Área", ["Matemática ENEM", "Natureza ENEM", "Linguagens ENEM", "Fuvest", "Simulado Completo"])
            ano = st.number_input("Ano", min_value=2009, max_value=2030, value=2024)
        with c2:
            tipo = st.text_input("Tipo", value="Prova antiga")
            total = st.number_input("Total de questões", min_value=1, max_value=180, value=45)
            data_prevista = st.date_input("Data prevista", value=date.today(), format="DD/MM/YYYY")
        if st.form_submit_button("Adicionar prova"):
            append_rows("Provas_Cadastradas", [[new_id("PROVA"), nome, area, int(ano), tipo, int(total), data_prevista.strftime("%d/%m/%Y"), "Pendente"]])
            st.success("Prova cadastrada.")
            st.rerun()


def page_subject(all_data, subject):
    show_topbar(subject, f"Acompanhe e gerencie seus registros de {subject}.")
    df = all_data[all_data["Matéria"] == subject].copy() if not all_data.empty else pd.DataFrame(columns=REGISTROS_COLUMNS + ["_sheet_row"])
    if df.empty:
        st.warning(f"Não encontrei registros de {subject} na Google Planilhas.")
        return
    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Horas", round(df["Tempo (h)"].sum(), 1), "tempo registrado")
    with c2: metric_card("Exercícios", int(df["Exercícios"].sum()), "questões feitas")
    with c3: metric_card("Pendências", int(open_pending_mask(df).sum()), "em aberto")
    st.write("")
    st.markdown("### Evolução")
    chart_df = df.dropna(subset=["Data"]).groupby("Data", as_index=False)["Tempo (h)"].sum()
    if not chart_df.empty:
        st.line_chart(chart_df, x="Data", y="Tempo (h)", height=300)
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
            edit_subject = st.selectbox("Matéria", SUBJECTS, index=SUBJECTS.index(selected["Matéria"]) if selected["Matéria"] in SUBJECTS else 0)
            edit_content = st.text_input("Conteúdo estudado", value=selected["Conteúdo"])
        with e2:
            edit_time = st.number_input("Tempo (h)", min_value=0.0, value=float(selected["Tempo (h)"]), step=0.5)
            edit_exercises = st.number_input("Exercícios", min_value=0, value=int(selected["Exercícios"]), step=1)
            edit_hits = st.number_input("Acertos", min_value=0, value=int(selected["Acertos"]), step=1)
        edit_pending = st.selectbox("Pendência", ["Não", "Sim"], index=1 if selected["Pendência"].lower() == "sim" else 0)
        current_review_type, current_review_stage = parse_review_state(selected["Revisão feita"])
        edit_review_type = st.selectbox("Tipo de revisão", REVIEW_TYPE_OPTIONS, index=REVIEW_TYPE_OPTIONS.index(current_review_type) if current_review_type in REVIEW_TYPE_OPTIONS else 0)
        edit_obs = st.text_area("Observações", value=selected["Observações"])
        if st.form_submit_button("Salvar alterações"):
            if not edit_content.strip():
                st.warning("Preencha o conteúdo estudado.")
            elif edit_hits > edit_exercises:
                st.warning("Acertos não podem ser maiores que exercícios.")
            else:
                pending_done = selected["Pendência feita"] if edit_pending == "Sim" and selected["Pendência"].lower() == "sim" else ""
                if edit_review_type != current_review_type:
                    review_state = make_review_state(edit_review_type, 0); last_review = ""
                else:
                    review_state = make_review_state(edit_review_type, current_review_stage); last_review = selected["Última revisão"]
                values = build_row_values(edit_date, edit_subject, edit_content, edit_time, edit_exercises, edit_hits, edit_pending, edit_obs, selected["ID"], last_review, review_state, pending_done)
                update_record(selected["_sheet_row"], values)
                st.success("Registro atualizado!")
                st.rerun()
    with st.expander("Excluir este registro"):
        st.warning("Esta ação apaga a linha da planilha e não poderá ser desfeita.")
        confirm = st.checkbox("Confirmo que quero excluir este registro.", key=f"confirm_{selected_id}")
        if st.button("Excluir definitivamente", type="primary", disabled=not confirm, key=f"delete_{selected_id}"):
            delete_record(selected["_sheet_row"]); st.rerun()

# ============================================================
# Execução
# ============================================================
try:
    all_data = load_data()
except Exception as error:
    st.error("Não consegui carregar os dados. Confira se a aba Registros possui todas as 12 colunas na ordem correta.")
    st.exception(error)
    st.stop()

page = sidebar_menu()

if page == "Início":
    page_inicio(all_data)
elif page == "Semana":
    page_semana()
elif page == "Simulados":
    page_simulados()
elif page == "Correção":
    page_correcao()
elif page == "Banco de Erros":
    page_banco_erros()
elif page == "Pendências":
    page_pendencias(all_data)
elif page == "Desempenho":
    page_desempenho(all_data)
elif page == "Adicionar":
    page_adicionar()
elif page == "Provas Cadastradas":
    page_provas_cadastradas()
else:
    page_subject(all_data, page)
