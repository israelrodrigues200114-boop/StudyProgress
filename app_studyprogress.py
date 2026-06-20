import uuid
import html
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:
    px = None
    go = None
from google.oauth2.service_account import Credentials

# ============================================================
# StudyProgress — versão com menu lateral + Cronograma/Simulados/Banco de Erros
# Mantém a aba antiga Registros e adiciona abas novas sem apagar seus dados.
# ============================================================

st.set_page_config(
    page_title="StudyProgress",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPREADSHEET_NAME = "FutureEng_V4"
APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")

def today_date():
    """Data de hoje no Brasil/São Paulo. Evita o Streamlit Cloud usar UTC e virar o dia antes da meia-noite daqui."""
    return datetime.now(APP_TIMEZONE).date()

def now_br():
    """Agora no fuso do Brasil/São Paulo."""
    return datetime.now(APP_TIMEZONE)

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
    "Cronograma_Teoria": [
        "ID_Teoria", "Dia_Semana", "Horario_Inicio", "Horario_Fim",
        "Materia", "Status", "Observacoes"
    ],
}

STATUS_OPTIONS = ["Pendente", "Fazendo", "Feito", "Corrigido", "Pulado"]
ALT_OPTIONS = ["", "A", "B", "C", "D", "E"]
TIPO_ERRO_OPTIONS = ["", "Conteúdo", "Interpretação", "Conta", "Atenção", "Tempo", "Chute", "Outro"]

MENU_ITEMS = [
    "Início", "Planejamento", "Simulados", "Correção", "Banco de Erros",
    "Pendências", "Desempenho", "Adicionar",
] + SUBJECTS

MENU_SHORT = {
    "Início": "IN", "Planejamento": "PL", "Simulados": "SM", "Correção": "CR",
    "Banco de Erros": "BE", "Pendências": "PE", "Desempenho": "DE", "Adicionar": "AD",
    "Matemática": "MT", "Física": "FI", "Química": "QU", "Biologia": "BI",
    "Português": "PT", "História": "HI", "Geografia": "GE", "Filosofia": "FL",
    "Sociologia": "SO", "Literatura": "LI", "Redação": "RD",
}

SUBJECT_COLORS = {
    "Matemática": "#8B5CF6",   # lavanda forte
    "Física": "#38BDF8",       # azul elétrico suave
    "Química": "#14B8A6",      # teal
    "Biologia": "#22C55E",     # verde folha
    "Português": "#FB7185",    # rosa coral
    "História": "#F59E0B",     # dourado
    "Geografia": "#06B6D4",    # ciano
    "Filosofia": "#A78BFA",    # lilás
    "Sociologia": "#F472B6",   # pink suave
    "Literatura": "#F97316",   # laranja palco
    "Redação": "#EAB308",      # amarelo ouro
}

AREA_COLORS = {
    "Matemática ENEM": "#8B5CF6",
    "Natureza ENEM": "#22C55E",
    "Linguagens ENEM": "#FB7185",
    "Fuvest": "#A78BFA",
    "Simulado Completo": "#14B8A6",
    "ENEM": "#38BDF8",
}

