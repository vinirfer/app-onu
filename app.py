# ============================================================================
# app.py — Interface Streamlit para gestão de itens de transporte químico
# ============================================================================
# Aplicação web com duas páginas:
#   🔍 Consultar Itens  — pesquisa por nº do item ou descrição (+ edição)
#   ➕ Cadastrar Novo Item — formulário para inserir novos registos
#
# Base de dados: PostgreSQL (ligação via st.secrets["DATABASE_URL"])
# Uso: streamlit run app.py
# ============================================================================

import psycopg2
import psycopg2.extras
from contextlib import contextmanager

import streamlit as st

# ---------------------------------------------------------------------------
# Configuração da página Streamlit
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Controle ONU — Transporte de Produtos Químicos",
    page_icon="🧪",
    layout="wide",
)

ITENS_POR_PAGINA = 20  # quantidade de itens exibidos por defeito


# ---------------------------------------------------------------------------
# Ligação à base de dados PostgreSQL (via Streamlit Secrets)
# ---------------------------------------------------------------------------
@contextmanager
def get_connection():
    """Context manager para ligação segura à base de dados PostgreSQL.

    A URL de ligação é obtida de st.secrets['DATABASE_URL'], que deve ser
    configurada no ficheiro .streamlit/secrets.toml ou nas variáveis de
    ambiente do Streamlit Cloud.
    """
    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Criação automática da tabela (para BD nova/vazia)
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Cria a tabela 'itens' caso ainda não exista na base de dados.

    Executada a cada arranque da aplicação para garantir que a estrutura
    da base de dados está pronta, sem necessidade de scripts externos.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS itens (
                    id                SERIAL PRIMARY KEY,
                    n_item            TEXT,
                    descricao         TEXT,
                    grupo             TEXT,
                    ncm               TEXT,
                    volume            TEXT,
                    codigo_onu        TEXT,
                    classe_risco      TEXT,
                    grupo_embalagem   TEXT,
                    qtde_veiculo      TEXT,
                    qtde_interna      TEXT,
                    kit_epi           TEXT,
                    extintor_ate_1t   TEXT,
                    extintor_mais_1t  TEXT
                )
            """)
        conn.commit()


# Executar init_db ao arrancar a aplicação
init_db()


# ---------------------------------------------------------------------------
# Funções de acesso a dados (CRUD)
# ---------------------------------------------------------------------------
def obter_itens_recentes(limite: int = ITENS_POR_PAGINA) -> list[dict]:
    """Retorna os primeiros N itens ordenados por descrição."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM itens ORDER BY descricao LIMIT %s", (limite,))
            return [dict(row) for row in cur.fetchall()]


