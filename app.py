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

# --- Carregar Secrets (Segredos) ---
# Tenta carregar os segredos do Streamlit
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_USER = st.secrets["GITHUB_USER"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
    GITHUB_FILE_PATH = st.secrets["GITHUB_FILE_PATH"]
    
    # URL da API do GitHub para o arquivo
    API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    
    # Headers para autenticação na API do GitHub
    HEADERS = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

except KeyError:
    st.error("Erro: Configure seus GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO e GITHUB_FILE_PATH nos Streamlit Secrets.")
    st.info("O erro anterior sobre WEBHOOK_URL foi removido, mas os segredos do GitHub ainda são necessários.")
    st.stop()


# --- Funções para Ler e Salvar Dados no GitHub ---

def carregar_dados_github():
    """Lê o arquivo data.json do GitHub."""
    try:
        req = requests.get(API_URL, headers=HEADERS)
        req.raise_for_status() # Lança erro se a requisição falhar
        
        data = req.json()
        
        # O conteúdo do arquivo vem em Base64
        content = base64.b64decode(data['content']).decode('utf-8')
        
        # Guarda o 'sha' para futuras atualizações
        st.session_state.github_sha = data['sha']
        
        if not content:
            return pd.DataFrame(columns=["Tarefa", "Início", "Previsão", "Progresso (%)", "Colaboradores"])
            
        # Converte o JSON para DataFrame do Pandas
        df = pd.DataFrame(json.loads(content))
        return df

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            # Se o arquivo não existe, retorna um DF vazio e limpa o SHA
            st.session_state.github_sha = None
            st.warning(f"Arquivo '{GITHUB_FILE_PATH}' não encontrado. Um novo será criado ao salvar.")
            return pd.DataFrame(columns=["Tarefa", "Início", "Previsão", "Progresso (%)", "Colaboradores"])
        else:
            st.error(f"Erro ao carregar dados do GitHub: {err}")
            return None
    except Exception as e:
        st.error(f"Erro inesperado ao carregar dados: {e}")
        return None

def salvar_dados_github(df):
    """Salva o DataFrame de volta no data.json do GitHub."""
    try:
        # Converte o DataFrame para string JSON
        data_json = df.to_json(orient='records')
        
        # Codifica para Base64
        data_b64 = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        
        # Prepara o payload para a API
        payload = {
            "message": "Atualização dos dados do Kanban via Streamlit",
            "content": data_b64,
            "committer": {"name": "Streamlit App", "email": "app@streamlit.io"}
        }
        
        # Se o arquivo já existe, precisamos enviar o SHA para atualizá-lo
        if 'github_sha' in st.session_state and st.session_state.github_sha:
            payload['sha'] = st.session_state.github_sha
            
        # Faz a requisição PUT para criar ou atualizar o arquivo
        req = requests.put(API_URL, headers=HEADERS, data=json.dumps(payload))
        req.raise_for_status()
        
        # Atualiza o SHA na session_state para a próxima gravação
        st.session_state.github_sha = req.json()['content']['sha']
        
        st.success("Dados salvos com sucesso no GitHub!")
        return True

    except Exception as e:
        st.error(f"Erro ao salvar dados no GitHub: {e}")
        return False

# --- Lógica Principal da Aplicação ---

# Título
st.title("📋 Meu Quadro Kanban/Tarefas")

# Carrega os dados na primeira vez ou quando recarrega
if 'data' not in st.session_state:
    st.session_state.data = carregar_dados_github()

if st.session_state.data is not None:
    
    st.header("Editor de Tarefas", divider="gray")

    # O "Coração" do App: O Editor de Dados
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
                format="%d%%", # Mostra o número com %
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
    if st.button("Salvar Alterações no GitHub", type="primary"):
        # Atualiza os dados na session_state antes de salvar
        st.session_state.data = edited_df
        salvar_dados_github(edited_df)

else:
    st.error("Não foi possível carregar os dados. Verifique os logs e os Secrets.")
