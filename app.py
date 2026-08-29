import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import pandas as pd
import os
from PIL import Image
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
# Verifica se o escudo do time existe para usá-lo como ícone oficial (favicon)
icone_pagina = "meu_time.png" if os.path.exists("meu_time.png") else "⚽"

st.set_page_config(
    page_title="União Itapura F.C. - Gestão Oficial",
    page_icon=icone_pagina,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXÃO COM O SUPABASE (POSTGRESQL) ---
SUPABASE_URL = "postgresql://postgres.kydwkgijbukwfgrzzmvv:Uni%C3%A3o_Itapura*2026@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

def conectar_banco():
    return psycopg2.connect(SUPABASE_URL)

def iniciar_banco():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Tabela de Usuários
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, 
        usuario TEXT UNIQUE, 
        senha TEXT, 
        perfil TEXT)''')
    
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (%s, %s, %s)", ("admin", "admin123", "Admin"))
        cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (%s, %s, %s)", ("diretor", "diretor123", "Diretor"))

    # Tabela de Dados Institucionais do Clube
    cursor.execute('''CREATE TABLE IF NOT EXISTS clube_info (
        id SERIAL PRIMARY KEY, 
        nome_clube TEXT, cnpj TEXT, endereco TEXT, telefone TEXT, 
        presidente TEXT, diretoria TEXT, assessor TEXT, 
        data_criacao TEXT, historia TEXT)''')
    
    cursor.execute("SELECT COUNT(*) FROM clube_info")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''INSERT INTO clube_info (nome_clube, cnpj, endereco, telefone, presidente, diretoria, assessor, data_criacao, historia) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                       ("União Itapura F.C.", "00.000.000/0001-00", "Itapura, Santo Amaro, São Paulo - SP", "(11) 90000-0000", 
                        "Deivid Teixeira", "Diretoria Executiva União", "Assessoria de Comunicação", "20/01/2026", 
                        "Clube amador tradicional focado na união da comunidade, esporte e lazer."))

    # Tabelas de Apoio do Admin
    cursor.execute('''CREATE TABLE IF NOT EXISTS patrocinadores (id SERIAL PRIMARY KEY, nome TEXT, contato TEXT, tipo_apoio TEXT, valor_estimado REAL, telefone TEXT, email TEXT, endereco TEXT, observacao TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS doadores (id SERIAL PRIMARY KEY, nome TEXT, contato TEXT, observacao TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS campos (id SERIAL PRIMARY KEY, nome_local TEXT, endereco TEXT, responsavel TEXT, contato TEXT)''')
    
    # Tabela de Atletas / Membros
    cursor.execute('''CREATE TABLE IF NOT EXISTS atletas (
        id SERIAL PRIMARY KEY, nome TEXT, documentos TEXT, 
        nascimento TEXT, posicao TEXT, telefone TEXT, endereco TEXT, 
        status TEXT DEFAULT 'Ativo', cargo TEXT, nome_mae TEXT, foto_path TEXT, 
        criado_por TEXT, data_registro TEXT)''')
    
    # Tabela Financeiro
    cursor.execute('''CREATE TABLE IF NOT EXISTS financeiro (
        id SERIAL PRIMARY KEY, valor REAL, data TEXT, 
        tipo TEXT, referencia TEXT, status_pgto TEXT, observacao TEXT, 
        atleta_id INTEGER, criado_por TEXT, data_registro TEXT)''')
    
    # Tabela de Jogos
    cursor.execute('''CREATE TABLE IF NOT EXISTS jogos (
        id SERIAL PRIMARY KEY, adversario TEXT, 
        placar_uniao INTEGER, placar_adv INTEGER, data TEXT,
        local TEXT, penaltis TEXT, observacao TEXT, resultado TEXT, 
        criado_por TEXT, data_registro TEXT)''')
    
    # Tabela de Presenças
    cursor.execute('''CREATE TABLE IF NOT EXISTS presencas (
        id SERIAL PRIMARY KEY, atleta_id INTEGER, 
        jogo_id INTEGER, presenca INTEGER DEFAULT 0)''')
    
    # Tabela de Scouts
    cursor.execute('''CREATE TABLE IF NOT EXISTS scouts (
        id SERIAL PRIMARY KEY, atleta_id INTEGER, 
        jogo_id INTEGER, gols INTEGER, assistencias INTEGER, data TEXT, 
        criado_por TEXT, data_registro TEXT)''')

    conn.commit()
    cursor.close()
    conn.close()

iniciar_banco()

# --- CLASSE PDF RELATÓRIO ---
class PDFRelatorio(FPDF):
    def __init__(self, titulo_relatorio=""):
        super().__init__()
        self.titulo_relatorio = titulo_relatorio

    def header(self):
        # LOGO DO TIME
        if os.path.exists("meu_time.png"):
            self.image("meu_time.png", 10, 8, 12)

        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, "GESTÃO TIME DE VÁRZEA - UNIÃO ITAPURA F.C.", 0, 1, "C")
        self.set_font("Helvetica", "B", 8)
        self.cell(0, 5, "DTBRAS SOLUÇÕES TECNOLÓGICAS - CNPJ: 32.608.676/0001-59", 0, 1, "C")
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, "Programa desenvolvido por DTBRAS Soluções Tecnológicas - CNPJ: 32.608.676/0001-59 | Página " + str(self.page_no()), 0, 0, "C")

# --- CONTROLE DE SESSÃO / LOGIN & TIMEOUT (5 Minutos) ---
TEMPO_LIMITE_INATIVIDADE = timedelta(minutes=5)

if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = ""
    st.session_state.perfil = ""
    st.session_state.ultima_atividade = datetime.now()

# Verifica se estourou o tempo de inatividade
if st.session_state.logado:
    tempo_inativo = datetime.now() - st.session_state.ultima_atividade
    if tempo_inativo > TEMPO_LIMITE_INATIVIDADE:
        st.session_state.logado = False
        st.session_state.usuario = ""
        st.session_state.perfil = ""
        st.warning("⚠️ Sessão expirada por inatividade (mais de 5 minutos sem uso). Faça o login novamente.")
        st.rerun()
    else:
        # Atualiza o cronômetro a cada ação do usuário
        st.session_state.ultima_atividade = datetime.now()

# --- CONTROLE DE EXIBIÇÃO APÓS O LOGIN / TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("⚽ GESTÃO UNIÃO ITAPURA F.C.")
    aba_entrar, aba_recuperar = st.tabs(["🔑 Entrar no Sistema", "🔄 Recuperar Senha"])
    
    with aba_entrar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Acesso Restrito")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar", use_container_width=True)
                
                if submit_login:
                    conn_l = conectar_banco()
                    c_l = conn_l.cursor()
                    c_l.execute("SELECT senha, perfil FROM usuarios WHERE usuario = %s", (usuario_input,))
                    res = c_l.fetchone()
                    c_l.close()
                    conn_l.close()
                    
                    if res and res[0] == senha_input:
                        st.session_state.logado = True
                        st.session_state.usuario = usuario_input
                        st.session_state.perfil = res[1]
                        st.session_state.ultima_atividade = datetime.now()
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")

    with aba_recuperar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Recuperação de Senha")
            st.write("Insira seu nome de usuário para cadastrar uma nova senha de acesso.")
            with st.form("form_recuperar"):
                user_rec = st.text_input("Nome de Usuário")
                nova_senha_rec = st.text_input("Nova Senha Desejada", type="password")
                submit_rec = st.form_submit_button("Redefinir Senha", use_container_width=True)
                
                if submit_rec:
                    if user_rec and nova_senha_rec:
                        conn_r = conectar_banco()
                        c_r = conn_r.cursor()
                        c_r.execute("SELECT id FROM usuarios WHERE usuario = %s", (user_rec,))
                        existe = c_r.fetchone()
                        if existe:
                            c_r.execute("UPDATE usuarios SET senha = %s WHERE usuario = %s", (nova_senha_rec, user_rec))
                            conn_r.commit()
                            st.success("Senha redefinida com sucesso! Volte na aba 'Entrar no Sistema'.")
                        else:
                            st.error("Usuário não encontrado no sistema.")
                        c_r.close()
                        conn_r.close()
                    else:
                        st.warning("Preencha todos os campos.")
                        
    st.stop()  # Para a execução aqui se não estiver logado, evitando ler o resto do app

# --- CONTROLE DE EXIBIÇÃO APÓS O LOGIN / TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("⚽ GESTÃO UNIÃO ITAPURA F.C.")
    aba_entrar, aba_recuperar = st.tabs(["🔑 Entrar no Sistema", "🔄 Recuperar Senha"])
    
    with aba_entrar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Acesso Restrito")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar", use_container_width=True)
                
                if submit_login:
                    conn_l = conectar_banco()
                    c_l = conn_l.cursor()
                    c_l.execute("SELECT senha, perfil FROM usuarios WHERE usuario = %s", (usuario_input,))
                    res = c_l.fetchone()
                    c_l.close()
                    conn_l.close()
                    
                    if res and res[0] == senha_input:
                        st.session_state.logado = True
                        st.session_state.usuario = usuario_input
                        st.session_state.perfil = res[1]
                        st.session_state.ultima_atividade = datetime.now()
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")

    with aba_recuperar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Recuperação de Senha")
            st.write("Insira seu nome de usuário para cadastrar uma nova senha de acesso.")
            with st.form("form_recuperar"):
                user_rec = st.text_input("Nome de Usuário")
                nova_senha_rec = st.text_input("Nova Senha Desejada", type="password")
                submit_rec = st.form_submit_button("Redefinir Senha", use_container_width=True)
                
                if submit_rec:
                    if user_rec and nova_senha_rec:
                        conn_r = conectar_banco()
                        c_r = conn_r.cursor()
                        c_r.execute("SELECT id FROM usuarios WHERE usuario = %s", (user_rec,))
                        existe = c_r.fetchone()
                        if existe:
                            c_r.execute("UPDATE usuarios SET senha = %s WHERE usuario = %s", (nova_senha_rec, user_rec))
                            conn_r.commit()
                            st.success("Senha redefinida com sucesso! Volte na aba 'Entrar no Sistema'.")
                        else:
                            st.error("Usuário não encontrado no sistema.")
                        c_r.close()
                        conn_r.close()
                    else:
                        st.warning("Preencha todos os campos.")
                        
    st.stop()  # Para a execução aqui se não estiver logado

# --- CONEXÃO GLOBAL PÓS-LOGIN ---
conn = conectar_banco()

# --- MENU LATERAL DO SISTEMA (Só carrega se estiver logado) ---
st.sidebar.image("meu_time.png" if os.path.exists("meu_time.png") else "⚽", width=100)
st.sidebar.markdown(f"### Olá, {st.session_state.usuario}!")
st.sidebar.markdown(f"**Perfil:** {st.session_state.perfil}")

if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.logado = False
    st.session_state.usuario = ""
    st.session_state.perfil = ""
    st.rerun()

st.sidebar.divider()

menu = st.sidebar.radio(
    "Navegação Principal",
    ["📊 Dashboard", "👥 Membros", "💰 Financeiro", "⚽ Jogos", "🏆 Scout", "📄 Relatórios PDF", "⚙️ Painel Admin"]
)

st.sidebar.divider()

    # ==========================================
    # ⚙️ PAINEL ADMIN
    # ==========================================
if menu == "⚙️ Painel Admin":
        st.title("⚙️ Painel do Administrador - Gestão do Clube")
        
        tab_adm1, tab_adm2, tab_adm3, tab_adm4, tab_adm5, tab_adm6 = st.tabs([
            "🛡️ Dados do Clube", "👥 Acessos", "🤝 Patrocinadores", "🎁 Doadores", "🏟️ Campos Conveniados", "💾 Backup & Dados"
        ])
        
        with tab_adm1:
            st.subheader("Configurações Oficiais e Identidade do Clube")
            c_info = pd.read_sql("SELECT * FROM clube_info WHERE id=1", conn).iloc[0]
            
            with st.form("form_clube_info"):
                nc = st.text_input("Nome Oficial do Clube", value=c_info['nome_clube'])
                cnpj = st.text_input("CNPJ", value=c_info['cnpj'])
                end = st.text_input("Endereço / Sede", value=c_info['endereco'])
                tel = st.text_input("Telefone de Contato", value=c_info['telefone'])
                pres = st.text_input("Nome do Presidente", value=c_info['presidente'])
                dir_t = st.text_input("Diretoria Responsável", value=c_info['diretoria'])
                ass = st.text_input("Assessor de Imprensa / Comunicação", value=c_info['assessor'])
                dt_c = st.text_input("Data de Criação / Fundação", value=c_info['data_criacao'])
                hist = st.text_area("História do Clube", value=c_info['historia'])
                
                if st.form_submit_button("💾 Salvar Dados do Clube", use_container_width=True):
                    c = conn.cursor()
                    c.execute("""UPDATE clube_info SET nome_clube=%s, cnpj=%s, endereco=%s, telefone=%s, presidente=%s, diretoria=%s, assessor=%s, data_criacao=%s, historia=%s WHERE id=1""",
                              (nc, cnpj, end, tel, pres, dir_t, ass, dt_c, hist))
                    conn.commit()
                    c.close()
                    st.success("Dados institucionais atualizados com sucesso!")
                    st.rerun()

        with tab_adm2:
            st.subheader("Gerenciar Usuários e Acessos do Sistema")
            if 'edit_user_id' not in st.session_state:
                st.session_state.edit_user_id = None

            df_users_all = pd.read_sql("SELECT id, usuario, perfil FROM usuarios ORDER BY usuario ASC", conn)
            with st.expander("🔍 Pesquisar / Selecionar Usuários", expanded=True):
                termo_u = st.text_input("Pesquisar usuário por nome:")
                if not df_users_all.empty:
                    lista_opcoes_users = {f"ID {row['id']} - {row['usuario']} ({row['perfil']})": row['id'] for _, row in df_users_all.iterrows()}
                    user_selecionado_str = st.selectbox("Selecione o usuário:", ["-- Novo Usuário --"] + list(lista_opcoes_users.keys()))
                    
                    col_u1, col_u2, col_u3 = st.columns(3)
                    if col_u1.button("✏️ Carregar Usuário p/ Editar", key="btn_ed_user"):
                        if user_selecionado_str != "-- Novo Usuário --":
                            st.session_state.edit_user_id = lista_opcoes_users[user_selecionado_str]
                            st.rerun()
                    if col_u2.button("🧹 Limpar Seleção", key="btn_cl_user"):
                        st.session_state.edit_user_id = None
                        st.rerun()
                    if col_u3.button("🗑️ Excluir Usuário", key="btn_del_user"):
                        if user_selecionado_str != "-- Novo Usuário --":
                            id_u_exc = lista_opcoes_users[user_selecionado_str]
                            if id_u_exc == 1:
                                st.error("Não é permitido excluir o usuário Administrador principal!")
                            else:
                                c = conn.cursor()
                                c.execute("DELETE FROM usuarios WHERE id = %s", (id_u_exc,))
                                conn.commit()
                                c.close()
                                st.session_state.edit_user_id = None
                                st.success("Usuário excluído com sucesso!")
                                st.rerun()

            user_atual = {"usuario": "", "senha": "", "perfil": "Diretor"}
            if st.session_state.edit_user_id:
                c = conn.cursor()
                c.execute("SELECT usuario, senha, perfil FROM usuarios WHERE id = %s", (st.session_state.edit_user_id,))
                res_u = c.fetchone()
                c.close()
                if res_u:
                    user_atual = {"usuario": res_u[0], "senha": res_u[1], "perfil": res_u[2]}
                    st.info(f"Editando Usuário ID: {st.session_state.edit_user_id} - {res_u[0]}")

            with st.form("form_cad_usuario"):
                novo_user = st.text_input("Nome de Usuário", value=user_atual["usuario"])
                nova_senha = st.text_input("Senha", type="password", value=user_atual["senha"])
                perfis_lista = ["Admin", "Diretor"]
                idx_perfil = perfis_lista.index(user_atual["perfil"]) if user_atual["perfil"] in perfis_lista else 1
                novo_perfil = st.selectbox("Perfil de Acesso", perfis_lista, index=idx_perfil)
                
                if st.form_submit_button("💾 Salvar / Atualizar Usuário", use_container_width=True):
                    if novo_user and nova_senha:
                        try:
                            c = conn.cursor()
                            if st.session_state.edit_user_id:
                                c.execute("UPDATE usuarios SET usuario=%s, senha=%s, perfil=%s WHERE id=%s", 
                                          (novo_user, nova_senha, novo_perfil, st.session_state.edit_user_id))
                                st.success(f"Usuário '{novo_user}' atualizado com sucesso!")
                            else:
                                c.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (%s, %s, %s)", (novo_user, nova_senha, novo_perfil))
                                st.success(f"Usuário '{novo_user}' cadastrado com sucesso!")
                            conn.commit()
                            c.close()
                            st.session_state.edit_user_id = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar usuário: {e}")
                    else:
                        st.warning("Preencha todos os campos.")
            
            st.divider()
            st.subheader("Lista de Usuários Cadastrados")
            query_u = "SELECT id, usuario, perfil FROM usuarios"
            if termo_u:
                query_u += f" WHERE usuario ILIKE '%{termo_u}%'"
            query_u += " ORDER BY id ASC"
            st.dataframe(pd.read_sql(query_u, conn), use_container_width=True, hide_index=True)

        with tab_adm3:
            st.subheader("Gerenciar Patrocinadores")
            if 'edit_pat_id' not in st.session_state:
                st.session_state.edit_pat_id = None

            try:
                df_pat_all = pd.read_sql("SELECT id, nome, tipo_apoio FROM patrocinadores ORDER BY nome ASC", conn)
            except:
                df_pat_all = pd.DataFrame()
            
            with st.expander("🔍 Pesquisar / Selecionar Patrocinador", expanded=True):
                termo_p = st.text_input("Pesquisar patrocinador por nome:")
                if not df_pat_all.empty:
                    lista_opcoes_pat = {f"ID {row['id']} - {row['nome']} ({row['tipo_apoio']})": row['id'] for _, row in df_pat_all.iterrows()}
                    pat_selecionado_str = st.selectbox("Selecione o patrocinador:", ["-- Novo Patrocinador --"] + list(lista_opcoes_pat.keys()))
                    
                    col_p1, col_p2, col_p3 = st.columns(3)
                    if col_p1.button("✏️ Carregar Patrocinador p/ Editar", key="btn_ed_pat"):
                        if pat_selecionado_str != "-- Novo Patrocinador --":
                            st.session_state.edit_pat_id = lista_opcoes_pat[pat_selecionado_str]
                            st.rerun()
                    if col_p2.button("🧹 Limpar Seleção", key="btn_cl_pat"):
                        st.session_state.edit_pat_id = None
                        st.rerun()
                    if col_p3.button("🗑️ Excluir Patrocinador", key="btn_del_pat"):
                        if pat_selecionado_str != "-- Novo Patrocinador --":
                            id_p_exc = lista_opcoes_pat[pat_selecionado_str]
                            c = conn.cursor()
                            c.execute("DELETE FROM patrocinadores WHERE id = %s", (id_p_exc,))
                            conn.commit()
                            c.close()
                            st.session_state.edit_pat_id = None
                            st.success("Patrocinador excluído com sucesso!")
                            st.rerun()
                else:
                    st.info("⚠️ Nenhum patrocinador cadastrado ainda. Preencha o formulário abaixo.")

            pat_atual = {"nome": "", "telefone": "", "email": "", "endereco": "", "tipo_apoio": "", "valor_estimado": 0.0, "observacao": ""}
            if st.session_state.edit_pat_id:
                c = conn.cursor()
                try:
                    c.execute("SELECT nome, telefone, email, endereco, tipo_apoio, valor_estimado, observacao FROM patrocinadores WHERE id = %s", (st.session_state.edit_pat_id,))
                    res_p = c.fetchone()
                    c.close()
                    if res_p:
                        pat_atual = {"nome": res_p[0], "telefone": res_p[1], "email": res_p[2], "endereco": res_p[3], "tipo_apoio": res_p[4], "valor_estimado": res_p[5] or 0.0, "observacao": res_p[6]}
                        st.info(f"Editando Patrocinador ID: {st.session_state.edit_pat_id} - {res_p[0]}")
                except:
                    pass

            with st.form("form_patrocinador"):
                p_nome = st.text_input("Nome / Empresa Patrocinadora", value=pat_atual["nome"])
                
                c1, c2 = st.columns(2)
                p_tel = c1.text_input("Telefone", value=pat_atual["telefone"])
                p_email = c2.text_input("E-mail", value=pat_atual["email"])
                
                p_end = st.text_input("Endereço", value=pat_atual["endereco"])
                
                c3, c4 = st.columns(2)
                p_tipo = c3.text_input("Tipo de Apoio", value=pat_atual["tipo_apoio"])
                p_val = c4.number_input("Valor Estimado Mensal/Total (R$)", value=float(pat_atual["valor_estimado"]), format="%.2f")
                
                p_obs = st.text_area("Observação e Detalhes do Acordo", value=pat_atual["observacao"])
                
                if st.form_submit_button("💾 Salvar / Atualizar Patrocinador", use_container_width=True):
                    if p_nome:
                        c = conn.cursor()
                        if st.session_state.edit_pat_id:
                            c.execute("UPDATE patrocinadores SET nome=%s, telefone=%s, email=%s, endereco=%s, tipo_apoio=%s, valor_estimado=%s, observacao=%s WHERE id=%s", 
                                      (p_nome, p_tel, p_email, p_end, p_tipo, p_val, p_obs, st.session_state.edit_pat_id))
                            st.success("Patrocinador atualizado com sucesso!")
                        else:
                            c.execute("INSERT INTO patrocinadores (nome, telefone, email, endereco, tipo_apoio, valor_estimado, observacao) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                      (p_nome, p_tel, p_email, p_end, p_tipo, p_val, p_obs))
                            st.success("Patrocinador cadastrado com sucesso!")
                        conn.commit()
                        c.close()
                        st.session_state.edit_pat_id = None
                        st.rerun()
                    else:
                        st.warning("O nome do patrocinador é obrigatório.")
            
            st.divider()
            st.subheader("Lista de Patrocinadores")
            try:
                query_p = "SELECT id, nome, telefone, email, endereco, tipo_apoio, valor_estimado, observacao FROM patrocinadores"
                if termo_p:
                    query_p += f" WHERE nome ILIKE '%{termo_p}%'"
                st.dataframe(pd.read_sql(query_p, conn), use_container_width=True, hide_index=True)
            except:
                st.info("Tabela em atualização...")

        with tab_adm4:
            st.subheader("Gerenciar Doadores")
            if 'edit_doa_id' not in st.session_state:
                st.session_state.edit_doa_id = None

            df_doa_all = pd.read_sql("SELECT id, nome FROM doadores ORDER BY nome ASC", conn)
            with st.expander("🔍 Pesquisar / Selecionar Doador", expanded=True):
                termo_d = st.text_input("Pesquisar doador por nome:")
                if not df_doa_all.empty:
                    lista_opcoes_doa = {f"ID {row['id']} - {row['nome']}": row['id'] for _, row in df_doa_all.iterrows()}
                    doa_selecionado_str = st.selectbox("Selecione o doador:", ["-- Novo Doador --"] + list(lista_opcoes_doa.keys()))
                    
                    col_d1, col_d2, col_d3 = st.columns(3)
                    if col_d1.button("✏️ Carregar Doador p/ Editar", key="btn_ed_doa"):
                        if doa_selecionado_str != "-- Novo Doador --":
                            st.session_state.edit_doa_id = lista_opcoes_doa[doa_selecionado_str]
                            st.rerun()
                    if col_d2.button("🧹 Limpar Seleção", key="btn_cl_doa"):
                        st.session_state.edit_doa_id = None
                        st.rerun()
                    if col_d3.button("🗑️ Excluir Doador", key="btn_del_doa"):
                        if doa_selecionado_str != "-- Novo Doador --":
                            id_d_exc = lista_opcoes_doa[doa_selecionado_str]
                            c = conn.cursor()
                            c.execute("DELETE FROM doadores WHERE id = %s", (id_d_exc,))
                            conn.commit()
                            c.close()
                            st.session_state.edit_doa_id = None
                            st.success("Doador excluído com sucesso!")
                            st.rerun()

            doa_atual = {"nome": "", "contato": "", "observacao": ""}
            if st.session_state.edit_doa_id:
                c = conn.cursor()
                c.execute("SELECT nome, contato, observacao FROM doadores WHERE id = %s", (st.session_state.edit_doa_id,))
                res_d = c.fetchone()
                c.close()
                if res_d:
                    doa_atual = {"nome": res_d[0], "contato": res_d[1], "observacao": res_d[2]}
                    st.info(f"Editando Doador ID: {st.session_state.edit_doa_id} - {res_d[0]}")

            with st.form("form_doador"):
                d_nome = st.text_input("Nome do Doador", value=doa_atual["nome"])
                d_cont = st.text_input("Contato", value=doa_atual["contato"])
                d_obs = st.text_input("Observação", value=doa_atual["observacao"])
                
                if st.form_submit_button("💾 Salvar / Atualizar Doador", use_container_width=True):
                    if d_nome:
                        c = conn.cursor()
                        if st.session_state.edit_doa_id:
                            c.execute("UPDATE doadores SET nome=%s, contato=%s, observacao=%s WHERE id=%s", 
                                      (d_nome, d_cont, d_obs, st.session_state.edit_doa_id))
                            st.success("Doador atualizado com sucesso!")
                        else:
                            c.execute("INSERT INTO doadores (nome, contato, observacao) VALUES (%s,%s,%s)", 
                                      (d_nome, d_cont, d_obs))
                            st.success("Doador cadastrado com sucesso!")
                        conn.commit()
                        c.close()
                        st.session_state.edit_doa_id = None
                        st.rerun()
                    else:
                        st.warning("O nome do doador é obrigatório.")
            
            st.divider()
            st.subheader("Lista de Doadores")
            query_d = "SELECT * FROM doadores"
            if termo_d:
                query_d += f" WHERE nome ILIKE '%{termo_d}%'"
            st.dataframe(pd.read_sql(query_d, conn), use_container_width=True, hide_index=True)

        with tab_adm5:
            st.subheader("Gerenciar Campos Conveniados")
            if 'edit_camp_id' not in st.session_state:
                st.session_state.edit_camp_id = None

            df_camp_all = pd.read_sql("SELECT id, nome_local FROM campos ORDER BY nome_local ASC", conn)
            with st.expander("🔍 Pesquisar / Selecionar Campo", expanded=True):
                termo_c = st.text_input("Pesquisar campo por nome do local:")
                if not df_camp_all.empty:
                    lista_opcoes_camp = {f"ID {row['id']} - {row['nome_local']}": row['id'] for _, row in df_camp_all.iterrows()}
                    camp_selecionado_str = st.selectbox("Selecione o campo:", ["-- Novo Campo --"] + list(lista_opcoes_camp.keys()))
                    
                    col_c1, col_c2, col_c3 = st.columns(3)
                    if col_c1.button("✏️ Carregar Campo p/ Editar", key="btn_ed_camp"):
                        if camp_selecionado_str != "-- Novo Campo --":
                            st.session_state.edit_camp_id = lista_opcoes_camp[camp_selecionado_str]
                            st.rerun()
                    if col_c2.button("🧹 Limpar Seleção", key="btn_cl_camp"):
                        st.session_state.edit_camp_id = None
                        st.rerun()
                    if col_c3.button("🗑️ Excluir Campo", key="btn_del_camp"):
                        if camp_selecionado_str != "-- Novo Campo --":
                            id_c_exc = lista_opcoes_camp[camp_selecionado_str]
                            c = conn.cursor()
                            c.execute("DELETE FROM campos WHERE id = %s", (id_c_exc,))
                            conn.commit()
                            c.close()
                            st.session_state.edit_camp_id = None
                            st.success("Campo excluído com sucesso!")
                            st.rerun()

            camp_atual = {"nome_local": "", "endereco": "", "responsavel": "", "contato": ""}
            if st.session_state.edit_camp_id:
                c = conn.cursor()
                c.execute("SELECT nome_local, endereco, responsavel, contato FROM campos WHERE id = %s", (st.session_state.edit_camp_id,))
                res_c = c.fetchone()
                c.close()
                if res_c:
                    camp_atual = {"nome_local": res_c[0], "endereco": res_c[1], "responsavel": res_c[2], "contato": res_c[3]}
                    st.info(f"Editando Campo ID: {st.session_state.edit_camp_id} - {res_c[0]}")

            with st.form("form_campo"):
                c_nome = st.text_input("Nome do Local / Arena", value=camp_atual["nome_local"])
                c_end = st.text_input("Endereço", value=camp_atual["endereco"])
                c_resp = st.text_input("Responsável", value=camp_atual["responsavel"])
                c_cont = st.text_input("Contato", value=camp_atual["contato"])
                
                if st.form_submit_button("💾 Salvar / Atualizar Campo", use_container_width=True):
                    if c_nome:
                        c = conn.cursor()
                        if st.session_state.edit_camp_id:
                            c.execute("UPDATE campos SET nome_local=%s, endereco=%s, responsavel=%s, contato=%s WHERE id=%s", 
                                      (c_nome, c_end, c_resp, c_cont, st.session_state.edit_camp_id))
                            st.success("Campo atualizado com sucesso!")
                        else:
                            c.execute("INSERT INTO campos (nome_local, endereco, responsavel, contato) VALUES (%s,%s,%s,%s)", 
                                      (c_nome, c_end, c_resp, c_cont))
                            st.success("Campo cadastrado com sucesso!")
                        conn.commit()
                        c.close()
                        st.session_state.edit_camp_id = None
                        st.rerun()
                    else:
                        st.warning("O nome do local é obrigatório.")
            
            st.divider()
            st.subheader("Lista de Campos Conveniados")
            query_c = "SELECT * FROM campos"
            if termo_c:
                query_c += f" WHERE nome_local ILIKE '%{termo_c}%'"
            st.dataframe(pd.read_sql(query_c, conn), use_container_width=True, hide_index=True)

        with tab_adm6:
            st.subheader("💾 Central de Backup e Segurança de Dados")
            st.write("Baixe uma cópia de segurança em formato CSV de todas as tabelas do sistema para o seu computador a qualquer momento.")
            
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                df_b_atletas = pd.read_sql("SELECT * FROM atletas", conn)
                st.download_button(
                    label="📥 Baixar Backup de Membros (CSV)",
                    data=df_b_atletas.to_csv(index=False).encode('utf-8'),
                    file_name="backup_membros_uniao_itapura.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                df_b_fin = pd.read_sql("SELECT * FROM financeiro", conn)
                st.download_button(
                    label="📥 Baixar Backup Financeiro (CSV)",
                    data=df_b_fin.to_csv(index=False).encode('utf-8'),
                    file_name="backup_financeiro_uniao_itapura.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col_b2:
                df_b_jogos = pd.read_sql("SELECT * FROM jogos", conn)
                st.download_button(
                    label="📥 Baixar Backup de Jogos (CSV)",
                    data=df_b_jogos.to_csv(index=False).encode('utf-8'),
                    file_name="backup_jogos_uniao_itapura.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                df_b_scouts = pd.read_sql("SELECT * FROM scouts", conn)
                st.download_button(
                    label="📥 Baixar Backup de Scouts (CSV)",
                    data=df_b_scouts.to_csv(index=False).encode('utf-8'),
                    file_name="backup_scouts_uniao_itapura.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # ==========================================
    # 📊 DASHBOARD
    # ==========================================
elif menu == "📊 Dashboard":
        st.title("📊 GESTÃO TIME DE VÁRZEA - Painel Executivo")
        
        ativos = pd.read_sql("SELECT COUNT(*) FROM atletas WHERE status='Ativo'", conn).iloc[0,0]
        vit = pd.read_sql("SELECT COUNT(*) FROM jogos WHERE resultado='Vitória'", conn).iloc[0,0]
        emp = pd.read_sql("SELECT COUNT(*) FROM jogos WHERE resultado='Empate'", conn).iloc[0,0]
        der = pd.read_sql("SELECT COUNT(*) FROM jogos WHERE resultado='Derrota'", conn).iloc[0,0]
        
        df_fin = pd.read_sql("SELECT tipo, valor FROM financeiro", conn)
        saldo = 0.0
        entradas_cat = ["Mensalidade", "Avulso", "Patrocínio", "Diretoria", "Verba", "Doação"]
        for _, row in df_fin.iterrows():
            if row['valor'] < 0: saldo += row['valor']
            else:
                if row['tipo'] in entradas_cat: saldo += row['valor']
                else: saldo -= row['valor']

        cor_saldo = "#00cc66" if saldo >= 0 else "#ff4d4d"

        st.markdown(
            f"""
            <div style="display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 140px; background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-top: 4px solid #3399ff;">
                    <p style="color: gray; margin: 0; font-size: 13px;">Membros Ativos</p>
                    <h2 style="color: white; margin: 5px 0 0 0;">{ativos}</h2>
                </div>
                <div style="flex: 1; min-width: 140px; background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-top: 4px solid #00b33c;">
                    <p style="color: gray; margin: 0; font-size: 13px;">Vitórias</p>
                    <h2 style="color: #00b33c; margin: 5px 0 0 0;">{vit}</h2>
                </div>
                <div style="flex: 1; min-width: 140px; background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-top: 4px solid #ffcc00;">
                    <p style="color: gray; margin: 0; font-size: 13px;">Empates</p>
                    <h2 style="color: #ffcc00; margin: 5px 0 0 0;">{emp}</h2>
                </div>
                <div style="flex: 1; min-width: 140px; background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-top: 4px solid #ff4d4d;">
                    <p style="color: gray; margin: 0; font-size: 13px;">Derrotas</p>
                    <h2 style="color: #ff4d4d; margin: 5px 0 0 0;">{der}</h2>
                </div>
                <div style="flex: 1; min-width: 140px; background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-top: 4px solid {cor_saldo};">
                    <p style="color: gray; margin: 0; font-size: 13px;">Saldo em Caixa</p>
                    <h2 style="color: {cor_saldo}; margin: 5px 0 0 0;">R$ {saldo:.2f}</h2>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("📈 Movimentações Financeiras por Categoria")
            if not df_fin.empty:
                df_grp = df_fin.groupby('tipo')['valor'].sum().reset_index()
                
                # Calcula a porcentagem em relação ao total absoluto movimentado
                total_abs = df_grp['valor'].abs().sum()
                if total_abs > 0:
                    df_grp['porcentagem'] = (df_grp['valor'].abs() / total_abs) * 100
                    df_grp['rotulo_pct'] = df_grp['porcentagem'].apply(lambda x: f"{x:.1f}%")
                else:
                    df_grp['rotulo_pct'] = "0.0%"
                
                import altair as alt
                
                # Base do gráfico de barras
                barras = alt.Chart(df_grp).mark_bar().encode(
                    x=alt.X('tipo:N', title='Categoria', sort='-y', axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('valor:Q', title='Valor (R$)'),
                    color=alt.Color('tipo:N', legend=None)
                )
                
                # Rótulos de texto com a porcentagem em cima/abaixo das barras
                texto = alt.Chart(df_grp).mark_text(
                    dy=-10,
                    color='white',
                    fontSize=11
                ).encode(
                    x=alt.X('tipo:N', sort='-y'),
                    y=alt.Y('valor:Q'),
                    text='rotulo_pct:N'
                )
                
                chart = (barras + texto).properties(height=300)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Sem dados financeiros para exibir gráfico.")

        with col_g2:
            st.subheader("🏃 Top 5 Presenças em Jogos")
            df_pres = pd.read_sql("""
                SELECT a.nome, COUNT(p.id) as total_presenca 
                FROM atletas a JOIN presencas p ON a.id = p.atleta_id 
                WHERE p.presenca = 1
                GROUP BY a.id ORDER BY total_presenca DESC LIMIT 5
            """, conn)
            if not df_pres.empty:
                st.dataframe(df_pres, use_container_width=True, hide_index=True)
            else:
                st.info("Sem registros de presença nas súmulas.")

        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🎂 Aniversariantes (Próximos 3 Meses)")
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            limite_tres_meses = hoje + timedelta(days=90)
            
            dias_semana_pt = {
                0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
                3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
            }
            
            df_atletas = pd.read_sql("SELECT nome, nascimento FROM atletas WHERE status='Ativo'", conn)
            aniv_encontrados = []
            
            for _, row in df_atletas.iterrows():
                nasc_str = str(row['nascimento'] or "").strip()
                if len(nasc_str) >= 10:
                    try:
                        partes = nasc_str.split('/')
                        dia_nasc = int(partes[0])
                        mes_nasc = int(partes[1])
                        ano_nasc = int(partes[2])
                        
                        # Testa o aniversário no ano atual e no próximo ano para abranger o intervalo de 90 dias
                        for ano_ref in [hoje.year, hoje.year + 1]:
                            try:
                                aniv_dt = datetime(ano_ref, mes_nasc, dia_nasc)
                            except ValueError:
                                continue
                                
                            if hoje <= aniv_dt <= limite_tres_meses:
                                idade_que_faz = aniv_dt.year - ano_nasc
                                dia_semana = dias_semana_pt[aniv_dt.weekday()]
                                data_formatada = aniv_dt.strftime(f"%d/%m ({dia_semana})")
                                
                                aniv_encontrados.append({
                                    'data_obj': aniv_dt,
                                    'Atleta': row['nome'],
                                    'Data': data_formatada,
                                    'Idade': f"{idade_que_faz} anos"
                                })
                    except:
                        continue
            
            # Remove duplicatas caso caia no mesmo ano e ordena
            aniv_unicos = {x['Atleta'] + x['Data']: x for x in aniv_encontrados}.values()
            aniv_ordenados = sorted(aniv_unicos, key=lambda x: x['data_obj'])
            
            if aniv_ordenados:
                df_aniv_final = pd.DataFrame(aniv_ordenados)[['Atleta', 'Data', 'Idade']]
                st.dataframe(df_aniv_final, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum aniversariante próximo nos próximos 3 meses.")

        with col_b:
            st.subheader("🏆 Top Artilheiros & Assistências")
            df_art = pd.read_sql("""
                SELECT a.nome, SUM(s.gols) as gols, SUM(s.assistencias) as assists 
                FROM atletas a JOIN scouts s ON a.id = s.atleta_id 
                GROUP BY a.id ORDER BY gols DESC LIMIT 5
            """, conn)
            if not df_art.empty:
                st.dataframe(df_art, use_container_width=True, hide_index=True)
            else:
                st.info("Sem registros de scouts.")

    # ==========================================
    # 👥 MEMBROS
    # ==========================================
elif menu == "👥 Membros":
        st.title("👥 Gestão de Membros & Identificação")
        if 'edit_membro_id' not in st.session_state:
            st.session_state.edit_membro_id = None

        df_membros_all = pd.read_sql("SELECT id, nome FROM atletas ORDER BY nome ASC", conn)
        with st.expander("🔍 Painel de Pesquisa / Seleção de Membros", expanded=True):
            col_p1, col_p2 = st.columns([3, 1])
            with col_p1:
                termo_pesquisa = st.text_input("Pesquisar membro por nome:")
            with col_p2:
                btn_pesquisar = st.button("Pesquisar", use_container_width=True)
            
            if not df_membros_all.empty:
                lista_opcoes_membros = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_membros_all.iterrows()}
                membro_selecionado_str = st.selectbox("Ou selecione diretamente na lista:", ["-- Novo Cadastro --"] + list(lista_opcoes_membros.keys()))
                
                col_b1, col_b2, col_b3 = st.columns(3)
                if col_b1.button("✏️ Carregar para Editar"):
                    if membro_selecionado_str != "-- Novo Cadastro --":
                        st.session_state.edit_membro_id = lista_opcoes_membros[membro_selecionado_str]
                        st.success("Membro carregado para edição abaixo!")
                        st.rerun()
                if col_b2.button("🧹 Limpar Seleção / Tela"):
                    st.session_state.edit_membro_id = None
                    st.rerun()
                if col_b3.button("🗑️ Excluir Membro Selecionado"):
                    if membro_selecionado_str != "-- Novo Cadastro --":
                        id_excluir = lista_opcoes_membros[membro_selecionado_str]
                        c = conn.cursor()
                        c.execute("DELETE FROM atletas WHERE id = %s", (id_excluir,))
                        conn.commit()
                        c.close()
                        st.session_state.edit_membro_id = None
                        st.success("Membro excluído com sucesso!")
                        st.rerun()

        membro_atual = {"nome": "", "documentos": "", "nascimento": "", "nome_mae": "", "telefone": "", "endereco": "", "cargo": "Jogador", "posicao": "Goleiro", "status": "Ativo", "foto_path": ""}
        if st.session_state.edit_membro_id:
            c = conn.cursor()
            c.execute("SELECT nome, documentos, nascimento, posicao, telefone, endereco, status, cargo, nome_mae, foto_path FROM atletas WHERE id = %s", (st.session_state.edit_membro_id,))
            res_m = c.fetchone()
            c.close()
            if res_m:
                membro_atual = {"nome": res_m[0], "documentos": res_m[1], "nascimento": res_m[2], "posicao": res_m[3], "telefone": res_m[4], "endereco": res_m[5], "status": res_m[6], "cargo": res_m[7], "nome_mae": res_m[8], "foto_path": res_m[9]}
                st.info(f"Editando o membro: **{res_m[0]}** (ID: {st.session_state.edit_membro_id})")

        with st.form("form_membro"):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome Completo", value=membro_atual["nome"])
                docs = st.text_input("Documentos (RG/CPF)", value=membro_atual["documentos"])
                nasc = st.text_input("Nascimento (DD/MM/AAAA)", value=membro_atual["nascimento"])
                nome_mae = st.text_input("Nome da Mãe", value=membro_atual["nome_mae"])
                tel = st.text_input("Telefone / WhatsApp", value=membro_atual["telefone"])
            with col2:
                endereco = st.text_input("Endereço", value=membro_atual["endereco"])
                cargos_lista = ["Jogador", "Diretor", "Técnico", "Colaborador", "Assistente", "Marketing", "Ajudante", "Outros"]
                idx_cargo = cargos_lista.index(membro_atual["cargo"]) if membro_atual["cargo"] in cargos_lista else 0
                cargo = st.selectbox("Cargo", cargos_lista, index=idx_cargo)
                
                pos_lista = ["Goleiro", "Zagueiro", "Lateral", "Volante", "Meia", "Atacante", "N/A"]
                idx_pos = pos_lista.index(membro_atual["posicao"]) if membro_atual["posicao"] in pos_lista else 0
                posicao = st.selectbox("Posição em Campo", pos_lista, index=idx_pos)
                
                status_lista = ["Ativo", "Inativo"]
                idx_status = status_lista.index(membro_atual["status"]) if membro_atual["status"] in status_lista else 0
                status = st.selectbox("Status", status_lista, index=idx_status)
                foto_path = st.text_input("Caminho ou URL da Foto 3x4 (Opcional)", value=membro_atual["foto_path"])
            
            btn_salvar_membro = st.form_submit_button("💾 Salvar / Atualizar Membro", use_container_width=True)
            if btn_salvar_membro:
                if nome:
                    c = conn.cursor()
                    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if st.session_state.edit_membro_id:
                        c.execute("""UPDATE atletas SET nome=%s, documentos=%s, nascimento=%s, posicao=%s, telefone=%s, endereco=%s, status=%s, cargo=%s, nome_mae=%s, foto_path=%s, criado_por=%s, data_registro=%s WHERE id=%s""",
                                  (nome, docs, nasc, posicao, tel, endereco, status, cargo, nome_mae, foto_path, st.session_state.usuario, data_hora_atual, st.session_state.edit_membro_id))
                        st.success(f"Membro atualizado com sucesso por {st.session_state.usuario}!")
                    else:
                        c.execute("""INSERT INTO atletas (nome, documentos, nascimento, posicao, telefone, endereco, status, cargo, nome_mae, foto_path, criado_por, data_registro) 
                                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                                  (nome, docs, nasc, posicao, tel, endereco, status, cargo, nome_mae, foto_path, st.session_state.usuario, data_hora_atual))
                        st.success(f"Membro cadastrado com sucesso por {st.session_state.usuario}!")
                    conn.commit()
                    c.close()
                    st.session_state.edit_membro_id = None
                    st.rerun()
                else:
                    st.warning("O nome é obrigatório.")

        st.divider()
        st.subheader("Lista de Membros (Com Auditoria)")
        query_m = "SELECT id, nome, cargo, posicao, telefone, status, criado_por, data_registro FROM atletas"
        if termo_pesquisa:
            query_m += f" WHERE nome ILIKE '%{termo_pesquisa}%'"
        query_m += " ORDER BY nome ASC"
        st.dataframe(pd.read_sql(query_m, conn), use_container_width=True, hide_index=True)

    # ==========================================
    # 💰 FINANCEIRO
    # ==========================================
elif menu == "💰 Financeiro":
        st.title("💰 Controle Financeiro & Calendário de Mensalidades")
        tab1, tab2 = st.tabs(["💵 Lançamentos Gerais", "📅 Calendário de Mensalidades & Relatório"])
        
        with tab1:
            if 'edit_fin_id' not in st.session_state:
                st.session_state.edit_fin_id = None

            df_fin_all = pd.read_sql("SELECT id, tipo, valor, data, observacao FROM financeiro ORDER BY id DESC", conn)
            with st.expander("🔍 Pesquisar / Gerenciar Lançamentos", expanded=True):
                termo_f = st.text_input("Pesquisar no extrato (por tipo ou observação):")
                if not df_fin_all.empty:
                    lista_opcoes_fin = {f"ID {row['id']} - {row['tipo']} | R$ {row['valor']} ({row['data']})": row['id'] for _, row in df_fin_all.iterrows()}
                    fin_selecionado_str = st.selectbox("Selecione um lançamento:", ["-- Novo Lançamento --"] + list(lista_opcoes_fin.keys()))
                    
                    col_f1, col_f2, col_f3 = st.columns(3)
                    if col_f1.button("✏️ Carregar Lançamento p/ Editar"):
                        if fin_selecionado_str != "-- Novo Lançamento --":
                            st.session_state.edit_fin_id = lista_opcoes_fin[fin_selecionado_str]
                            st.rerun()
                    if col_f2.button("🧹 Limpar Seleção"):
                        st.session_state.edit_fin_id = None
                        st.rerun()
                    if col_f3.button("🗑️ Excluir Lançamento"):
                        if fin_selecionado_str != "-- Novo Lançamento --":
                            id_f_exc = lista_opcoes_fin[fin_selecionado_str]
                            c = conn.cursor()
                            c.execute("DELETE FROM financeiro WHERE id = %s", (id_f_exc,))
                            conn.commit()
                            c.close()
                            st.session_state.edit_fin_id = None
                            st.success("Lançamento excluído!")
                            st.rerun()

            fin_atual = {"data": datetime.now().strftime("%d/%m/%Y"), "valor": 50.00, "tipo": "Mensalidade", "observacao": "", "atleta_id": None, "referencia": datetime.now().strftime("%m/%Y")}
            if st.session_state.edit_fin_id:
                c = conn.cursor()
                c.execute("SELECT data, valor, tipo, observacao, atleta_id, referencia FROM financeiro WHERE id = %s", (st.session_state.edit_fin_id,))
                res_f = c.fetchone()
                c.close()
                if res_f:
                    fin_atual = {"data": res_f[0], "valor": res_f[1], "tipo": res_f[2], "observacao": res_f[3], "atleta_id": res_f[4], "referencia": res_f[5] or datetime.now().strftime("%m/%Y")}
                    st.info(f"Editando Lançamento ID: {st.session_state.edit_fin_id}")

            with st.form("form_fin"):
                c1, c2, c3 = st.columns(3)
                f_data = c1.text_input("Data do Lançamento", value=fin_atual["data"])
                f_valor = c2.number_input("Valor (R$)", value=float(fin_atual["valor"]), format="%.2f")
                
                categorias_f = ["Mensalidade", "Jogos", "Avulso", "Patrocínio", "Diretoria", "Verba", "Doação", "Manutenção", "Água", "Juiz/Troféu", "Outros"]
                idx_tipo = categorias_f.index(fin_atual["tipo"]) if fin_atual["tipo"] in categorias_f else 0
                f_tipo = c3.selectbox("Categoria", categorias_f, index=idx_tipo)
                
                atleta_id_escolhido = None
                f_ref = datetime.now().strftime("%m/%Y")
                
                if f_tipo == "Mensalidade":
                    st.markdown("---")
                    st.markdown("📌 **Vínculo da Mensalidade com o Atleta**")
                    df_atl_box = pd.read_sql("SELECT id, nome FROM atletas WHERE status='Ativo' ORDER BY nome ASC", conn)
                    if not df_atl_box.empty:
                        dict_atl = {row['nome']: row['id'] for _, row in df_atl_box.iterrows()}
                        atl_escolhido_nome = st.selectbox("Selecione o Atleta Pagante", list(dict_atl.keys()))
                        atleta_id_escolhido = dict_atl[atl_escolhido_nome]
                        f_ref = st.text_input("Mês de Referência (Ex: 08/2026)", value=fin_atual["referencia"])

                f_obs = st.text_area("Observação", value=fin_atual["observacao"])
                
                if st.form_submit_button("💾 Salvar / Atualizar Lançamento", use_container_width=True):
                    c = conn.cursor()
                    dh_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    ref_final = f_ref if f_tipo == "Mensalidade" else None
                    atl_final = atleta_id_escolhido if f_tipo == "Mensalidade" else None

                    if st.session_state.edit_fin_id:
                        c.execute("UPDATE financeiro SET valor=%s, data=%s, tipo=%s, observacao=%s, atleta_id=%s, referencia=%s, criado_por=%s, data_registro=%s WHERE id=%s", 
                                  (f_valor, f_data, f_tipo, f_obs, atl_final, ref_final, st.session_state.usuario, dh_atual, st.session_state.edit_fin_id))
                        st.success(f"Lançamento atualizado por {st.session_state.usuario}!")
                    else:
                        c.execute("INSERT INTO financeiro (valor, data, tipo, observacao, atleta_id, referencia, criado_por, data_registro) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                  (f_valor, f_data, f_tipo, f_obs, atl_final, ref_final, st.session_state.usuario, dh_atual))
                        st.success(f"Lançamento efetuado com sucesso!")
                    conn.commit()
                    c.close()
                    st.session_state.edit_fin_id = None
                    st.rerun()

            st.subheader("Extrato Financeiro (Com Auditoria)")
            query_ext = "SELECT id, data, tipo, valor, referencia, observacao, criado_por, data_registro FROM financeiro"
            if termo_f:
                query_ext += f" WHERE tipo ILIKE '%{termo_f}%' OR observacao ILIKE '%{termo_f}%'"
            query_ext += " ORDER BY id DESC"
            st.dataframe(pd.read_sql(query_ext, conn), use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("📅 Calendário de Mensalidades & Painel Financeiro")
            mes_ref_cal = st.text_input("Digite o Mês e Ano de Referência para Visualizar (Ex: 08/2026):", value=datetime.now().strftime("%m/%Y"))
            atletas_ativos = pd.read_sql("SELECT id, nome, telefone FROM atletas WHERE status='Ativo' ORDER BY nome ASC", conn)
            
            if not atletas_ativos.empty:
                c = conn.cursor()
                c.execute("SELECT atleta_id, valor FROM financeiro WHERE tipo='Mensalidade' AND referencia=%s", (mes_ref_cal,))
                pagamentos_efetuados = {row[0]: row[1] for row in c.fetchall()}
                c.close()
                
                dados_calendario = []
                total_arrecadado = 0.0
                total_pendente = 0.0
                valor_padrao_mensalidade = 50.00
                
                for _, atleta in atletas_ativos.iterrows():
                    aid = atleta['id']
                    nome_atleta = atleta['nome']
                    if aid in pagamentos_efetuados:
                        status = "✅ Pago"
                        val_pago = pagamentos_efetuados[aid]
                        total_arrecadado += val_pago
                        val_falta = 0.0
                    else:
                        status = "❌ Inadimplente"
                        val_pago = 0.0
                        total_pendente += valor_padrao_mensalidade
                        val_falta = valor_padrao_mensalidade
                    
                    dados_calendario.append({
                        "Atleta": nome_atleta,
                        "Status": status,
                        "Valor Pago (R$)": f"R$ {val_pago:.2f}" if val_pago > 0 else "R$ 0.00",
                        "Falta Pagar (R$)": f"R$ {val_falta:.2f}" if val_falta > 0 else "Quitado"
                    })
                
                df_cal = pd.DataFrame(dados_calendario)
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("💵 Total Arrecadado", f"R$ {total_arrecadado:.2f}")
                col_m2.metric("⚠️ Total Inadimplente (Pendente)", f"R$ {total_pendente:.2f}")
                col_m3.metric("👥 Atletas Ativos", len(atletas_ativos))
                
                st.markdown("---")
                st.subheader(f"📋 Calendário de Mensalidades - Referência: {mes_ref_cal}")
                st.dataframe(df_cal, use_container_width=True, hide_index=True)
                
                if st.button("📥 Gerar Relatório em PDF do Calendário de Mensalidades", use_container_width=True):
                    pdf = PDFRelatorio(f"CALENDARIO DE MENSALIDADES - {mes_ref_cal}")
                    pdf.add_page()
                    
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 8, f"Resumo Financeiro - Mes: {mes_ref_cal}", 0, 1)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(0, 6, f"Valor Total Arrecadado: R$ {total_arrecadado:.2f}", 0, 1)
                    pdf.cell(0, 6, f"Valor Total Inadimplente: R$ {total_pendente:.2f}", 0, 1)
                    pdf.ln(5)
                    
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 8, "Detalhamento por Atleta", 0, 1)
                    
                    for item in dados_calendario:
                        status_texto = "PAGO" if "Pago" in item['Status'] else "INADIMPLENTE"
                        pdf.set_font("Helvetica", "", 9)
                        pdf.cell(0, 6, f"- {item['Atleta']} | Status: {status_texto} | Pago: {item['Valor Pago (R$)']} | Pendente: {item['Falta Pagar (R$)']}", 0, 1)
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    st.success("PDF do Calendário de Mensalidades gerado com sucesso!")
                    st.download_button(
                        label="⬇️ Baixar Arquivo PDF Calendário de Mensalidades",
                        data=pdf_bytes,
                        file_name="Calendario_Mensalidades.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

    # ==========================================
    # ⚽ JOGOS & SÚMULA
    # ==========================================
elif menu == "⚽ Jogos":
        st.title("⚽ Cadastro de Partidas & Súmula de Presença")
        if 'edit_jogo_id' not in st.session_state:
            st.session_state.edit_jogo_id = None

        df_jogos_all = pd.read_sql("SELECT id, adversario, data FROM jogos ORDER BY id DESC", conn)
        with st.expander("🔍 Pesquisar / Gerenciar Partidas", expanded=True):
            termo_j = st.text_input("Pesquisar partida por adversário:")
            if not df_jogos_all.empty:
                lista_opcoes_jogos = {f"ID {row['id']} - vs {row['adversario']} ({row['data']})": row['id'] for _, row in df_jogos_all.iterrows()}
                jogo_selecionado_str = st.selectbox("Selecione a partida:", ["-- Nova Partida --"] + list(lista_opcoes_jogos.keys()))
                
                col_j1, col_j2, col_j3 = st.columns(3)
                if col_j1.button("✏️ Carregar Partida p/ Editar"):
                    if jogo_selecionado_str != "-- Nova Partida --":
                        st.session_state.edit_jogo_id = lista_opcoes_jogos[jogo_selecionado_str]
                        st.rerun()
                if col_j2.button("🧹 Limpar Seleção"):
                    st.session_state.edit_jogo_id = None
                    st.rerun()
                if col_j3.button("🗑️ Excluir Partida"):
                    if jogo_selecionado_str != "-- Nova Partida --":
                        id_j_exc = lista_opcoes_jogos[jogo_selecionado_str]
                        c = conn.cursor()
                        c.execute("DELETE FROM jogos WHERE id = %s", (id_j_exc,))
                        c.execute("DELETE FROM presencas WHERE jogo_id = %s", (id_j_exc,))
                        conn.commit()
                        c.close()
                        st.session_state.edit_jogo_id = None
                        st.success("Partida excluída!")
                        st.rerun()

        jogo_atual = {"data": datetime.now().strftime("%d/%m/%Y"), "adversario": "", "local": "Mandante", "p_u": 0, "p_a": 0, "pen": "", "obs": ""}
        if st.session_state.edit_jogo_id:
            c = conn.cursor()
            c.execute("SELECT data, adversario, local, placar_uniao, placar_adv, penaltis, observacao FROM jogos WHERE id = %s", (st.session_state.edit_jogo_id,))
            res_j = c.fetchone()
            c.close()
            if res_j:
                jogo_atual = {"data": res_j[0], "adversario": res_j[1], "local": res_j[2], "p_u": res_j[3], "p_a": res_j[4], "pen": res_j[5] or "", "obs": res_j[6] or ""}
                st.info(f"Editando Partida ID: {st.session_state.edit_jogo_id} vs {res_j[1]}")

        c1, c2, c3 = st.columns(3)
        j_data = c1.text_input("Data do Jogo", value=jogo_atual["data"])
        j_adv = c2.text_input("Nome do Adversário", value=jogo_atual["adversario"])
        loc_lista = ["Mandante", "Visitante"]
        idx_loc = loc_lista.index(jogo_atual["local"]) if jogo_atual["local"] in loc_lista else 0
        j_loc = c3.selectbox("Local / Mando", loc_lista, index=idx_loc)
        
        st.markdown("---")
        st.markdown("⚽ **Placar do Tempo Normal (90 minutos)**")
        sc1, sc2 = st.columns(2)
        j_gols_uniao = sc1.number_input("Gols do União Itapura", min_value=0, step=1, value=int(jogo_atual["p_u"]))
        j_gols_adv = sc2.number_input("Gols do Adversário", min_value=0, step=1, value=int(jogo_atual["p_a"]))
        
        j_penaltis = ""
        if j_gols_uniao == j_gols_adv:
            st.markdown("⚠️ *O jogo terminou empatado no tempo normal.*")
            teve_penaltis = st.selectbox("Houve disputa de pênaltis?", ["Não", "Sim"], index=0 if not jogo_atual["pen"] else 1)
            
            if teve_penaltis == "Sim":
                st.markdown("🥅 **Placar da Disputa de Pênaltis**")
                pc1, pc2 = st.columns(2)
                pen_uniao = pc1.number_input("Pênaltis União Itapura", min_value=0, step=1, value=0)
                pen_adv = pc2.number_input("Pênaltis Adversário", min_value=0, step=1, value=0)
                j_penaltis = f"União {pen_uniao} x {pen_adv} Adversário"

        with st.form("form_jogos_sufixo"):
            j_obs = st.text_area("Observações da Partida", value=jogo_atual["obs"])
            
            st.subheader("📋 Súmula: Marque os atletas presentes nesta partida")
            atletas_ativos = pd.read_sql("SELECT id, nome, posicao FROM atletas WHERE status='Ativo'", conn)
            
            presencas_salvas = []
            if st.session_state.edit_jogo_id:
                c = conn.cursor()
                c.execute("SELECT atleta_id FROM presencas WHERE jogo_id = %s AND presenca = 1", (st.session_state.edit_jogo_id,))
                presencas_salvas = [row[0] for row in c.fetchall()]
                c.close()

            presencas_checks = {}
            for _, r in atletas_ativos.iterrows():
                ja_presente = r['id'] in presencas_salvas
                presencas_checks[r['id']] = st.checkbox(f"{r['nome']} ({r['posicao']})", value=ja_presente)
            
            btn_salvar_partida = st.form_submit_button("💾 Salvar / Atualizar Partida e Súmula", use_container_width=True)
            
            if btn_salvar_partida:
                if j_adv:
                    if j_gols_uniao > j_gols_adv:
                        res = "Vitória"
                    elif j_gols_uniao < j_gols_adv:
                        res = "Derrota"
                    else:
                        res = "Empate"
                    
                    c = conn.cursor()
                    dh_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if st.session_state.edit_jogo_id:
                        jid = st.session_state.edit_jogo_id
                        c.execute("""UPDATE jogos SET adversario=%s, placar_uniao=%s, placar_adv=%s, data=%s, local=%s, penaltis=%s, observacao=%s, resultado=%s, criado_por=%s, data_registro=%s WHERE id=%s""", 
                                  (j_adv, j_gols_uniao, j_gols_adv, j_data, j_loc, j_penaltis, j_obs, res, st.session_state.usuario, dh_atual, jid))
                        c.execute("DELETE FROM presencas WHERE jogo_id = %s", (jid,))
                        st.success(f"Partida atualizada por {st.session_state.usuario}!")
                    else:
                        c.execute("""INSERT INTO jogos (adversario, placar_uniao, placar_adv, data, local, penaltis, observacao, resultado, criado_por, data_registro) 
                                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""", 
                                  (j_adv, j_gols_uniao, j_gols_adv, j_data, j_loc, j_penaltis, j_obs, res, st.session_state.usuario, dh_atual))
                        jid = c.fetchone()[0]
                        st.success(f"Partida gravada por {st.session_state.usuario}!")
                    
                    for aid, presente in presencas_checks.items():
                        if presente:
                            c.execute("INSERT INTO presencas (atleta_id, jogo_id, presenca) VALUES (%s,%s,%s)", (aid, jid, 1))
                    
                    conn.commit()
                    c.close()
                    st.session_state.edit_jogo_id = None
                    st.rerun()
                else:
                    st.warning("Informe o nome do adversário.")

        st.subheader("Histórico de Partidas (Com Auditoria)")
        query_jogos = "SELECT id, data, adversario, placar_uniao, placar_adv, penaltis, resultado, criado_por, data_registro FROM jogos"
        if termo_j:
            query_jogos += f" WHERE adversario ILIKE '%{termo_j}%'"
        query_jogos += " ORDER BY id DESC"
        st.dataframe(pd.read_sql(query_jogos, conn), use_container_width=True, hide_index=True)

    # ==========================================
    # 🏆 SCOUT
    # ==========================================
elif menu == "🏆 Scout":
        st.title("🏆 Registro de Gols e Assistências")
        if 'edit_scout_id' not in st.session_state:
            st.session_state.edit_scout_id = None

        df_j_list = pd.read_sql("SELECT id, adversario, data FROM jogos ORDER BY id DESC", conn)
        df_a_list = pd.read_sql("SELECT id, nome FROM atletas WHERE status='Ativo' ORDER BY nome ASC", conn)
        df_scouts_all = pd.read_sql("SELECT s.id, a.nome, j.adversario, s.gols, s.assistencias FROM scouts s JOIN atletas a ON s.atleta_id = a.id JOIN jogos j ON s.jogo_id = j.id ORDER BY s.id DESC", conn)
        
        with st.expander("🔍 Pesquisar / Gerenciar Scouts", expanded=True):
            if not df_scouts_all.empty:
                lista_opcoes_scout = {f"ID {row['id']} - Atleta: {row['nome']} | vs {row['adversario']} (Gols: {row['gols']}, Assist: {row['assistencias']})": row['id'] for _, row in df_scouts_all.iterrows()}
                scout_selecionado_str = st.selectbox("Selecione o registro de Scout:", ["-- Novo Scout --"] + list(lista_opcoes_scout.keys()))
                
                col_s1, col_s2, col_s3 = st.columns(3)
                if col_s1.button("✏️ Carregar Scout p/ Editar"):
                    if scout_selecionado_str != "-- Novo Scout --":
                        st.session_state.edit_scout_id = lista_opcoes_scout[scout_selecionado_str]
                        st.rerun()
                if col_s2.button("🧹 Limpar Seleção"):
                    st.session_state.edit_scout_id = None
                    st.rerun()
                if col_s3.button("🗑️ Excluir Scout"):
                    if scout_selecionado_str != "-- Novo Scout --":
                        id_s_exc = lista_opcoes_scout[scout_selecionado_str]
                        c = conn.cursor()
                        c.execute("DELETE FROM scouts WHERE id = %s", (id_s_exc,))
                        conn.commit()
                        c.close()
                        st.session_state.edit_scout_id = None
                        st.success("Scout excluído!")
                        st.rerun()

        scout_atual = {"gols": 0, "assists": 0}
        if st.session_state.edit_scout_id:
            c = conn.cursor()
            c.execute("SELECT gols, assistencias FROM scouts WHERE id = %s", (st.session_state.edit_scout_id,))
            res_s = c.fetchone()
            c.close()
            if res_s:
                scout_atual = {"gols": res_s[0], "assists": res_s[1]}
                st.info(f"Editando Scout ID: {st.session_state.edit_scout_id}")

        if not df_j_list.empty and not df_a_list.empty:
            with st.form("form_scout"):
                jogo_opcoes = {f"ID {row['id']} - União x {row['adversario']} ({row['data']})": row['id'] for _, row in df_j_list.iterrows()}
                atleta_opcoes = {row['nome']: row['id'] for _, row in df_a_list.iterrows()}
                
                j_escolha = st.selectbox("Selecione o Jogo", list(jogo_opcoes.keys()))
                a_escolha = st.selectbox("Selecione o Atleta", list(atleta_opcoes.keys()))
                
                c1, c2 = st.columns(2)
                gols = c1.number_input("Gols", min_value=0, step=1, value=int(scout_atual["gols"]))
                assists = c2.number_input("Assistências", min_value=0, step=1, value=int(scout_atual["assists"]))
                
                if st.form_submit_button("✅ Salvar / Atualizar Scout", use_container_width=True):
                    c = conn.cursor()
                    dh_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if st.session_state.edit_scout_id:
                        c.execute("UPDATE scouts SET atleta_id=%s, jogo_id=%s, gols=%s, assistencias=%s, criado_por=%s, data_registro=%s WHERE id=%s", 
                                  (atleta_opcoes[a_escolha], jogo_opcoes[j_escolha], gols, assists, st.session_state.usuario, dh_atual, st.session_state.edit_scout_id))
                        st.success(f"Scout atualizado por {st.session_state.usuario}!")
                    else:
                        c.execute("INSERT INTO scouts (atleta_id, jogo_id, gols, assistencias, data, criado_por, data_registro) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                  (atleta_opcoes[a_escolha], jogo_opcoes[j_escolha], gols, assists, datetime.now().strftime("%d/%m/%Y"), st.session_state.usuario, dh_atual))
                        st.success(f"Scout gravado por {st.session_state.usuario}!")
                    conn.commit()
                    c.close()
                    st.session_state.edit_scout_id = None
                    st.rerun()
        else:
            st.warning("Cadastre jogos e atletas ativos primeiro.")

        st.subheader("Histórico Geral de Scouts (Com Auditoria)")
        st.dataframe(pd.read_sql("SELECT s.id, a.nome, j.adversario, s.gols, s.assistencias, s.criado_por, s.data_registro FROM scouts s JOIN atletas a ON s.atleta_id = a.id JOIN jogos j ON s.jogo_id = j.id ORDER BY s.id DESC", conn), use_container_width=True, hide_index=True)

    # ==========================================
    # 📄 RELATÓRIOS PDF
    # ==========================================
elif menu == "📄 Relatórios PDF":
        st.title("📄 Central de Relatórios em PDF")
        col_r1, col_r2 = st.columns(2)
        
        with col_r1:
            # 1. RELATÓRIO FINANCEIRO
            if st.button("📥 Gerar PDF: Relatório Financeiro (Tabela)", use_container_width=True):
                data_hora_impressao = datetime.now().strftime("%d/%m/%Y - %H:%Mh")
                usuario_impressor = st.session_state.usuario
                
                pdf = PDFRelatorio("RELATÓRIO FINANCEIRO & MENSALISTAS")
                pdf.add_page(orientation='L') # Paisagem
                
                # Cabeçalho de controle de impressão no topo
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, f"IMPRESSÃO: {data_hora_impressao} - {usuario_impressor}", 0, 1, "R")
                pdf.ln(1)
                
                # Cabeçalho da Tabela (Soma exata = 277mm)
                # 20 + 26 + 48 + 24 + 129 + 30 = 277mm
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(220, 220, 220)
                pdf.set_text_color(0, 0, 0)
                
                pdf.cell(20, 7, "DATA", 1, 0, "C", True)
                pdf.cell(26, 7, "CATEGORIA", 1, 0, "C", True)
                pdf.cell(48, 7, "REFERÊNCIA", 1, 0, "C", True)
                pdf.cell(24, 7, "VALOR (R$)", 1, 0, "C", True)
                pdf.cell(129, 7, "OBSERVAÇÃO", 1, 0, "C", True)
                pdf.cell(30, 7, "REGISTRO", 1, 1, "C", True)
                
                c = conn.cursor()
                query_pdf_fin = """
                    SELECT f.data, f.tipo, f.referencia, f.valor, f.observacao, f.criado_por, f.data_registro, a.nome 
                    FROM financeiro f 
                    LEFT JOIN atletas a ON f.atleta_id = a.id 
                    ORDER BY f.id DESC
                """
                c.execute(query_pdf_fin)
                registros_fin = c.fetchall()
                c.close()
                
                pdf.set_font("Helvetica", "", 7.5)
                soma_total = 0.0
                
                for r in registros_fin:
                    dt = str(r[0] or "")
                    tp = str(r[1] or "")
                    
                    ref_original = str(r[2] or "")
                    nome_atleta = str(r[7] or "")
                    
                    if tp == "Mensalidade" and nome_atleta:
                        ref_str = f"{ref_original} - {nome_atleta}"
                    elif nome_atleta:
                        ref_str = f"{ref_original} ({nome_atleta})" if ref_original else nome_atleta
                    else:
                        ref_str = ref_original if ref_original else "-"
                        
                    val_num = float(r[3] or 0.0)
                    soma_total += val_num
                    val_str = f"R$ {val_num:.2f}"
                    obs = str(r[4] or "-")
                    
                    criado_por = str(r[5] or "-")
                    data_reg = str(r[6] or "")
                    reg_str = f"{criado_por}\n{data_reg}" if data_reg else criado_por
                    
                    altura_linha = 7.0
                    
                    # Verificação nativa de quebra de página do FPDF (evita espaços em branco indesejados)
                    if pdf.get_y() > 185:
                        pdf.add_page(orientation='L')
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_fill_color(220, 220, 220)
                        pdf.cell(20, 7, "DATA", 1, 0, "C", True)
                        pdf.cell(26, 7, "CATEGORIA", 1, 0, "C", True)
                        pdf.cell(48, 7, "REFERÊNCIA", 1, 0, "C", True)
                        pdf.cell(24, 7, "VALOR (R$)", 1, 0, "C", True)
                        pdf.cell(129, 7, "OBSERVAÇÃO", 1, 0, "C", True)
                        pdf.cell(30, 7, "REGISTRO", 1, 1, "C", True)
                        pdf.set_font("Helvetica", "", 7.5)

                    # Impressão sequencial fluida (Garante que a linha seguinte cole perfeitamente na anterior)
                    pdf.cell(20, altura_linha, dt, 1, 0, "C")
                    pdf.cell(26, altura_linha, tp, 1, 0, "L")
                    pdf.cell(48, altura_linha, ref_str[:32], 1, 0, "L")
                    pdf.cell(24, altura_linha, val_str, 1, 0, "R")
                    
                    # Observação com corte seguro
                    pdf.cell(129, altura_linha, obs[:85], 1, 0, "L")
                    
                    # Coluna de Registro formatada em bloco centralizado
                    x_reg = pdf.get_x()
                    y_reg = pdf.get_y()
                    pdf.cell(30, altura_linha, "", 1, 0, "C")
                    pdf.set_xy(x_reg, y_reg + 1)
                    pdf.set_font("Helvetica", "", 6.5)
                    pdf.multi_cell(30, 3, reg_str, 0, "C")
                    pdf.set_font("Helvetica", "", 7.5)
                    
                    # Pula para a linha de baixo perfeitamente encaixada
                    pdf.set_xy(pdf.l_margin, y_reg + altura_linha)

                # Linha de Total Geral em Caixa com Cores Condicionais (Azul Bic ou Vermelho)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(94, 8, "VALOR TOTAL GERAL EM CAIXA:", 1, 0, "R", True)
                
                if soma_total >= 0:
                    pdf.set_text_color(0, 0, 128) # Azul escuro tipo caneta BIC
                else:
                    pdf.set_text_color(255, 0, 0)  # Vermelho
                    
                pdf.cell(24, 8, f"R$ {soma_total:.2f}", 1, 0, "R", True)
                
                pdf.set_text_color(0, 0, 0)
                pdf.cell(159, 8, "", 1, 1, "C", True)
                
                pdf_bytes = pdf.output(dest='S').encode('latin1')
                st.success("PDF Financeiro ajustado com sucesso!")
                st.download_button(
                    label="📥 Baixar Arquivo PDF Financeiro Definitivo",
                    data=pdf_bytes,
                    file_name="Relatorio_Financeiro_Definitivo.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        with col_r2:
            # 2. RELATÓRIO DE MEMBROS / ATLETAS
            if st.button("📥 Gerar PDF: Relatório de Membros", use_container_width=True):
                data_hora_impressao = datetime.now().strftime("%d/%m/%Y - %H:%Mh")
                usuario_impressor = st.session_state.usuario
                
                pdf = PDFRelatorio("RELATÓRIO DE MEMBROS E ATLETAS - UNIÃO ITAPURA F.C.")
                pdf.add_page(orientation='P') # Retrato
                
                # Cabeçalho de controle de impressão
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, f"IMPRESSÃO: {data_hora_impressao} - {usuario_impressor}", 0, 1, "R")
                pdf.ln(2)
                
                c = conn.cursor()
                query_pdf_membros = "SELECT * FROM atletas ORDER BY nome ASC"
                c.execute(query_pdf_membros)
                membros = c.fetchall()
                
                colunas = [desc[0] for desc in c.description]
                c.close()
                
                def get_val(linha, possiveis_nomes, padrao="-"):
                    for nome_col in possiveis_nomes:
                        if nome_col in colunas:
                            idx = colunas.index(nome_col)
                            val = linha[idx]
                            return str(val) if val is not None and str(val).strip() != "" else padrao
                    return padrao

                for m in membros:
                    reg_id = f"REG-{int(m[0]):04d}" if m[0] else "REG-0000"
                    nome = get_val(m, ['nome'], 'Sem Nome')
                    funcao = get_val(m, ['tipo', 'funcao', 'cargo'], 'Jogador')
                    status = get_val(m, ['status'], 'Ativo')
                    
                    # Puxa o campo 'documentos' unificado do banco de dados
                    documentos = get_val(m, ['documentos', 'rg', 'cpf'], '-')
                    
                    nasc = get_val(m, ['data_nascimento', 'nascimento'], '-')
                    posicao = get_val(m, ['posicao'], '-')
                    mae = get_val(m, ['nome_mae', 'mae'], '-')
                    tel = get_val(m, ['telefone', 'tel'], '-')
                    end = get_val(m, ['endereco'], '-')
                    cad_por = get_val(m, ['criado_por', 'cadastrado_por'], 'admin')
                    cad_data = get_val(m, ['data_criacao', 'data_cadastro'], '-')
                    
                    if pdf.get_y() > 255:
                        pdf.add_page(orientation='P')
                    
                    # Bloco Individual do Atleta (Card)
                    pdf.set_fill_color(245, 245, 245)
                    pdf.set_draw_color(200, 200, 200)
                    
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_text_color(0, 0, 128)
                    pdf.cell(190, 6, f"[{reg_id}] {nome} ({funcao}) - Status: {status}", 1, 1, "L", True)
                    
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(0, 0, 0)
                    
                    # Exibe o documento unificado preenchido corretamente
                    pdf.cell(95, 5, f"Documentos (RG/CPF): {documentos}", "LR", 0, "L")
                    pdf.cell(95, 5, f"Nascimento: {nasc} | Posição: {posicao}", "R", 1, "L")
                    
                    pdf.cell(95, 5, f"Mãe: {mae}", "LR", 0, "L")
                    pdf.cell(95, 5, f"Telefone / WhatsApp: {tel}", "R", 1, "L")
                    
                    pdf.cell(190, 5, f"Endereço: {end}", "LR", 1, "L")
                    
                    pdf.set_font("Helvetica", "I", 7)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(190, 5, f"Cadastrado por: {cad_por} em {cad_data}", "LBR", 1, "L", True)
                    
                    pdf.ln(3)
                
                pdf_bytes = pdf.output(dest='S').encode('latin1')
                st.success("PDF de Membros organizado com sucesso!")
                st.download_button(
                    label="⬇️ Baixar Arquivo PDF de Membros Organizado",
                    data=pdf_bytes,
                    file_name="Relatorio_Membros_Organizado.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        with col_r1:
            # 3. RELATÓRIO DE JOGOS / PARTIDAS
            if st.button("📥 Gerar PDF: Resumo de Jogos Completo", use_container_width=True):
                data_hora_impressao = datetime.now().strftime("%d/%m/%Y - %H:%Mh")
                usuario_impressor = st.session_state.usuario
                
                pdf = PDFRelatorio("RELATÓRIO DE PARTIDAS & JOGOS - UNIÃO ITAPURA F.C.")
                pdf.add_page(orientation='P') # Retrato
                
                # Cabeçalho de controle de impressão
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, f"IMPRESSÃO: {data_hora_impressao} - {usuario_impressor}", 0, 1, "R")
                pdf.ln(2)
                
                try:
                    conn.rollback()
                except:
                    pass
                
                cj = conn.cursor()
                # Puxa os jogos usando exatamente os nomes reais das colunas da sua tabela 'jogos'
                cj.execute("SELECT id, data, adversario, local, placar_uniao, placar_adv, resultado FROM jogos ORDER BY id DESC")
                jogos = cj.fetchall()
                
                if jogos:
                    for j in jogos:
                        jid = j[0]
                        dt_jogo = str(j[1] or "Data não informada")
                        adversario = str(j[2] or "Jogo Oficial")
                        gp = int(j[4] if j[4] is not None else 0)
                        gc = int(j[5] if j[5] is not None else 0)
                        res_db = str(j[6] or "")
                        
                        # Determina resultado e texto do placar
                        if not res_db:
                            if gp > gc: res_db = "Vitória"
                            elif gp == gc: res_db = "Empate"
                            else: res_db = "Derrota"
                            
                        placar_str = f"UNIÃO {gp} x {gc} {adversario} ({res_db})"
                        
                        # Busca os Gols e Assistências (Scouts) deste jogo específico
                        cj.execute("""
                            SELECT a.nome, s.gols, s.assistencias 
                            FROM scouts s 
                            JOIN atletas a ON s.atleta_id = a.id 
                            WHERE s.jogo_id = %s AND (s.gols > 0 OR s.assistencias > 0)
                            ORDER BY s.gols DESC, a.nome ASC
                        """, (jid,))
                        scouts_jogo = cj.fetchall()
                        
                        gols_det_linhas = []
                        if scouts_jogo:
                            for sg in scouts_jogo:
                                nome_atleta = sg[0]
                                q_gols = sg[1] or 0
                                q_assists = sg[2] or 0
                                gols_det_linhas.append(f"- {nome_atleta}: {q_gols} Gols e {q_assists} Assistências")
                        
                        # Busca os Atletas Presentes na Súmula deste jogo
                        cj.execute("""
                            SELECT a.nome 
                            FROM presencas p 
                            JOIN atletas a ON p.atleta_id = a.id 
                            WHERE p.jogo_id = %s AND p.presenca = 1 
                            ORDER BY a.nome ASC
                        """, (jid,))
                        presencas_jogo = cj.fetchall()
                        
                        lista_presencas = [p[0] for p in presencas_jogo]
                        presencas_str = ", ".join(lista_presencas) if lista_presencas else "Nenhuma presença registrada."
                        
                        if pdf.get_y() > 230:
                            pdf.add_page(orientation='P')
                        
                        # Bloco / Card da Partida (Padrão de cores idêntico ao de Membros)
                        pdf.set_fill_color(245, 245, 245)
                        pdf.set_draw_color(200, 200, 200)
                        
                        # Cabeçalho do Card (Azul Escuro)
                        pdf.set_font("Helvetica", "B", 9)
                        pdf.set_text_color(0, 0, 128)
                        pdf.cell(190, 6, f"  DATA: {dt_jogo} | {placar_str}", 1, 1, "L", True)
                        
                        # Comissão Técnica fixa ou padrão do clube
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_text_color(50, 50, 50)
                        pdf.cell(190, 5, "  Comissão Técnica (Técnico): Edenicio Lopes Feitosa", "LR", 1, "L")
                        
                        # Gols e Assistências
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_text_color(0, 0, 0)
                        pdf.cell(190, 5, "  Gols e Assistências:", "LR", 1, "L")
                        
                        pdf.set_font("Helvetica", "", 8)
                        if gols_det_linhas:
                            for linha_g in gols_det_linhas:
                                pdf.cell(190, 4.5, f"    {linha_g}", "LR", 1, "L")
                        else:
                            pdf.cell(190, 4.5, "    Nenhum detalhe de gols registrado.", "LR", 1, "L")
                        
                        # Presenças em Campo
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.cell(190, 5, "  Presenças em Campo:", "LR", 1, "L")
                        
                        pdf.set_font("Helvetica", "", 7.5)
                        pdf.multi_cell(190, 4.5, f"    {presencas_str}", "LR", "L")
                        
                        # Rodapé do Card do Jogo
                        pdf.set_font("Helvetica", "I", 7)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(190, 5, "  Ficha técnica validada pelo sistema do clube", "LBR", 1, "L", True)
                        
                        pdf.ln(4)
                else:
                    pdf.set_font("Helvetica", "", 9)
                    pdf.cell(190, 10, "Nenhuma partida registrada no sistema até o momento.", 1, 1, "C")
                
                cj.close()

                pdf_bytes = pdf.output(dest='S').encode('latin1')
                st.success("Relatório de Jogos organizado com sucesso!")
                st.download_button(
                    label="📥 Baixar Arquivo PDF: Relatório de Jogos Organizado",
                    data=pdf_bytes,
                    file_name="Relatorio_Jogos_Organizado.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        with col_r2:
            # 4. RESUMO GERAL CONSOLIDADO COMPLETO
            if st.button("📥 Gerar PDF: Resumo Geral Consolidado Completo", use_container_width=True):
                data_hora_impressao = datetime.now().strftime("%d/%m/%Y - %H:%Mh")
                usuario_impressor = st.session_state.usuario
                
                pdf = PDFRelatorio("RELATÓRIO DE RESUMO GERAL & CONSOLIDADO - UNIÃO ITAPURA F.C.")
                pdf.add_page(orientation='P') # Retrato
                
                # Cabeçalho de controle de impressão
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, f"IMPRESSÃO: {data_hora_impressao} - {usuario_impressor}", 0, 1, "R")
                pdf.ln(2)
                
                try:
                    conn.rollback()
                except:
                    pass
                
                # 1. Coleta de Dados para o Painel Executivo
                c1 = conn.cursor()
                c1.execute("SELECT COUNT(*) FROM atletas WHERE status = 'Ativo' OR status IS NULL")
                total_ativos = c1.fetchone()[0] or 0
                c1.close()
                
                c2 = conn.cursor()
                c2.execute("SELECT SUM(valor) FROM financeiro")
                res_caixa = c2.fetchone()[0]
                saldo_caixa = float(res_caixa) if res_caixa else 0.0
                c2.close()
                
                try:
                    c3 = conn.cursor()
                    c3.execute("SELECT COUNT(*), SUM(CASE WHEN resultado = 'Vitória' THEN 1 ELSE 0 END), SUM(CASE WHEN resultado = 'Empate' THEN 1 ELSE 0 END), SUM(CASE WHEN resultado = 'Derrota' THEN 1 ELSE 0 END) FROM jogos")
                    j_info = c3.fetchone()
                    total_jogos = j_info[0] or 0
                    vitorias = j_info[1] or 0
                    empates = j_info[2] or 0
                    derrotas = j_info[3] or 0
                    c3.close()
                except:
                    total_jogos, vitorias, empates, derrotas = 0, 0, 0, 0

                # --- SEÇÃO 1: PAINEL EXECUTIVO & GRÁFICO DE INDICADORES ---
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_text_color(0, 0, 128)
                pdf.cell(190, 6, "  1. PAINEL EXECUTIVO & INDICADORES DO CLUBE", 1, 1, "L", True)
                
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(0, 0, 0)
                
                pdf.cell(95, 6, f"   Membros Ativos: {total_ativos}", "LR", 0, "L")
                saldo_cor_str = f"R$ {saldo_caixa:.2f}"
                pdf.cell(95, 6, f"   Saldo Total em Caixa: {saldo_cor_str}", "R", 1, "L")
                
                # Bloco Gráfico / Indicadores de Desempenho do Time (Usando caracteres seguros para latin-1)
                barra_v = "X" * vitorias if vitorias > 0 else "-"
                barra_e = "X" * empates if empates > 0 else "-"
                barra_d = "X" * derrotas if derrotas > 0 else "-"
                
                pdf.cell(190, 6, f"   Desempenho em Campo -> Jogos: {total_jogos} | Vitórias: {vitorias} [{barra_v}] | Empates: {empates} [{barra_e}] | Derrotas: {derrotas} [{barra_d}]", "LBR", 1, "L")
                pdf.ln(4)

                # --- SEÇÃO 2: RESUMO DOS JOGOS ---
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_text_color(0, 0, 128)
                pdf.cell(190, 6, "  2. RESUMO DE PARTIDAS E JOGOS", 1, 1, "L", True)
                
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(220, 220, 220)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(25, 6, "DATA", 1, 0, "C", True)
                pdf.cell(85, 6, "ADVERSÁRIO / CAMPO", 1, 0, "L", True)
                pdf.cell(40, 6, "PLACAR", 1, 0, "C", True)
                pdf.cell(40, 6, "RESULTADO", 1, 1, "C", True)
                
                ultimos_jogos = []
                try:
                    conn.rollback()
                    c4 = conn.cursor()
                    c4.execute("SELECT * FROM jogos ORDER BY id DESC LIMIT 5")
                    j_rows = c4.fetchall()
                    j_cols = [desc[0] for desc in c4.description]
                    c4.close()
                    
                    for row in j_rows:
                        ultimos_jogos.append(dict(zip(j_cols, row)))
                except Exception as e:
                    conn.rollback()
                    ultimos_jogos = []
                
                pdf.set_font("Helvetica", "", 8)
                if ultimos_jogos:
                    for j in ultimos_jogos:
                        dt_j = str(j.get('data') or "")
                        adv_j = str(j.get('adversario') or j.get('rival') or "Jogo Oficial")
                        
                        gp = int(j.get('placar_uniao') or j.get('gols_pro') or 0)
                        gc = int(j.get('placar_adv') or j.get('gols_contra') or 0)
                        
                        res = str(j.get('resultado') or "")
                        if not res:
                            if gp > gc: res = "Vitória"
                            elif gp == gc: res = "Empate"
                            else: res = "Derrota"
                            
                        placar = f"{gp} x {gc}"
                        
                        pdf.cell(25, 5.5, dt_j, 1, 0, "C")
                        pdf.cell(85, 5.5, adv_j[:45], 1, 0, "L")
                        pdf.cell(40, 5.5, placar, 1, 0, "C")
                        pdf.cell(40, 5.5, res, 1, 1, "C")
                else:
                    pdf.cell(190, 6, "Nenhuma partida registrada no sistema até o momento.", 1, 1, "C")
                
                pdf.ln(4)

                # --- SEÇÃO 3: RELAÇÃO DE MEMBROS ---
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_text_color(0, 0, 128)
                pdf.cell(190, 6, "  3. RELAÇÃO DE MEMBROS CADASTRADOS", 1, 1, "L", True)
                
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(220, 220, 220)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(25, 6, "REGISTRO", 1, 0, "C", True)
                pdf.cell(85, 6, "NOME COMPLETO", 1, 0, "L", True)
                pdf.cell(40, 6, "STATUS", 1, 0, "C", True)
                pdf.cell(40, 6, "POSIÇÃO", 1, 1, "C", True)
                
                c5 = conn.cursor()
                c5.execute("SELECT id, nome, status, posicao FROM atletas ORDER BY nome ASC")
                membros = c5.fetchall()
                c5.close()
                
                pdf.set_font("Helvetica", "", 8)
                for m in membros:
                    reg = f"REG-{int(m[0]):04d}" if m[0] else "REG-0000"
                    nome_m = str(m[1] or "-")
                    status_m = str(m[2] or "Ativo")
                    pos = str(m[3] or "N/A")
                    
                    if pdf.get_y() > 265:
                        pdf.add_page(orientation='P')
                        
                    pdf.cell(25, 5.5, reg, 1, 0, "C")
                    pdf.cell(85, 5.5, nome_m[:45], 1, 0, "L")
                    pdf.cell(40, 5.5, status_m, 1, 0, "C")
                    pdf.cell(40, 5.5, pos, 1, 1, "C")
                
                pdf.ln(4)

                # --- SEÇÃO 4: ÚLTIMAS MOVIMENTAÇÕES FINANCEIRAS ---
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_text_color(0, 0, 128)
                pdf.cell(190, 6, "  4. ÚLTIMAS MOVIMENTAÇÕES FINANCEIRAS", 1, 1, "L", True)
                
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(220, 220, 220)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(25, 6, "DATA", 1, 0, "C", True)
                pdf.cell(35, 6, "CATEGORIA", 1, 0, "C", True)
                pdf.cell(95, 6, "REFERÊNCIA / OBSERVAÇÃO", 1, 0, "L", True)
                pdf.cell(35, 6, "VALOR (R$)", 1, 1, "R", True)
                
                c6 = conn.cursor()
                c6.execute("SELECT data, tipo, referencia, valor, observacao FROM financeiro ORDER BY id DESC LIMIT 10")
                ultimos_fin = c6.fetchall()
                c6.close()
                
                pdf.set_font("Helvetica", "", 7.5)
                for f in ultimos_fin:
                    dt_f = str(f[0] or "")
                    tp_f = str(f[1] or "")
                    ref_f = str(f[2] or f[4] or "-")
                    val_f = float(f[3] or 0.0)
                    
                    if pdf.get_y() > 265:
                        pdf.add_page(orientation='P')
                        
                    pdf.cell(25, 5, dt_f, 1, 0, "C")
                    pdf.cell(35, 5, tp_f, 1, 0, "L")
                    pdf.cell(95, 5, ref_f[:55], 1, 0, "L")
                    pdf.cell(35, 5, f"R$ {val_f:.2f}", 1, 1, "R")

                pdf_bytes = pdf.output(dest='S').encode('latin1')
                st.success("Resumo Geral Consolidado gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Arquivo PDF: Resumo Geral Consolidado",
                    data=pdf_bytes,
                    file_name="Resumo_Geral_Consolidado.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

conn.close()