def pesquisar_itens(termo: str) -> list[dict]:
    """Pesquisa itens cujo n_item ou descrição contenham o termo (ILIKE).

    Usa ILIKE (case-insensitive) para uma pesquisa mais flexível no PostgreSQL.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            pattern = f"%{termo}%"
            cur.execute(
                """
                SELECT * FROM itens
                WHERE n_item   ILIKE %s
                   OR descricao ILIKE %s
                ORDER BY n_item
                """,
                (pattern, pattern),
            )
            return [dict(row) for row in cur.fetchall()]


def inserir_item(dados: dict) -> None:
    """Insere um novo registo na tabela 'itens'."""
    colunas = list(dados.keys())
    placeholders = ", ".join(["%s"] * len(colunas))
    sql = f"INSERT INTO itens ({', '.join(colunas)}) VALUES ({placeholders})"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, list(dados.values()))
        conn.commit()


def atualizar_item(item_id: int, dados: dict) -> None:
    """Atualiza um registo existente na tabela 'itens' pelo id."""
    set_clause = ", ".join([f"{col} = %s" for col in dados.keys()])
    sql = f"UPDATE itens SET {set_clause} WHERE id = %s"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, list(dados.values()) + [item_id])
        conn.commit()


# ---------------------------------------------------------------------------
# CSS personalizado para uma aparência mais moderna
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Cabeçalho principal */
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a73e8;
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #5f6368;
        margin-bottom: 1.5rem;
    }

    /* Estilização dos expanders de resultados */
    .stExpander {
        border: 1px solid #dadce0;
        border-radius: 12px;
        margin-bottom: 0.75rem;
    }

    /* Labels dos campos dentro do expander */
    .field-label {
        font-size: 0.75rem;
        color: #80868b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.1rem;
    }
    .field-value {
        font-size: 0.95rem;
        color: #202124;
        margin-bottom: 0.75rem;
        line-height: 1.4;
    }

    /* Divisor de secção dentro do expander */
    .section-title {
        font-weight: 600;
        font-size: 0.9rem;
        color: #1a73e8;
        border-bottom: 2px solid #e8eaed;
        padding-bottom: 0.3rem;
        margin-bottom: 0.75rem;
    }

    /* Badge de contagem de resultados */
    .result-badge {
        display: inline-block;
        background: #e8f0fe;
        color: #1a73e8;
        padding: 0.25rem 0.75rem;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Função auxiliar para renderizar um campo formatado
# ---------------------------------------------------------------------------
def campo(label: str, valor: str) -> None:
    """Exibe um par label/valor formatado."""
    st.markdown(f'<div class="field-label">{label}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="field-value">{valor if valor else "—"}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Diálogo de edição de item (modal)
# ---------------------------------------------------------------------------
@st.dialog("✏️ Editar Item", width="large")
def dialog_editar(item: dict):
    """Abre um modal com formulário pré-preenchido para editar um item."""

    st.markdown(f"**Editando:** {item['n_item']} — {item['descricao']}")
    st.divider()

    # --- Identificação ---
    st.subheader("📋 Identificação")
    col_a, col_b = st.columns(2)
    with col_a:
        e_n_item = st.text_input("Nº do Item *", value=item.get("n_item", ""), key="edit_n_item")
    with col_b:
        e_grupo = st.text_input("Grupo de Itens", value=item.get("grupo", ""), key="edit_grupo")

    e_descricao = st.text_input(
        "Descrição do Item *", value=item.get("descricao", ""), key="edit_descricao"
    )

    col_c, col_d = st.columns(2)
    with col_c:
        e_ncm = st.text_input("NCM", value=item.get("ncm", ""), key="edit_ncm")
    with col_d:
        e_volume = st.text_input("Volumes", value=item.get("volume", ""), key="edit_volume")

    st.divider()

    # --- Transporte ONU ---
    st.subheader("🚛 Transporte ONU")
    col_e, col_f, col_g = st.columns(3)
    with col_e:
        e_codigo_onu = st.text_input("Código ONU", value=item.get("codigo_onu", ""), key="edit_codigo_onu")
    with col_f:
        e_classe_risco = st.text_input("Classe de Risco", value=item.get("classe_risco", ""), key="edit_classe_risco")
    with col_g:
        e_grupo_embalagem = st.text_input("G.E.", value=item.get("grupo_embalagem", ""), key="edit_grupo_embalagem")

    col_h, col_i = st.columns(2)
    with col_h:
        e_qtde_veiculo = st.text_input("Qtde Limitada — Veículo", value=item.get("qtde_veiculo", ""), key="edit_qtde_veiculo")
    with col_i:
        e_qtde_interna = st.text_input("Qtde Limitada — Emb. Interna", value=item.get("qtde_interna", ""), key="edit_qtde_interna")

    st.divider()

    # --- Segurança ---
    st.subheader("🛡️ Segurança")
    e_kit_epi = st.text_area(
        "Kit EPI (NBR 9735)", value=item.get("kit_epi", ""), height=100, key="edit_kit_epi"
    )
    col_j, col_k = st.columns(2)
    with col_j:
        e_extintor_ate_1t = st.text_area(
            "Extintor de Incêndio (até 1 t)",
            value=item.get("extintor_ate_1t", ""),
            height=80,
            key="edit_extintor_ate_1t",
        )
    with col_k:
        e_extintor_mais_1t = st.text_area(
            "Extintor de Incêndio (> 1 t)",
            value=item.get("extintor_mais_1t", ""),
            height=80,
            key="edit_extintor_mais_1t",
        )

    st.divider()

    # Botão de guardar alterações
    if st.button("💾 Guardar Alterações", use_container_width=True, type="primary"):
        # Validação
        if not e_n_item.strip():
            st.error("⚠️ O campo **Nº do Item** é obrigatório.")
        elif not e_descricao.strip():
            st.error("⚠️ O campo **Descrição do Item** é obrigatório.")
        else:
            dados_atualizados = {
                "n_item":           e_n_item.strip(),
                "descricao":        e_descricao.strip(),
                "grupo":            e_grupo.strip(),
                "ncm":              e_ncm.strip(),
                "volume":           e_volume.strip(),
                "codigo_onu":       e_codigo_onu.strip(),
                "classe_risco":     e_classe_risco.strip(),
                "grupo_embalagem":  e_grupo_embalagem.strip(),
                "qtde_veiculo":     e_qtde_veiculo.strip(),
                "qtde_interna":     e_qtde_interna.strip(),
                "kit_epi":          e_kit_epi.strip(),
                "extintor_ate_1t":  e_extintor_ate_1t.strip(),
                "extintor_mais_1t": e_extintor_mais_1t.strip(),
            }
            try:
                atualizar_item(item["id"], dados_atualizados)
                st.success(f"✅ Item **{e_n_item.strip()}** atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao atualizar item: {e}")


# ---------------------------------------------------------------------------
# Função auxiliar para renderizar um item dentro de um expander
# ---------------------------------------------------------------------------
def renderizar_item(item: dict) -> None:
    """Renderiza os detalhes de um item dentro de um expander, com botão de edição."""
    titulo_expander = f"**{item['n_item']}** — {item['descricao']}"

    with st.expander(titulo_expander, expanded=False):
        # Botão de edição no topo do expander
        col_edit, col_spacer = st.columns([1, 5])
        with col_edit:
            if st.button("✏️ Editar", key=f"btn_edit_{item['id']}", type="secondary"):
                dialog_editar(item)

        col1, col2, col3 = st.columns(3)

        # ---- Coluna 1: Identificação ----
        with col1:
            st.markdown(
                '<div class="section-title">📋 Identificação</div>',
                unsafe_allow_html=True,
            )
            campo("Grupo de Itens", item.get("grupo", ""))
            campo("NCM", item.get("ncm", ""))
            campo("Volumes", item.get("volume", ""))

        # ---- Coluna 2: Transporte ONU ----
        with col2:
            st.markdown(
                '<div class="section-title">🚛 Transporte ONU</div>',
                unsafe_allow_html=True,
            )
            campo("Código ONU", item.get("codigo_onu", ""))
            campo("Classe de Risco", item.get("classe_risco", ""))
            campo("Grupo de Embalagem (G.E.)", item.get("grupo_embalagem", ""))
            campo("Qtde Limitada — Veículo", item.get("qtde_veiculo", ""))
            campo("Qtde Limitada — Emb. Interna", item.get("qtde_interna", ""))

        # ---- Coluna 3: Segurança ----
        with col3:
            st.markdown(
                '<div class="section-title">🛡️ Segurança</div>',
                unsafe_allow_html=True,
            )
            campo("Kit EPI (NBR 9735)", item.get("kit_epi", ""))
            campo("Extintor de Incêndio (até 1 t)", item.get("extintor_ate_1t", ""))
            campo("Extintor de Incêndio (> 1 t)", item.get("extintor_mais_1t", ""))


# ---------------------------------------------------------------------------
# Menu lateral de navegação
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://img.icons8.com/color/96/000000/chemical-plant.png",
        width=64,
    )
    st.markdown("### 🧪 Controle ONU")
    st.caption("Gestão de transporte de produtos químicos")
    st.divider()

    pagina = st.radio(
        "Navegação",
        options=["🔍 Consultar Itens", "➕ Cadastrar Novo Item"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("NBR 9735 • Regras ONU")


# =========================================================================
# PÁGINA A — Consultar Itens
# =========================================================================
if pagina == "🔍 Consultar Itens":
    st.markdown('<div class="main-header">🔍 Consultar Itens</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Pesquise por número do item ou parte da descrição</div>',
        unsafe_allow_html=True,
    )

    # Barra de pesquisa
    termo = st.text_input(
        "Pesquisar",
        placeholder="Digite o nº do item ou parte da descrição…",
        label_visibility="collapsed",
    )

    if termo:
        # ---- Modo pesquisa: filtra pelos termos ----
        resultados = pesquisar_itens(termo)

        if not resultados:
            st.warning("Nenhum item encontrado para a pesquisa informada.")
        else:
            st.markdown(
                f'<div class="result-badge">🔎 {len(resultados)} item(ns) encontrado(s)</div>',
                unsafe_allow_html=True,
            )
            for item in resultados:
                renderizar_item(item)
    else:
        # ---- Modo padrão: exibe os primeiros N itens ----
        itens_recentes = obter_itens_recentes(ITENS_POR_PAGINA)

        if not itens_recentes:
            st.info("📭 Nenhum item cadastrado na base de dados.")
        else:
            st.markdown(
                f'<div class="result-badge">📋 Exibindo os primeiros {len(itens_recentes)} itens — use a pesquisa para filtrar</div>',
                unsafe_allow_html=True,
            )
            for item in itens_recentes:
                renderizar_item(item)


# =========================================================================
# PÁGINA B — Cadastrar Novo Item
# =========================================================================
elif pagina == "➕ Cadastrar Novo Item":
    st.markdown('<div class="main-header">➕ Cadastrar Novo Item</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Preencha os dados abaixo para registar um novo item</div>',
        unsafe_allow_html=True,
    )

    with st.form("form_novo_item", clear_on_submit=True):
        st.subheader("📋 Identificação")
        col_a, col_b = st.columns(2)
        with col_a:
            f_n_item = st.text_input("Nº do Item *", placeholder="Ex.: 001-0001")
        with col_b:
            f_grupo = st.text_input("Grupo de Itens", placeholder="Ex.: Solventes")

        f_descricao = st.text_input("Descrição do Item *", placeholder="Descrição completa do produto")

        col_c, col_d = st.columns(2)
        with col_c:
            f_ncm = st.text_input("NCM", placeholder="Ex.: 2901.10.00")
        with col_d:
            f_volume = st.text_input("Volumes", placeholder="Ex.: Bombona 20L")

        st.divider()

        st.subheader("🚛 Transporte ONU")
        col_e, col_f, col_g = st.columns(3)
        with col_e:
            f_codigo_onu = st.text_input("Código ONU", placeholder="Ex.: 1993")
        with col_f:
            f_classe_risco = st.text_input("Classe de Risco", placeholder="Ex.: Classe 3")
        with col_g:
            f_grupo_embalagem = st.text_input("Grupo de Embalagem (G.E.)", placeholder="Ex.: III")

        col_h, col_i = st.columns(2)
        with col_h:
            f_qtde_veiculo = st.text_input("Qtde Limitada — Veículo", placeholder="Ex.: 1000 L")
        with col_i:
            f_qtde_interna = st.text_input("Qtde Limitada — Emb. Interna", placeholder="Ex.: 5 L")

        st.divider()

        st.subheader("🛡️ Segurança")
        f_kit_epi = st.text_area(
            "Kit EPI (NBR 9735)",
            placeholder="Descreva os EPIs necessários…",
            height=100,
        )
        col_j, col_k = st.columns(2)
        with col_j:
            f_extintor_ate_1t = st.text_area(
                "Extintor de Incêndio (até 1 t)",
                placeholder="Tipo e capacidade do extintor…",
                height=80,
            )
        with col_k:
            f_extintor_mais_1t = st.text_area(
                "Extintor de Incêndio (> 1 t)",
                placeholder="Tipo e capacidade do extintor…",
                height=80,
            )

        st.divider()

        # Botão de submissão
        submetido = st.form_submit_button("💾 Cadastrar Item", use_container_width=True)

        if submetido:
            # Validação dos campos obrigatórios
            if not f_n_item.strip():
                st.error("⚠️ O campo **Nº do Item** é obrigatório.")
            elif not f_descricao.strip():
                st.error("⚠️ O campo **Descrição do Item** é obrigatório.")
            else:
                dados = {
                    "n_item":           f_n_item.strip(),
                    "descricao":        f_descricao.strip(),
                    "grupo":            f_grupo.strip(),
                    "ncm":              f_ncm.strip(),
                    "volume":           f_volume.strip(),
                    "codigo_onu":       f_codigo_onu.strip(),
                    "classe_risco":     f_classe_risco.strip(),
                    "grupo_embalagem":  f_grupo_embalagem.strip(),
                    "qtde_veiculo":     f_qtde_veiculo.strip(),
                    "qtde_interna":     f_qtde_interna.strip(),
                    "kit_epi":          f_kit_epi.strip(),
                    "extintor_ate_1t":  f_extintor_ate_1t.strip(),
                    "extintor_mais_1t": f_extintor_mais_1t.strip(),
                }
                try:
                    inserir_item(dados)
                    st.success(
                        f"✅ Item **{f_n_item.strip()}** cadastrado com sucesso!"
                    )
                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar item: {e}")
