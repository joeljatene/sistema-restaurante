import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime, date
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema Restaurante", layout="wide", page_icon="🍽️")

# --- 2. CLASSE PARA GERAR O PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatorio de Estoque - Restaurante', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def gerar_pdf(df):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(200, 220, 255)
    cols = [("Produto", 60), ("Qtd", 25), ("Unid", 20), ("Validade", 30), ("Total R$", 35)]
    for col, width in cols:
        pdf.cell(width, 10, col, 1, 0, 'C', 1)
    pdf.ln()
    
    # Dados
    total_geral = 0
    for _, row in df.iterrows():
        # Limpeza básica de caracteres para o PDF não quebrar com acentos
        nome = str(row['nome']).encode('latin-1', 'replace').decode('latin-1')
        total_item = row['qtd_atual'] * row['preco_medio']
        total_geral += total_item
        
        pdf.cell(60, 10, nome, 1)
        pdf.cell(25, 10, f"{row['qtd_atual']:.2f}", 1, 0, 'C')
        pdf.cell(20, 10, str(row['unidade']), 1, 0, 'C')
        pdf.cell(30, 10, str(row['validade']), 1, 0, 'C')
        pdf.cell(35, 10, f"{total_item:.2f}", 1, 1, 'R')
        
    # Total
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"VALOR TOTAL EM ESTOQUE: R$ {total_geral:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. CONEXÃO COM GITHUB (DB) ---
def get_repo():
    token = st.secrets["GITHUB_TOKEN"]
    path = st.secrets["REPO_PATH"]
    g = Github(token)
    return g.get_repo(path)

def carregar_dados(arquivo):
    try:
        repo = get_repo()
        contents = repo.get_contents(arquivo)
        dados = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(dados))
    except:
        return pd.DataFrame()

def salvar_dados(arquivo, df, mensagem):
    repo = get_repo()
    try:
        contents = repo.get_contents(arquivo)
        repo.update_file(contents.path, mensagem, df.to_csv(index=False), contents.sha)
    except:
        repo.create_file(arquivo, mensagem, df.to_csv(index=False))

# --- 4. SISTEMA DE LOGIN ---
def login():
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False
        
    if not st.session_state['logado']:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Acesso Restrito")
            senha = st.text_input("Senha:", type="password")
            if st.button("Entrar"):
                if senha == "admin123": # <--- SUA SENHA AQUI
                    st.session_state['logado'] = True
                    st.rerun()
                else:
                    st.error("Senha Incorreta")
        return False
    return True

# --- 5. APLICAÇÃO PRINCIPAL ---
if login():
    # Carregamento Inicial
    if 'df_produtos' not in st.session_state:
        st.session_state['df_produtos'] = carregar_dados("estoque.csv")
    if 'df_historico' not in st.session_state:
        st.session_state['df_historico'] = carregar_dados("historico.csv")
        
    # Sidebar
    st.sidebar.title("🥘 Gestão Joel")
    menu = st.sidebar.radio("Menu", ["Dashboard & Financeiro", "Movimentação", "Cadastrar/Excluir", "Relatórios PDF"])
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()
        
    # --- ABA 1: DASHBOARD ---
    if menu == "Dashboard & Financeiro":
        st.title("📊 Visão Geral")
        df = st.session_state['df_produtos']
        if not df.empty:
            df['total'] = df['qtd_atual'] * df['preco_medio']
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Produtos", len(df))
            c2.metric("Valor em Estoque", f"R$ {df['total'].sum():,.2f}")
            
            # Validade
            hoje = date.today()
            df['validade_dt'] = pd.to_datetime(df['validade'], errors='coerce').dt.date
            vencidos = len(df[df['validade_dt'] < hoje])
            c3.metric("⚠️ Vencidos", vencidos, delta_color="inverse")
            
            st.dataframe(df[['nome', 'qtd_atual', 'unidade', 'validade', 'total']], use_container_width=True)
        else:
            st.warning("Nenhum dado. Cadastre produtos.")

    # --- ABA 2: MOVIMENTAÇÃO ---
    elif menu == "Movimentação":
        st.title("🔄 Entrada e Saída")
        df = st.session_state['df_produtos']
        if not df.empty:
            escolha = st.selectbox("Produto:", df['nome'] + " (ID: " + df['id'].astype(str) + ")")
            id_sel = int(escolha.split("ID: ")[1].replace(")", ""))
            idx = df.index[df['id'] == id_sel].tolist()[0]
            item = df.loc[idx]
            
            st.info(f"Atual: {item['qtd_atual']} {item['unidade']} | Validade: {item['validade']}")
            
            c1, c2 = st.columns(2)
            tipo = c1.radio("Ação", ["Saída", "Entrada"])
            qtd = c2.number_input("Quantidade", min_value=0.1)
            
            if st.button("Confirmar"):
                if tipo == "Saída":
                    st.session_state['df_produtos'].at[idx, 'qtd_atual'] -= qtd
                else:
                    st.session_state['df_produtos'].at[idx, 'qtd_atual'] += qtd
                
                # Salva
                with st.spinner("Salvando..."):
                    salvar_dados("estoque.csv", st.session_state['df_produtos'], f"{tipo}: {item['nome']}")
                st.success("Atualizado!")
                st.rerun()

    # --- ABA 3: CADASTRO ---
    elif menu == "Cadastrar/Excluir":
        tab1, tab2 = st.tabs(["Novo Item", "Excluir Item"])
        with tab1:
            with st.form("novo"):
                nome = st.text_input("Nome")
                un = st.selectbox("Unidade", ["kg", "un", "lt"])
                qtd = st.number_input("Qtd Inicial", min_value=0.0)
                preco = st.number_input("Preço Custo", min_value=0.0)
                validade = st.date_input("Validade")
                if st.form_submit_button("Salvar"):
                    df = st.session_state['df_produtos']
                    novo_id = 1 if df.empty else df['id'].max() + 1
                    novo = pd.DataFrame([{"id": novo_id, "nome": nome, "unidade": un, "qtd_atual": qtd, "qtd_minima": 10, "preco_medio": preco, "validade": validade}])
                    st.session_state['df_produtos'] = pd.concat([df, novo], ignore_index=True)
                    salvar_dados("estoque.csv", st.session_state['df_produtos'], "Cadastro")
                    st.success("Salvo!")
                    st.rerun()
        
        with tab2:
            df = st.session_state['df_produtos']
            if not df.empty:
                exc = st.selectbox("Excluir:", df['nome'])
                if st.button("Deletar"):
                    st.session_state['df_produtos'] = df[df['nome'] != exc]
                    salvar_dados("estoque.csv", st.session_state['df_produtos'], "Exclusão")
                    st.success("Deletado!")
                    st.rerun()

    # --- ABA 4: PDF ---
    elif menu == "Relatórios PDF":
        st.title("📄 Relatórios")
        df = st.session_state['df_produtos']
        if not df.empty:
            pdf_data = gerar_pdf(df)
            st.download_button("Baixar PDF", data=pdf_data, file_name="estoque.pdf", mime="application/pdf")
