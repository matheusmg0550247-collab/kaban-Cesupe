import streamlit as st
import pandas as pd
import requests
import json
import base64

# --- Configuração da Página ---
st.set_page_config(
    page_title="Kanban Streamlit",
    page_icon="📋",
    layout="wide"
)

# --- Variáveis Globais de Configuração ---
API_URL = None
HEADERS = None

# --- Funções de Ajuda ---

def get_empty_df():
    """Retorna um DataFrame vazio com a estrutura do Kanban."""
    return pd.DataFrame(columns=["Tarefa", "Início", "Previsão", "Progresso (%)", "Colaboradores"])

# --- Verificação de Secrets e Configuração ---

# Tenta carregar os segredos e define o estado de configuração
if 'github_configured' not in st.session_state:
    try:
        # Tenta acessar todos os segredos necessários
        GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
        GITHUB_USER = st.secrets["GITHUB_USER"]
        GITHUB_REPO = st.secrets["GITHUB_REPO"]
        GITHUB_FILE_PATH = st.secrets["GITHUB_FILE_PATH"]
        
        # Se tudo deu certo, configura as variáveis globais
        API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        HEADERS = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        st.session_state.github_configured = True
        
    except KeyError:
        # Se faltar algum segredo, marca como não configurado
        st.session_state.github_configured = False


# --- Funções para Ler e Salvar Dados no GitHub ---
# Estas funções só serão chamadas se 'github_configured' for True

def carregar_dados_github():
    """Lê o arquivo data.json do GitHub."""
    if not API_URL or not HEADERS:
        st.error("Configuração da API do GitHub não encontrada.")
        return get_empty_df()
        
    try:
        req = requests.get(API_URL, headers=HEADERS)
        req.raise_for_status() # Lança erro se a requisição falhar
        
        data = req.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        st.session_state.github_sha = data['sha'] # Guarda o 'sha' para atualizações
        
        if not content:
            return get_empty_df()
            
        df = pd.DataFrame(json.loads(content))
        return df

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            st.session_state.github_sha = None
            st.warning(f"Arquivo de dados não encontrado no GitHub. Um novo será criado ao salvar.")
            return get_empty_df()
        else:
            st.error(f"Erro HTTP ao carregar dados do GitHub: {err}")
            return get_empty_df()
    except Exception as e:
        st.error(f"Erro inesperado ao carregar dados: {e}")
        return get_empty_df()

def salvar_dados_github(df):
    """Salva o DataFrame de volta no data.json do GitHub."""
    if not API_URL or not HEADERS:
        st.error("Configuração da API do GitHub não encontrada. Não é possível salvar.")
        return False
        
    try:
        data_json = df.to_json(orient='records')
        data_b64 = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": "Atualização dos dados do Kanban via Streamlit",
            "content": data_b64,
            "committer": {"name": "Streamlit App", "email": "app@streamlit.io"}
        }
        
        if 'github_sha' in st.session_state and st.session_state.github_sha:
            payload['sha'] = st.session_state.github_sha
            
        req = requests.put(API_URL, headers=HEADERS, data=json.dumps(payload))
        req.raise_for_status()
        
        st.session_state.github_sha = req.json()['content']['sha']
        st.success("Dados salvos com sucesso no GitHub!")
        return True

    except Exception as e:
        st.error(f"Erro ao salvar dados no GitHub: {e}")
        return False

# --- Lógica Principal da Aplicação ---

st.title("📋 Meu Quadro Kanban/Tarefas")

# Exibe o aviso se os segredos não estiverem configurados
if not st.session_state.github_configured:
    st.warning("""
        **Modo de Demonstração (Somente Leitura)**
        
        A conexão com o GitHub não foi configurada. 
        Você pode visualizar e editar os dados na tabela, mas o botão **'Salvar' está desabilitado**.
        
        Para habilitar o salvamento, configure os seguintes Streamlit Secrets:
        `GITHUB_TOKEN`, `GITHUB_USER`, `GITHUB_REPO`, `GITHUB_FILE_PATH`
    """)

# Carrega os dados (do GitHub se configurado, ou um DF vazio se não)
if 'data' not in st.session_state:
    if st.session_state.github_configured:
        st.session_state.data = carregar_dados_github()
    else:
        st.session_state.data = get_empty_df()

# --- Interface do Editor ---

st.header("Editor de Tarefas", divider="gray")

# O st.data_editor armazena suas edições em 'edited_df'
edited_df = st.data_editor(
    st.session_state.data,
    num_rows="dynamic", # Permite adicionar e deletar linhas
    use_container_width=True,
    column_config={
        "Tarefa": st.column_config.TextColumn(
            "Tarefa", required=True, help="Descrição da atividade."
        ),
        "Início": st.column_config.DateColumn(
            "Data de Início", format="DD/MM/YYYY"
        ),
        "Previsão": st.column_config.DateColumn(
            "Previsão de Término", format="DD/MM/YYYY"
        ),
        "Progresso (%)": st.column_config.ProgressColumn(
            "Progresso (%)",
            help="Ajuste manual da % concluída",
            format="%d%%",
            min_value=0,
            max_value=100,
        ),
        "Colaboradores": st.column_config.ListColumn(
            "Colaboradores",
            help="Nomes dos envolvidos (pressione Enter após cada nome)",
        )
    },
    height=400
)

# Botão de Salvar
# Fica desabilitado se 'github_configured' for False
if st.button("Salvar Alterações no GitHub", type="primary", disabled=not st.session_state.github_configured):
    # Atualiza os dados na session_state antes de salvar
    st.session_state.data = edited_df
    salvar_dados_github(edited_df)