# ============================================================
# CSS — layout final: menu lateral limpo, cards profissionais e cores por matéria
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    :root {
        --midnight:#0B1026;
        --midnight-2:#151B3D;
        --violet:#6D5DF6;
        --lavender:#A78BFA;
        --rose:#F472B6;
        --coral:#FB7185;
        --gold:#F6C453;
        --peach:#FDBA74;
        --paper:#FCF8F3;
        --card:#FFFFFF;
        --ink:#111827;
        --muted:#6B7280;
        --border:#E9E2DA;
        --soft:#FFF7ED;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(167,139,250,.16), transparent 28%),
            radial-gradient(circle at top right, rgba(251,113,133,.13), transparent 24%),
            linear-gradient(180deg, #FCF8F3 0%, #FFFDF9 42%, #F8FAFC 100%);
    }

    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.4rem;
        max-width: 1400px;
    }

    /* Sidebar — estética midnight, sem bolinhas, sem cara genérica */
    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 22% 6%, rgba(246,196,83,.18), transparent 18%),
            radial-gradient(circle at 90% 36%, rgba(244,114,182,.15), transparent 22%),
            linear-gradient(180deg, #0B1026 0%, #151B3D 52%, #2A124B 100%);
        border-right: 1px solid rgba(255,255,255,.08);
    }

    section[data-testid="stSidebar"] * {
        color: #FFF7ED !important;
    }

    section[data-testid="stSidebar"] ul,
    section[data-testid="stSidebar"] li {
        list-style: none !important;
        padding-left: 0 !important;
        margin-left: 0 !important;
    }

    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        min-height: 46px;
        border: 1px solid transparent !important;
        border-radius: 18px !important;
        padding: .76rem 1rem !important;
        margin: .14rem 0 !important;
        background: transparent !important;
        color: rgba(255,247,237,.88) !important;
        box-shadow: none !important;
        font-weight: 850 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        line-height: 1.1 !important;
        letter-spacing: -.15px;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,.10) !important;
        border-color: rgba(246,196,83,.28) !important;
        transform: translateX(3px);
        color: #FFFFFF !important;
    }

    section[data-testid="stSidebar"] .nav-active > div > button {
        background: linear-gradient(135deg, rgba(167,139,250,.38), rgba(244,114,182,.23)) !important;
        border-color: rgba(246,196,83,.38) !important;
        box-shadow: inset 4px 0 0 #F6C453, 0 14px 30px rgba(0,0,0,.22) !important;
    }

    .sidebar-brand {
        display:flex;
        align-items:center;
        gap:13px;
        padding: 10px 4px 24px 4px;
    }

    .brand-mark {
        width:48px;
        height:48px;
        border-radius:18px;
        background:
            linear-gradient(135deg, #F6C453 0%, #F472B6 48%, #8B5CF6 100%);
        display:flex;
        align-items:center;
        justify-content:center;
        color:#0B1026 !important;
        font-weight:950;
        font-size:17px;
        letter-spacing:-.6px;
        box-shadow: 0 18px 36px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.5);
    }

    .brand-title {
        font-size:22px;
        font-weight:950;
        letter-spacing:-.8px;
        color:#FFFFFF !important;
    }

    .brand-subtitle {
        font-size:12px;
        opacity:.74;
        margin-top:2px;
        color:#FDE68A !important;
    }

    .sidebar-profile {
        margin-top: 24px;
        padding: 15px;
        border-radius: 22px;
        background: rgba(255,255,255,.08);
        font-size: 13px;
        line-height: 1.35;
        border:1px solid rgba(246,196,83,.20);
        box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
    }

    /* Cards e containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid var(--border) !important;
        border-radius: 26px !important;
        box-shadow: 0 18px 48px rgba(17,24,39,.065) !important;
        background: rgba(255,255,255,.78) !important;
        backdrop-filter: blur(10px);
    }

    .topbar {
        display:flex;
        justify-content:space-between;
        align-items:center;
        gap:16px;
        padding: 16px 18px;
        border: 1px solid var(--border);
        border-radius: 28px;
        background: rgba(255,255,255,.76);
        box-shadow: 0 18px 42px rgba(17,24,39,.06);
        margin-bottom: 18px;
        backdrop-filter: blur(10px);
    }

    .page-title {
        font-size: 30px;
        font-weight: 950;
        color: var(--ink);
        margin-bottom: 3px;
        letter-spacing:-.9px;
    }

    .page-subtitle {
        color: var(--muted);
        margin-top: 0;
        margin-bottom: 0;
        font-weight: 500;
    }

    .date-pill {
        padding: 10px 14px;
        border-radius: 16px;
        background: linear-gradient(135deg, #FFF7ED, #F5F3FF);
        border:1px solid #E9E2DA;
        color:#1F2937;
        font-weight:850;
        white-space: nowrap;
    }

    /* Hero inspirado em noite de estudos + brilho de palco */
    .hero {
        position:relative;
        overflow:hidden;
        min-height:165px;
        padding: 28px 30px;
        border-radius: 34px;
        background:
            radial-gradient(circle at 78% 12%, rgba(246,196,83,.30), transparent 12%),
            radial-gradient(circle at 92% 35%, rgba(244,114,182,.22), transparent 18%),
            linear-gradient(135deg, #0B1026 0%, #1B1F4B 44%, #3A195D 100%);
        border: 1px solid rgba(246,196,83,.26);
        margin-bottom:18px;
        box-shadow: 0 24px 60px rgba(11,16,38,.22);
    }

    .hero:before {
        content:"";
        position:absolute;
        inset:0;
        background-image:
            radial-gradient(circle, rgba(255,255,255,.55) 1px, transparent 1px),
            radial-gradient(circle, rgba(246,196,83,.42) 1px, transparent 1px);
        background-size: 42px 42px, 68px 68px;
        background-position: 0 0, 18px 12px;
        opacity:.16;
        pointer-events:none;
    }

    .hero h1 {
        position:relative;
        margin:0;
        font-size:36px;
        color:#FFF7ED;
        letter-spacing:-1.1px;
        max-width:720px;
    }

    .hero p {
        position:relative;
        color:#E9D5FF;
        margin:10px 0 0 0;
        font-size:15px;
        font-weight:600;
        max-width:720px;
    }

    .study-art {
        position:absolute;
        right:28px;
        top:24px;
        width:260px;
        height:125px;
        opacity:.98;
    }

    .book-a, .book-b, .book-c {
        position:absolute;
        border-radius:16px;
        box-shadow:0 18px 34px rgba(0,0,0,.24);
        border:1px solid rgba(255,255,255,.23);
    }

    .book-a {
        width:86px;
        height:118px;
        right:124px;
        top:2px;
        background:linear-gradient(180deg,#8B5CF6,#4C1D95);
        transform:rotate(-6deg);
    }

    .book-b {
        width:86px;
        height:118px;
        right:68px;
        top:7px;
        background:linear-gradient(180deg,#F472B6,#9D174D);
        transform:rotate(5deg);
    }

    .book-c {
        width:86px;
        height:118px;
        right:14px;
        top:13px;
        background:linear-gradient(180deg,#F6C453,#D97706);
        transform:rotate(-2deg);
    }

    .book-line {
        position:absolute;
        left:14px;
        right:14px;
        height:7px;
        border-radius:99px;
        background:rgba(255,247,237,.78);
    }

    .pencil {
        position:absolute;
        width:132px;
        height:14px;
        right:72px;
        top:101px;
        background:linear-gradient(90deg,#FB7185,#FDBA74,#F6C453);
        border-radius:999px;
        transform:rotate(-14deg);
        box-shadow:0 12px 24px rgba(0,0,0,.20);
    }

    .metric-card, .pro-card, .soft-card {
        background: rgba(255,255,255,.84);
        border:1px solid var(--border);
        border-radius:24px;
        padding:19px;
        box-shadow: 0 16px 38px rgba(17,24,39,.06);
        height:100%;
        backdrop-filter: blur(8px);
    }

    .metric-title {
        color:#6B7280;
        font-size:13px;
        font-weight:850;
        margin-bottom:9px;
    }

    .metric-value {
        color:#111827;
        font-size:31px;
        font-weight:950;
        line-height:1;
        letter-spacing:-1px;
    }

    .metric-desc {
        color:#9CA3AF;
        font-size:12px;
        margin-top:8px;
        font-weight:650;
    }

    .section-title {
        font-size:23px;
        font-weight:950;
        color:#111827;
        margin: 0 0 9px 0;
        letter-spacing:-.65px;
    }

    .section-sub {
        color:#6B7280;
        font-size:13px;
        margin-bottom:14px;
        font-weight:500;
    }

    .task-card {
        border:1px solid #ECE7DE;
        background: linear-gradient(180deg, rgba(255,255,255,.93), rgba(255,251,245,.82));
        border-radius:20px;
        padding:14px 15px;
        margin-bottom:10px;
        box-shadow:0 10px 25px rgba(17,24,39,.045);
    }

    .task-line {
        display:flex;
        justify-content:space-between;
        gap:12px;
        align-items:center;
    }

    .task-title {
        font-weight:950;
        color:#111827;
        letter-spacing:-.25px;
    }

    .task-meta {
        color:#6B7280;
        font-size:13px;
        margin-top:4px;
        line-height:1.35;
    }

    .subject-pill, .badge {
        display:inline-block;
        padding:5px 10px;
        border-radius:999px;
        font-size:12px;
        font-weight:950;
        white-space:nowrap;
    }

    .badge-blue { background:#EEF2FF; color:#6D5DF6; }
    .badge-purple { background:#F5F3FF; color:#7C3AED; }
    .badge-green { background:#ECFDF5; color:#059669; }
    .badge-red { background:#FFF1F2; color:#E11D48; }
    .badge-orange { background:#FFF7ED; color:#EA580C; }
    .badge-gray { background:#F3F4F6; color:#4B5563; }

    .week-grid {
        display:grid;
        grid-template-columns: repeat(7, minmax(135px, 1fr));
        gap:14px;
        width:100%;
        overflow-x:auto;
        padding:2px 0 12px 0;
        scrollbar-width: thin;
    }

    .week-native-card {
        border:1px solid #ECE7DE;
        border-radius:22px;
        padding:15px 14px;
        min-height:190px;
        background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(255,251,245,.78));
        box-shadow: 0 13px 28px rgba(17,24,39,.055);
        display:flex;
        flex-direction:column;
        justify-content:flex-start;
        gap:10px;
        overflow:hidden;
    }

    @media (max-width: 980px) {
        .week-grid {
            grid-template-columns: repeat(7, minmax(150px, 150px));
        }
    }

    .week-native-card.today {
        border:2px solid #F6C453;
        background:
            radial-gradient(circle at top right, rgba(244,114,182,.16), transparent 35%),
            linear-gradient(180deg, #FFF7ED, #F5F3FF);
        box-shadow: 0 18px 40px rgba(246,196,83,.16);
    }

    .week-day-head {
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:8px;
        padding-bottom:8px;
        border-bottom:1px solid rgba(233,226,218,.78);
    }

    .day-name {
        font-size:12px;
        font-weight:950;
        color:#6B7280;
        text-transform:uppercase;
        letter-spacing:.35px;
    }

    .day-num {
        font-size:28px;
        font-weight:950;
        color:#111827;
        margin-top:2px;
        letter-spacing:-.8px;
        line-height:1;
    }

    .week-today-pill {
        font-size:10px;
        font-weight:950;
        color:#7C2D12;
        background:#FEF3C7;
        border:1px solid #FDE68A;
        border-radius:999px;
        padding:4px 7px;
        white-space:nowrap;
    }

    .week-card-body {
        display:flex;
        flex-direction:column;
        gap:8px;
        margin-top:2px;
    }

    .week-task {
        border-radius:14px;
        padding:9px 10px;
        background:rgba(255,255,255,.72);
        border:1px solid rgba(233,226,218,.86);
    }

    .week-area {
        font-size:11px;
        font-weight:950;
        text-transform:uppercase;
        line-height:1.15;
        margin-bottom:3px;
    }

    .week-activity {
        font-size:13px;
        font-weight:850;
        color:#111827;
        line-height:1.25;
        word-break:break-word;
    }

    .week-status {
        display:inline-block;
        margin-top:7px;
        padding:3px 7px;
        border-radius:999px;
        font-size:10px;
        font-weight:950;
        background:#F5F3FF;
        color:#6D5DF6;
    }

    .week-empty {
        color:#6B7280;
        font-size:14px;
        font-weight:850;
        margin-top:8px;
    }

    .week-sub {
        color:#9CA3AF;
        font-size:12px;
        margin-top:-4px;
    }

    .week-more {
        font-size:12px;
        color:#6B7280;
        font-weight:800;
        margin-top:2px;
    }

    /* Botões principais — toque showgirl sem perder cara de estudo */
    div[data-testid="stButton"] button,
    div[data-testid="stFormSubmitButton"] button {
        border-radius: 16px !important;
        border: 0 !important;
        background: linear-gradient(135deg,#6D5DF6 0%, #F472B6 58%, #F6C453 130%) !important;
        color:#FFFFFF !important;
        font-weight: 950 !important;
        padding: 0.66rem 1.12rem !important;
        box-shadow: 0 14px 28px rgba(109,93,246,.18) !important;
        letter-spacing:-.1px;
    }

    div[data-testid="stButton"] button:hover,
    div[data-testid="stFormSubmitButton"] button:hover {
        filter: brightness(1.04);
        transform: translateY(-1px);
        color:#FFFFFF !important;
        box-shadow: 0 18px 34px rgba(244,114,182,.22) !important;
    }

    /* Inputs/tabelas */
    [data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(255,255,255,.52);
        padding: 6px;
        border-radius: 18px;
        border:1px solid #ECE7DE;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 14px;
        padding: 9px 17px;
        background: transparent;
        font-weight:900;
        color:#4B5563;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #F5F3FF, #FFF7ED) !important;
        color:#111827 !important;
        box-shadow: 0 8px 18px rgba(17,24,39,.05);
    }

    @media (max-width: 900px) {
        .study-art { display:none; }
        .hero h1 { font-size:29px; }
        .topbar { flex-direction:column; align-items:flex-start; }
    }
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


@st.cache_resource
def get_worksheet_cached(name):
    """Retorna a aba sem fazer leituras extras de cabeçalho a cada rerun."""
    spreadsheet = get_spreadsheet()
    return spreadsheet.worksheet(name)


def get_or_create_ws(name, headers):
    spreadsheet = get_spreadsheet()
    try:
        return get_worksheet_cached(name)
    except Exception:
        try:
            ws = spreadsheet.worksheet(name)
            return ws
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(headers), 10))
            ws.update("A1", [headers])
            get_worksheet_cached.clear()
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


def parse_time_hours(value):
    """Converte tempo de estudo sem deixar 1.5 virar 15.

    No Google Sheets em pt-BR, às vezes 1.5 pode ser interpretado como 15.
    Para sessões de estudo, valores inteiros entre 10 e 99 provavelmente vieram desse bug
    e são tratados como décimos: 15 -> 1.5, 25 -> 2.5.
    """
    if value is None or pd.isna(value) or str(value).strip() == "":
        return 0.0
    raw = str(value).strip().replace("h", "").replace("H", "").strip()
    try:
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        num = float(raw)
    except Exception:
        return 0.0
    if num.is_integer() and 10 <= num <= 99 and "," not in str(value) and "." not in str(value):
        num = num / 10
    return round(num, 2)


def format_time_hours_for_sheet(value):
    """Salva decimal com vírgula para evitar bug de localidade no Google Sheets."""
    try:
        num = float(value)
    except Exception:
        num = 0.0
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def today_ts():
    return pd.Timestamp(today_date()).normalize()


def clear_all_cache():
    """Limpa tudo só quando realmente precisa recarregar todas as abas.

Antes o app limpava todos os caches a cada registro salvo. Isso fazia a Home
reler várias abas do Google Sheets no mesmo minuto e podia estourar a cota.
"""
    load_data.clear()
    load_sheet_df.clear()


def clear_registros_cache():
    """Limpa apenas a aba Registros, mantendo cronogramas/provas em cache."""
    load_data.clear()


def clear_aux_cache():
    """Limpa apenas as abas novas: cronogramas, simulados e banco de erros."""
    load_sheet_df.clear()


@st.cache_data(ttl=300, show_spinner=False)
def load_sheet_df(sheet_name):
    """Carrega uma aba nova com apenas UMA leitura no Sheets.

Evita row_values + get_all_records, que dobrava as leituras e causava erro 429.
"""
    headers = SHEET_HEADERS[sheet_name]
    ws = get_or_create_ws(sheet_name, headers)
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=headers)
    sheet_headers = values[0]
    rows = values[1:]
    if sheet_headers[: len(headers)] != headers:
        st.warning(f"Confira o cabeçalho da aba {sheet_name}. O app tentou carregar mesmo assim.")
    normalized_rows = []
    for row in rows:
        row = row + [""] * max(0, len(sheet_headers) - len(row))
        normalized_rows.append(dict(zip(sheet_headers, row)))
    df = pd.DataFrame(normalized_rows) if normalized_rows else pd.DataFrame(columns=headers)
    for col in headers:
        if col not in df.columns:
            df[col] = ""
    return df[headers]


def append_rows(sheet_name, rows):
    if not rows:
        return
    ws = get_or_create_ws(sheet_name, SHEET_HEADERS[sheet_name])
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    clear_aux_cache()


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
    base = pd.Timestamp(any_day or today_date()).normalize()
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


@st.cache_data(ttl=300, show_spinner=False)
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
    df["Tempo (h)"] = df["Tempo (h)"].apply(parse_time_hours)
    df["Exercícios"] = pd.to_numeric(df["Exercícios"], errors="coerce").fillna(0).astype(int)
    df["Acertos"] = pd.to_numeric(df["Acertos"], errors="coerce").fillna(0).astype(int)
    text_cols = ["Matéria", "Conteúdo", "Pendência", "Observações", "ID", "Revisão feita", "Pendência feita"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def build_row_values(study_date, subject, content, time_hours, exercises, hits, pending, observations, record_id, last_review="", review_done="", pending_done=""):
    return [
        format_date_br(study_date), subject, content.strip(), format_time_hours_for_sheet(time_hours), int(exercises), int(hits),
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
        value_input_option="RAW",
    )
    clear_registros_cache()


def update_record(sheet_row, values):
    worksheet = connect_to_sheet()
    worksheet.update(range_name=f"A{int(sheet_row)}:L{int(sheet_row)}", values=[values], value_input_option="RAW")
    clear_registros_cache()


def delete_record(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.delete_rows(int(sheet_row))
    clear_registros_cache()


def mark_pending_done(sheet_row):
    worksheet = connect_to_sheet()
    worksheet.update_cell(int(sheet_row), REGISTROS_COLUMNS.index("Pendência feita") + 1, "Sim")
    clear_registros_cache()


def mark_review_done(sheet_row, current_state):
    worksheet = connect_to_sheet()
    review_type, current_stage = parse_review_state(current_state)
    if review_type == "Sem revisão":
        clear_registros_cache(); return
    next_stage = current_stage + 1
    worksheet.update(
        range_name=f"J{int(sheet_row)}:K{int(sheet_row)}",
        values=[[today_date().strftime("%d/%m/%Y"), make_review_state(review_type, next_stage)]],
        value_input_option="USER_ENTERED",
    )
    clear_registros_cache()


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



def normalize_text(value):
    return str(value or "").strip()


def get_color_for_subject(subject):
    return SUBJECT_COLORS.get(normalize_text(subject), "#6B7280")


def get_color_for_area(area):
    text = normalize_text(area)
    for key, color in AREA_COLORS.items():
        if key.lower() in text.lower():
            return color
    return "#6B7280"


def subject_badge(subject):
    color = get_color_for_subject(subject)
    return f'<span class="subject-pill" style="background:{color}1F;color:{color};border:1px solid {color}38;">{subject}</span>' 


def load_planejamento_provas():
    """Une Cronograma_Provas com Provas_Cadastradas.
    Assim, quando você cadastra uma prova manualmente para hoje, ela aparece na Home e na semana.
    """
    cron = load_cronograma().copy()
    provas = load_provas().copy()
    frames = []
    if not cron.empty:
        frames.append(cron)
    if not provas.empty:
        manual = pd.DataFrame()
        manual["ID_Atividade"] = provas["ID_Prova"].astype(str)
        manual["Data"] = provas["Data_Prevista"].apply(format_date_br)
        manual["Data_dt"] = provas["Data_dt"]
        manual["Dia"] = manual["Data_dt"].apply(lambda x: nice_day_name(x) if pd.notna(x) else "")
        manual["Semana"] = ""
        manual["Tipo"] = provas["Tipo"].astype(str)
        manual["Área"] = provas["Área"].astype(str)
        manual["Atividade"] = provas["Nome_Prova"].astype(str)
        manual["Prova"] = provas["Nome_Prova"].astype(str)
        manual["Questões"] = provas["Total_Questões"].apply(lambda n: f"1-{int(n)}" if pd.notna(n) and int(n) > 0 else "")
        manual["Status"] = provas["Status"].replace("", "Pendente")
        manual["Tempo_Estimado"] = ""
        manual["Meta_Acertos"] = ""
        manual["Observações"] = "Cadastrada em Provas_Cadastradas"
        manual = manual[SHEET_HEADERS["Cronograma_Provas"] + ["Data_dt"]]
        frames.append(manual)
    if not frames:
        base = pd.DataFrame(columns=SHEET_HEADERS["Cronograma_Provas"] + ["Data_dt"])
        return base
    combined = pd.concat(frames, ignore_index=True)
    combined["Data_dt"] = combined["Data_dt"].apply(parse_google_sheet_date)
    combined = combined.dropna(subset=["Data_dt"], how="all")
    combined = combined.sort_values(["Data_dt", "Área", "Atividade"])
    combined = combined.drop_duplicates(subset=["ID_Atividade"], keep="first")
    return combined


def card_header(title, subtitle=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)

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


def load_cronograma_teoria():
    df = load_sheet_df("Cronograma_Teoria")
    if df.empty:
        return df
    for col in ["Dia_Semana", "Horario_Inicio", "Horario_Fim", "Materia", "Status", "Observacoes"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    ordem = {"segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6}
    df["_ordem_dia"] = df["Dia_Semana"].str.lower().map(ordem).fillna(99).astype(int)
    df["_hora_ordem"] = df["Horario_Inicio"].astype(str).str.replace(":", "", regex=False)
    return df.sort_values(["_ordem_dia", "_hora_ordem", "Materia"])


def theory_today(df):
    if df.empty:
        return df
    hoje = nice_day_name(today_ts()).lower()
    today_df = df[(df["Dia_Semana"].str.lower() == hoje) & (df["Status"].str.lower().isin(["ativo", "", "pendente"]))].copy()
    return today_df.sort_values(["Horario_Inicio", "Materia"])


def append_teoria(dia, inicio, fim, materia, status, obs):
    append_rows("Cronograma_Teoria", [[new_id("TEO"), dia, inicio, fim, materia, status, obs]])


def update_teoria(item_id, dia, inicio, fim, materia, status, obs):
    ws = get_or_create_ws("Cronograma_Teoria", SHEET_HEADERS["Cronograma_Teoria"])
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    idx = {h: i + 1 for i, h in enumerate(headers)}
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) >= idx["ID_Teoria"] and row[idx["ID_Teoria"] - 1] == item_id:
            ws.update(range_name=f"A{row_idx}:G{row_idx}", values=[[item_id, dia, inicio, fim, materia, status, obs]], value_input_option="RAW")
            clear_aux_cache()
            return True
    return False


def delete_teoria(item_id):
    ws = get_or_create_ws("Cronograma_Teoria", SHEET_HEADERS["Cronograma_Teoria"])
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    try:
        id_idx = headers.index("ID_Teoria") + 1
    except ValueError:
        return False
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) >= id_idx and row[id_idx - 1] == item_id:
            ws.delete_rows(row_idx)
            clear_aux_cache()
            return True
    return False


def proxima_revisao_por_etapa(etapa):
    etapa = int(etapa or 0)
    dias = {0: 1, 1: 7, 2: 30, 3: 60}.get(etapa, 30)
    return today_date() + timedelta(days=dias)


def salvar_respostas(prova_row, respostas_dict):
    old = load_respostas()
    id_prova = prova_row["ID_Prova"]
    # Não apaga as antigas. Mantém histórico. A correção sempre pega a última resposta por questão.
    rows = []
    for questao, alt in respostas_dict.items():
        if str(alt).strip():
            rows.append([
                new_id("RESP"), id_prova, prova_row["Nome_Prova"], prova_row["Área"], int(questao), alt,
                today_date().strftime("%d/%m/%Y"),
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
                etapa, prox.strftime("%d/%m/%Y"), "Agendada", today_date().strftime("%d/%m/%Y"), "",
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
            ws.update_cell(row_idx, idx["Ultima_Revisao"], today_date().strftime("%d/%m/%Y"))
            clear_aux_cache()
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
            <div class="date-pill">Hoje • {today_date().strftime('%d/%m/%Y')}</div>
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


def task_card(title, meta="", badge_html="", color="#8B5CF6"):
    st.markdown(
        f"""
        <div class="task-card" style="border-left:5px solid {color};">
            <div class="task-line">
                <div>
                    <div class="task-title">{title}</div>
                    <div class="task-meta">{meta}</div>
                </div>
                <div>{badge_html}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def apply_plot_style(fig, height=340):
    """Aplica uma identidade visual mais refinada aos gráficos."""
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=18, b=12),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,251,245,.55)",
        font=dict(family="Inter, sans-serif", color="#111827"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor="#E9E2DA",
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280"),
    )
    fig.update_yaxes(
        gridcolor="rgba(233,226,218,.75)",
        linecolor="#E9E2DA",
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280"),
    )
    return fig


def quick_nav_button(label, page, key, prefill=None):
    if st.button(label, key=key):
        if prefill:
            st.session_state["prefill_adicionar"] = prefill
        st.session_state["menu_page"] = page
        st.rerun()


def render_week_cards(cronograma, selected_day=None, teoria=None):
    """Renderiza a semana com provas + cronograma teórico.

    A renderização acontece em um componente HTML único para evitar bugs no celular/tablet:
    - nada de HTML aparecendo como texto;
    - nada de palavras quebrando letra por letra;
    - rolagem horizontal quando a tela for pequena.
    """
    monday, sunday = week_bounds(selected_day)
    if cronograma is not None and not cronograma.empty:
        week_df = cronograma[(cronograma["Data_dt"] >= monday) & (cronograma["Data_dt"] <= sunday)].copy()
    else:
        week_df = pd.DataFrame()

    if teoria is not None and not teoria.empty:
        teoria_df = teoria[teoria["Status"].astype(str).str.lower().isin(["ativo", "", "pendente"])].copy()
    else:
        teoria_df = pd.DataFrame()

    day_map = {
        "segunda": "Segunda", "terça": "Terça", "terca": "Terça", "quarta": "Quarta",
        "quinta": "Quinta", "sexta": "Sexta", "sábado": "Sábado", "sabado": "Sábado", "domingo": "Domingo",
    }

    cards = []
    for i in range(7):
        d = monday + pd.Timedelta(days=i)
        dia_nome = nice_day_name(d)
        dia_norm = dia_nome.lower()
        day_rows = week_df[week_df["Data_dt"] == d] if not week_df.empty else pd.DataFrame()
        if not teoria_df.empty:
            mapped_days = teoria_df["Dia_Semana"].astype(str).str.lower().map(day_map).fillna(teoria_df["Dia_Semana"].astype(str)).str.lower()
            theory_rows = teoria_df[mapped_days == dia_norm]
        else:
            theory_rows = pd.DataFrame()
        is_today = d.normalize() == today_ts()
        today_pill = '<span class="today-pill">HOJE</span>' if is_today else ''

        task_blocks = []

        if not theory_rows.empty:
            for _, row in theory_rows.sort_values(["Horario_Inicio", "Materia"]).head(3).iterrows():
                materia = normalize_text(row.get("Materia", "Teoria")) or "Teoria"
                horario = f"{normalize_text(row.get('Horario_Inicio',''))}–{normalize_text(row.get('Horario_Fim',''))}".strip("–")
                color = get_color_for_subject(materia)
                detalhe = "Cronograma de teoria"
                title = f"{horario} • {materia}" if horario else materia
                task_blocks.append(
                    f'''<div class="task theory" style="border-left-color:{color};">
                        <div class="area" style="color:{color};">TEORIA</div>
                        <div class="activity">{html.escape(title)}</div>
                        <div class="detail">{html.escape(detalhe)}</div>
                    </div>'''
                )

        if not day_rows.empty:
            for _, row in day_rows.head(3).iterrows():
                area = normalize_text(row.get("Área", "")) or "Prova"
                atividade = normalize_text(row.get("Atividade", "")) or normalize_text(row.get("Prova", "")) or "Atividade cadastrada"
                prova = normalize_text(row.get("Prova", ""))
                questoes = normalize_text(row.get("Questões", ""))
                status = normalize_text(row.get("Status", "Pendente")) or "Pendente"
                color = get_color_for_area(area)
                detalhe_parts = [p for p in [prova if prova and prova != atividade else "", f"Questões {questoes}" if questoes else ""] if p]
                detail = " • ".join(detalhe_parts)
                task_blocks.append(
                    f'''<div class="task prova" style="border-left-color:{color};">
                        <div class="area" style="color:{color};">{html.escape(area)}</div>
                        <div class="activity">{html.escape(atividade)}</div>
                        <div class="detail">{html.escape(detail)}</div>
                        <span class="status">{html.escape(status)}</span>
                    </div>'''
                )

        total_extra = max(0, len(day_rows) - 3) + max(0, len(theory_rows) - 3)
        if total_extra:
            task_blocks.append(f'<div class="more">+ {total_extra} atividade(s)</div>')

        if not task_blocks:
            tasks_html = '<div class="free">Livre</div><div class="sub">Sem atividade marcada</div>'
        else:
            tasks_html = ''.join(task_blocks)

        active = ' today' if is_today else ''
        cards.append(
            f'''<div class="day-card{active}">
                <div class="head">
                    <div>
                        <div class="dow">{html.escape(nice_day_name(d)[:3]).upper()}</div>
                        <div class="num">{d.strftime('%d')}</div>
                    </div>
                    {today_pill}
                </div>
                <div class="body">{tasks_html}</div>
            </div>'''
        )

    component_html = f"""
    <!doctype html>
    <html>
    <head>
    <meta charset="utf-8" />
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin:0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: transparent; }}
        .week-wrap {{ width:100%; overflow-x:auto; padding: 4px 0 14px; }}
        .week-grid {{ display:grid; grid-template-columns: repeat(7, minmax(172px, 1fr)); gap:18px; min-width: 1210px; }}
        .day-card {{ min-height:244px; border:1px solid #E9E2DA; border-radius:26px; padding:17px; background:rgba(255,255,255,.74); box-shadow:0 18px 38px rgba(17,24,39,.06); }}
        .day-card.today {{ border:2px solid #F6C453; background:linear-gradient(180deg, rgba(245,243,255,.94), rgba(255,247,237,.92)); }}
        .head {{ display:flex; justify-content:space-between; gap:10px; align-items:flex-start; padding-bottom:12px; border-bottom:1px solid #EFE7DE; }}
        .dow {{ font-size:13px; font-weight:900; color:#6B7280; letter-spacing:.4px; }}
        .num {{ font-size:31px; font-weight:950; color:#0B1026; line-height:1.05; margin-top:6px; }}
        .today-pill {{ display:inline-flex; align-items:center; padding:5px 9px; border-radius:999px; background:#FFF7ED; color:#92400E; border:1px solid #F6C453; font-size:11px; font-weight:950; }}
        .body {{ padding-top:13px; min-height:144px; display:flex; flex-direction:column; gap:9px; }}
        .free {{ color:#6B7280; font-size:15px; font-weight:800; margin-top:8px; }}
        .sub {{ color:#9CA3AF; font-size:12px; margin-top:4px; line-height:1.45; }}
        .task {{ border-left:5px solid #8B5CF6; background:rgba(255,255,255,.84); border-radius:18px; padding:10px 11px; box-shadow:0 10px 22px rgba(17,24,39,.055); overflow:hidden; }}
        .task.theory {{ background:linear-gradient(135deg, rgba(255,255,255,.92), rgba(245,243,255,.78)); }}
        .area {{ font-size:11px; font-weight:950; text-transform:uppercase; letter-spacing:.2px; white-space:normal; overflow-wrap:break-word; word-break:normal; }}
        .activity {{ margin-top:4px; font-size:13.5px; font-weight:900; color:#111827; line-height:1.25; white-space:normal; overflow-wrap:break-word; word-break:normal; }}
        .detail {{ margin-top:3px; font-size:11.5px; color:#6B7280; line-height:1.3; white-space:normal; overflow-wrap:break-word; word-break:normal; }}
        .status {{ margin-top:8px; display:inline-flex; width:max-content; max-width:100%; padding:5px 9px; border-radius:999px; background:#F5F3FF; color:#6D5DF6; font-size:11px; font-weight:950; }}
        .more {{ color:#6B7280; font-size:12px; font-weight:800; padding:4px 2px; }}
        @media (max-width: 900px) {{ .week-grid {{ grid-template-columns: repeat(7, 174px); min-width: 1310px; gap:14px; }} .day-card {{ min-height:252px; }} }}
    </style>
    </head>
    <body><div class="week-wrap"><div class="week-grid">{''.join(cards)}</div></div></body>
    </html>
    """
    components.html(component_html, height=330, scrolling=True)
    st.caption(f"Semana de {format_date_br(monday)} a {format_date_br(sunday)}")

def sidebar_menu():
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="brand-mark">SP</div>
                <div>
                    <div class="brand-title">StudyProgress</div>
                    <div class="brand-subtitle">Foco, provas e revisão</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if "menu_page" not in st.session_state or st.session_state["menu_page"] not in MENU_ITEMS:
            st.session_state["menu_page"] = "Início"

        for item in MENU_ITEMS:
            active = st.session_state.get("menu_page") == item
            label = item
            if active:
                st.markdown('<div class="nav-active">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{item}"):
                st.session_state["menu_page"] = item
                st.rerun()
            if active:
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="sidebar-profile">
                <b>Israel Rodrigues</b><br>
                ENEM • Fuvest • rotina
            </div>
            """,
            unsafe_allow_html=True,
        )
    return st.session_state.get("menu_page", "Início")


# ============================================================
# Páginas
# ============================================================
def page_inicio(all_data):
    show_topbar("Olá, Israel", "Painel do dia com teoria, provas, pendências e revisões.")
    cron = load_planejamento_provas()
    teoria = load_cronograma_teoria()
    teoria_hoje = theory_today(teoria)
    erros = load_erros()
    reviews_antigas = get_reviews(all_data)
    pend_antigas = get_pending(all_data)

    provas_hoje = cron[cron["Data_dt"] == today_ts()].copy() if not cron.empty else pd.DataFrame()
    pend_erros_abertos = erros[(erros["Status_Revisao"] != "Concluída")] if not erros.empty else pd.DataFrame()
    rev_erros_hoje = erros[(erros["Status_Revisao"] != "Concluída") & (erros["Proxima_Revisao_dt"] <= today_ts())] if not erros.empty else pd.DataFrame()
    revisoes_total = len(reviews_antigas) + len(rev_erros_hoje)
    pendencias_total = len(pend_antigas) + len(pend_erros_abertos)

    st.markdown(
        """
        <div class="hero">
            <h1>Painel de estudos</h1>
            <p>Seu cronograma de teoria, provas, pendências e revisões em um só lugar — com foco, clareza e um toque de brilho.</p>
            <div class="study-art">
                <div class="book-a"><div class="book-line" style="top:22px"></div><div class="book-line" style="top:42px"></div></div>
                <div class="book-b"><div class="book-line" style="top:24px"></div><div class="book-line" style="top:46px"></div></div>
                <div class="book-c"><div class="book-line" style="top:26px"></div><div class="book-line" style="top:50px"></div></div>
                <div class="pencil"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Teoria hoje", len(teoria_hoje), "matérias no cronograma")
    with c2: metric_card("Provas hoje", len(provas_hoje), "provas, simulados ou listas")
    with c3: metric_card("Pendências", pendencias_total, "itens em aberto")
    with c4: metric_card("Revisões", revisoes_total, "vencidas ou para hoje")

    st.write("")
    left, right = st.columns([1.05, 1.25])
    with left:
        with st.container(border=True):
            card_header("Cronograma de teoria hoje", "Clique para registrar o estudo. A matéria já vai preenchida; o conteúdo você coloca na hora.")
            if teoria_hoje.empty:
                st.info("Nenhuma matéria de teoria cadastrada para hoje.")
                quick_nav_button("Montar cronograma", "Planejamento", "home_add_teoria")
            else:
                for _, row in teoria_hoje.iterrows():
                    horario = f"{row.get('Horario_Inicio','')}–{row.get('Horario_Fim','')}".strip("–")
                    materia = row.get("Materia", "")
                    task_card(f"{horario} — {materia}", row.get("Observacoes", ""), subject_badge(materia), get_color_for_subject(materia))
                    quick_nav_button(
                        "Registrar estudo",
                        "Adicionar",
                        f"reg_teoria_{row.get('ID_Teoria','')}",
                        prefill={"Materia": materia, "Origem": "Cronograma_Teoria"},
                    )
                    st.write("")
        with st.container(border=True):
            card_header("Provas e simulados hoje", "Aparece tanto o cronograma pronto quanto provas cadastradas manualmente.")
            if provas_hoje.empty:
                st.info("Nenhuma prova ou simulado marcado para hoje.")
            else:
                for _, row in provas_hoje.iterrows():
                    area = row.get("Área", "")
                    meta = f"{row.get('Prova','')} • Questões {row.get('Questões','')}"
                    task_card(row.get("Atividade", ""), meta, status_badge(row.get("Status", "Pendente")), get_color_for_area(area))
                    quick_nav_button("Responder", "Simulados", f"start_prova_{row.get('ID_Atividade','')}")
                    st.write("")
    with right:
        with st.container(border=True):
            card_header("Planejamento da semana", "Resumo rápido de teoria, provas e simulados.")
            render_week_cards(cron, teoria=teoria)

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            card_header("Pendências", "Resumo organizado: antigas, provas pendentes e erros abertos.")
            proximas_provas = cron[cron["Status"].astype(str).str.lower().isin(["pendente", "fazendo"])] if not cron.empty else pd.DataFrame()
            proximas_provas = proximas_provas.sort_values("Data_dt").head(3) if not proximas_provas.empty else proximas_provas
            if proximas_provas.empty and pend_antigas.empty and pend_erros_abertos.empty:
                st.success("Nada pendente no momento.")
            else:
                for _, row in proximas_provas.iterrows():
                    task_card(f"{format_date_br(row['Data_dt'])} — {row['Atividade']}", row.get("Área", ""), status_badge(row.get("Status", "Pendente")), get_color_for_area(row.get("Área", "")))
                for _, row in pend_antigas.head(3).iterrows():
                    task_card(f"{row['Matéria']} — {row['Conteúdo']}", "pendência antiga", subject_badge(row['Matéria']), get_color_for_subject(row['Matéria']))
                if not pend_erros_abertos.empty:
                    st.caption(f"Banco de erros: {len(pend_erros_abertos)} questão(ões) ainda em revisão.")
            quick_nav_button("Ver pendências", "Pendências", "home_ver_pend")
    with right:
        with st.container(border=True):
            card_header("Revisões para hoje", "Inclui revisões antigas e erros de simulados.")
            if rev_erros_hoje.empty and reviews_antigas.empty:
                st.success("Nenhuma revisão vencida.")
            else:
                for _, row in rev_erros_hoje.head(3).iterrows():
                    task_card(f"Questão {row['Questão']} — {row['Prova']}", row.get("Tipo_Erro", "erro"), status_badge("Revisar hoje"), get_color_for_area(row.get("Área", "")))
                for _, row in reviews_antigas.head(3).iterrows():
                    task_card(f"{row['Matéria']} — {row['Conteúdo']}", "revisão antiga", subject_badge(row['Matéria']), get_color_for_subject(row['Matéria']))
            quick_nav_button("Ver revisões", "Pendências", "home_ver_rev")


def page_planejamento():
    show_topbar("Planejamento", "Um só lugar para cronograma de teoria, semana de provas e provas cadastradas.")
    teoria = load_cronograma_teoria()
    cron = load_planejamento_provas()
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    tab1, tab2, tab3 = st.tabs(["Semana", "Cronograma de teoria", "Provas cadastradas"])

    with tab1:
        st.markdown("### Visão semanal")
        selected = st.date_input("Escolha uma semana", value=today_date(), format="DD/MM/YYYY", key="planejamento_semana")
        render_week_cards(cron, selected, teoria=teoria)
        monday, sunday = week_bounds(selected)
        week_df = cron[(cron["Data_dt"] >= monday) & (cron["Data_dt"] <= sunday)].sort_values("Data_dt").copy() if not cron.empty else pd.DataFrame()
        theory_week_df = teoria[teoria["Status"].astype(str).str.lower().isin(["ativo", "", "pendente"])].copy() if not teoria.empty else pd.DataFrame()
        st.write("")
        left, right = st.columns([1.15, .85])
        with left:
            with st.container(border=True):
                card_header("Atividades da semana", "Provas, simulados, listas e teoria cadastrada.")
                if week_df.empty and theory_week_df.empty:
                    st.info("Sem atividades cadastradas nessa semana.")
                else:
                    for _, row in week_df.iterrows():
                        meta = f"{nice_day_name(row['Data_dt'])}, {format_date_br(row['Data_dt'])} • {row.get('Área','')} • Questões {row.get('Questões','')}"
                        task_card(row.get("Atividade", ""), meta, status_badge(row.get("Status", "Pendente")), get_color_for_area(row.get("Área", "")))
                    if not theory_week_df.empty:
                        st.caption("Cronograma de teoria fixo da semana")
                        for _, row in theory_week_df.head(10).iterrows():
                            materia = row.get("Materia", "")
                            horario = f"{row.get('Horario_Inicio','')}–{row.get('Horario_Fim','')}".strip("–")
                            meta = f"{row.get('Dia_Semana','')} • {horario}"
                            task_card(materia, meta, subject_badge(materia), get_color_for_subject(materia))
        with right:
            with st.container(border=True):
                card_header("Teoria de hoje", "Atalhos para registrar estudo.")
                tday = theory_today(teoria)
                if tday.empty:
                    st.info("Sem teoria cadastrada para hoje.")
                else:
                    for _, row in tday.iterrows():
                        task_card(f"{row.get('Horario_Inicio','')}–{row.get('Horario_Fim','')} — {row.get('Materia','')}", row.get("Observacoes", ""), subject_badge(row.get("Materia", "")), get_color_for_subject(row.get("Materia", "")))

    with tab2:
        st.markdown("### Rotina semanal de teoria")
        cols = st.columns(7)
        for i, dia in enumerate(dias):
            dia_df = teoria[teoria["Dia_Semana"].str.lower() == dia.lower()] if not teoria.empty else pd.DataFrame()
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"#### {dia[:3]}")
                    if dia_df.empty:
                        st.caption("Livre")
                    else:
                        for _, row in dia_df.iterrows():
                            materia = row.get("Materia", "")
                            status = str(row.get("Status", "Ativo"))
                            opacity = ".45" if status.lower() == "pausado" else "1"
                            st.markdown(f'<div style="opacity:{opacity};font-weight:900;color:{get_color_for_subject(materia)};">{row.get("Horario_Inicio","")}–{row.get("Horario_Fim","")}</div>', unsafe_allow_html=True)
                            st.write(materia)
        st.divider()
        left, right = st.columns([.95, 1.05])
        with left:
            with st.container(border=True):
                card_header("Adicionar matéria ao cronograma")
                with st.form("add_teoria"):
                    c1, c2 = st.columns(2)
                    with c1:
                        dia = st.selectbox("Dia da semana", dias)
                        materia = st.selectbox("Matéria", SUBJECTS)
                        status = st.selectbox("Status", ["Ativo", "Pausado"])
                    with c2:
                        inicio = st.text_input("Horário de início", value="19:00", placeholder="19:00")
                        fim = st.text_input("Horário de fim", value="20:00", placeholder="20:00")
                        obs = st.text_input("Observações", placeholder="opcional")
                    if st.form_submit_button("Adicionar"):
                        append_teoria(dia, inicio, fim, materia, status, obs)
                        st.success("Matéria adicionada ao cronograma.")
                        st.rerun()
        with right:
            with st.container(border=True):
                card_header("Editar ou excluir")
                if teoria.empty:
                    st.info("Nenhum item cadastrado ainda.")
                else:
                    options = {row["ID_Teoria"]: f"{row['Dia_Semana']} • {row['Horario_Inicio']}–{row['Horario_Fim']} • {row['Materia']}" for _, row in teoria.iterrows()}
                    selected_id = st.selectbox("Escolha o item", list(options), format_func=lambda rid: options[rid])
                    selected = teoria[teoria["ID_Teoria"] == selected_id].iloc[0]
                    with st.form(f"edit_teoria_{selected_id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            dia = st.selectbox("Dia", dias, index=dias.index(selected["Dia_Semana"]) if selected["Dia_Semana"] in dias else 0)
                            materia = st.selectbox("Matéria", SUBJECTS, index=SUBJECTS.index(selected["Materia"]) if selected["Materia"] in SUBJECTS else 0)
                            status = st.selectbox("Status", ["Ativo", "Pausado"], index=1 if selected["Status"].lower() == "pausado" else 0)
                        with c2:
                            inicio = st.text_input("Horário início", value=str(selected["Horario_Inicio"]))
                            fim = st.text_input("Horário fim", value=str(selected["Horario_Fim"]))
                            obs = st.text_input("Observações", value=str(selected.get("Observacoes", "")))
                        if st.form_submit_button("Salvar alterações"):
                            update_teoria(selected_id, dia, inicio, fim, materia, status, obs)
                            st.success("Cronograma atualizado.")
                            st.rerun()
                    confirm = st.checkbox("Confirmo que quero excluir este item.", key=f"conf_del_teo_{selected_id}")
                    if st.button("Excluir", disabled=not confirm, key=f"del_teo_{selected_id}"):
                        delete_teoria(selected_id)
                        st.rerun()

    with tab3:
        page_provas_cadastradas(internal=True)


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
        st.info("No celular, mantenha o modo lista ligado para as questões ficarem na ordem correta. No computador, você pode desligar para usar a grade compacta.")
        modo_lista = st.toggle("Modo celular / lista em ordem", value=True, key=f"modo_lista_{prova['ID_Prova']}")
        with st.form(f"respostas_{prova['ID_Prova']}"):
            respostas = {}
            if modo_lista:
                for bloco_inicio in range(1, total + 1, 15):
                    bloco_fim = min(bloco_inicio + 14, total)
                    st.markdown(f"#### Questões {bloco_inicio} a {bloco_fim}")
                    for q in range(bloco_inicio, bloco_fim + 1):
                        c1, c2 = st.columns([.30, .70])
                        with c1:
                            st.markdown(f"**Questão {q}**")
                        with c2:
                            respostas[q] = st.radio(
                                "Alternativa",
                                ALT_OPTIONS,
                                key=f"resp_{prova['ID_Prova']}_{q}",
                                horizontal=True,
                                label_visibility="collapsed",
                            )
            else:
                for linha_inicio in range(1, total + 1, 5):
                    cols = st.columns(5)
                    for offset, q in enumerate(range(linha_inicio, min(linha_inicio + 5, total + 1))):
                        with cols[offset]:
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
                resultado_auto, tipo if resultado_auto == "Errei" else "", conteudo, comentario, today_date().strftime("%d/%m/%Y"),
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
    show_topbar("Desempenho", "Leitura visual das horas, questões, acertos e erros.")
    correcoes = load_correcoes()
    erros = load_erros()

    total_horas = round(all_data["Tempo (h)"].sum(), 1) if not all_data.empty else 0
    total_questoes = int(all_data["Exercícios"].sum()) if not all_data.empty else 0
    acertos_reg = int(all_data["Acertos"].sum()) if not all_data.empty else 0
    taxa_reg = round(acertos_reg / total_questoes * 100) if total_questoes else 0
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Horas registradas", f"{total_horas}h", "tempo total")
    with c2: metric_card("Questões", total_questoes, "exercícios feitos")
    with c3: metric_card("Taxa de acertos", f"{taxa_reg}%", f"{acertos_reg}/{total_questoes}")
    with c4: metric_card("Erros no banco", len(erros), "questões para revisar")

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            card_header("Horas por data")
            evo = all_data.dropna(subset=["Data"]).groupby("Data", as_index=False)["Tempo (h)"].sum() if not all_data.empty else pd.DataFrame()
            if evo.empty:
                st.info("Sem dados suficientes.")
            elif px is not None:
                fig = px.area(evo, x="Data", y="Tempo (h)", markers=True)
                fig.update_traces(line_color="#8B5CF6", fillcolor="rgba(244,114,182,.18)", marker=dict(size=8, color="#F6C453", line=dict(width=2, color="#8B5CF6")))
                fig = apply_plot_style(fig, 350)
                fig.update_layout(xaxis_title="", yaxis_title="Horas")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(evo, x="Data", y="Tempo (h)", height=320)
    with right:
        with st.container(border=True):
            card_header("Horas por matéria")
            subj = all_data.groupby("Matéria", as_index=False)["Tempo (h)"].sum().sort_values("Tempo (h)", ascending=False) if not all_data.empty else pd.DataFrame()
            if subj.empty:
                st.info("Sem dados suficientes.")
            elif px is not None:
                colors = {m: SUBJECT_COLORS.get(m, "#64748B") for m in subj["Matéria"]}
                fig = px.bar(subj, x="Matéria", y="Tempo (h)", color="Matéria", color_discrete_map=colors)
                fig = apply_plot_style(fig, 350)
                fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Horas")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(subj, x="Matéria", y="Tempo (h)", height=320)

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            card_header("Acertos por matéria")
            if all_data.empty or int(all_data["Exercícios"].sum()) == 0:
                st.info("Sem exercícios registrados.")
            else:
                acc = all_data.groupby("Matéria", as_index=False).agg({"Exercícios":"sum", "Acertos":"sum"})
                acc = acc[acc["Exercícios"] > 0]
                acc["Taxa"] = (acc["Acertos"] / acc["Exercícios"] * 100).round(1)
                if px is not None and not acc.empty:
                    fig = px.bar(acc.sort_values("Taxa", ascending=False), x="Matéria", y="Taxa", color="Matéria", color_discrete_map={m: SUBJECT_COLORS.get(m, "#64748B") for m in acc["Matéria"]})
                    fig = apply_plot_style(fig, 350)
                    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Taxa (%)")
                    fig.add_hline(y=70, line_dash="dot", line_color="#F6C453", annotation_text="Meta 70%", annotation_position="top left")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(acc, use_container_width=True, hide_index=True)
    with right:
        with st.container(border=True):
            card_header("Erros por tipo")
            if erros.empty or erros["Tipo_Erro"].replace("", pd.NA).dropna().empty:
                st.info("Sem erros registrados.")
            else:
                grp = erros.groupby("Tipo_Erro", as_index=False).size().rename(columns={"size": "Total"})
                if px is not None:
                    fig = px.pie(grp, names="Tipo_Erro", values="Total", hole=.58, color_discrete_sequence=["#8B5CF6", "#F472B6", "#F6C453", "#14B8A6", "#FB7185", "#38BDF8"])
                    fig.update_traces(textposition="inside", textinfo="percent+label", marker=dict(line=dict(color="#FFF7ED", width=3)))
                    fig = apply_plot_style(fig, 350)
                    fig.update_layout(legend_title_text="", annotations=[dict(text="Erros", x=.5, y=.5, font_size=18, showarrow=False, font_color="#111827")])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(grp, x="Tipo_Erro", y="Total", height=320)


def page_adicionar():
    prefill = st.session_state.get("prefill_adicionar", {})
    show_topbar("Adicionar estudo", "Registre o que você estudou. Pode vir do cronograma de teoria ou ser manual.")
    if prefill:
        st.info(f"Matéria vinda do cronograma: {prefill.get('Materia', '')}. Preencha o conteúdo real que você estudou.")
        if st.button("Limpar preenchimento do cronograma"):
            st.session_state.pop("prefill_adicionar", None)
            st.rerun()

    default_subject = prefill.get("Materia", "Matemática") if isinstance(prefill, dict) else "Matemática"
    default_index = SUBJECTS.index(default_subject) if default_subject in SUBJECTS else 0

    with st.form("form_adicionar_estudo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            study_date = st.date_input("Data", value=today_date(), format="DD/MM/YYYY")
            subject = st.selectbox("Matéria", SUBJECTS, index=default_index)
            content = st.text_input("Conteúdo estudado", placeholder="Ex.: função afim, ecologia, repertório...")
        with c2:
            time_hours = st.number_input("Tempo (h)", min_value=0.0, max_value=12.0, step=0.25, format="%.2f")
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
                st.session_state.pop("prefill_adicionar", None)
                st.success("Estudo salvo com sucesso!")
                st.rerun()


def page_provas_cadastradas(internal=False):
    if not internal:
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
            data_prevista = st.date_input("Data prevista", value=today_date(), format="DD/MM/YYYY")
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
            edit_date = st.date_input("Data do estudo", value=selected["Data"].date() if pd.notna(selected["Data"]) else today_date(), format="DD/MM/YYYY")
            edit_subject = st.selectbox("Matéria", SUBJECTS, index=SUBJECTS.index(selected["Matéria"]) if selected["Matéria"] in SUBJECTS else 0)
            edit_content = st.text_input("Conteúdo estudado", value=selected["Conteúdo"])
        with e2:
            edit_time = st.number_input("Tempo (h)", min_value=0.0, max_value=12.0, value=float(selected["Tempo (h)"]), step=0.25, format="%.2f")
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
    msg = str(error)
    if "Quota exceeded" in msg or "Read requests" in msg or "429" in msg:
        st.error("O Google Planilhas bloqueou temporariamente por excesso de leituras. Aguarde 1 a 2 minutos e atualize a página. Esta versão reduz bastante as leituras para evitar esse erro.")
        with st.expander("Detalhes técnicos"):
            st.exception(error)
    else:
        st.error("Não consegui carregar os dados. Confira se a aba Registros possui todas as 12 colunas na ordem correta.")
        st.exception(error)
    st.stop()

page = sidebar_menu()

if page == "Início":
    page_inicio(all_data)
elif page == "Planejamento":
    page_planejamento()
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
else:
    page_subject(all_data, page)
