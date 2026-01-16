import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime, date
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Restaurante V6.2", layout="wide", page_icon="🥘")

# --- 2. FUNÇÕES PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatorio Geral de Estoque', 0, 1, 'C')
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
    cols = [("Produto", 60), ("Qtd", 25), ("Un", 15), ("Validade", 25), ("Total R$", 30), ("Status", 35)]
    for col, width in cols:
        pdf.cell(width, 10, col, 1, 0, 'C', 1)
    pdf.ln()
    
    # Dados
    total_geral = 0
    for _, row in df.iterrows():
        nome = str(row['nome']).encode('latin-1', 'replace').decode('latin-1')
        try:
            status_calc = "OK"
            if row['qtd_atual'] <= row['qtd_minima']:
                status_calc = "REPOR"
        except:
            status_calc = "-"
            
        total_item = row['qtd_atual'] * row['preco_medio']
        total_geral += total_item
        
        pdf.cell(60, 10, nome, 1)
        pdf.cell(25, 10, f"{row['qtd_atual']:.2f}", 1, 0, 'C')
        pdf.cell(15, 10, str(row['unidade']), 1, 0, 'C')
        pdf.cell(25, 10, str(row['validade']), 1, 0, 'C')
        pdf.cell(30, 10, f"{total_item:.2f}", 1, 0, 'R')
        pdf.cell(35, 10, status_calc, 1, 1, 'C')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"VALOR TOTAL EM ESTOQUE: R$ {total_geral:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. CONEXÃO GITHUB ---
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

# --- 4. LOGIN ---
def login():
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False
    if not st.session_state['logado']:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Acesso Gestão")
            senha = st.text_input("Senha:", type="password")
            if st.button("Entrar", type="primary"):
                if senha == "admin123": 
                    st.session_state['logado'] = True
                    st.rerun()
                else:
                    st.error("Senha Incorreta")
        return False
    return True

# --- 5. APP PRINCIPAL ---
if login():
    # Carrega tabelas
    if 'df_produtos' not in st.session_state:
        st.session_state['df_produtos'] = carregar_dados("estoque.csv")
    if 'df_historico' not in st.session_state:
        st.session_state['df_historico'] = carregar_dados("historico.csv")
    if 'df_fichas' not in st.session_state:
        st.session_state['df_fichas'] = carregar_dados("fichas.csv")
    if 'df_fornecedores' not in st.session_state:
        st.session_state['df_fornecedores'] = carregar_dados("fornecedores.csv")

    # Menu Lateral
    st.sidebar.title("🥘 Bem Caseiro")
    
    menu = st.sidebar.radio("Menu", 
        ["🚨 Dashboard", 
         "🔄 Movimentação", 
         "🚚 Fornecedores", 
         "👨‍🍳 Fichas & Cardápios", 
         "📝 Estoque (Cadastro)", 
         "📜 Histórico",
         "📄 Relatórios PDF"])
    
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    # --- ABA 1: DASHBOARD ---
    if menu == "🚨 Dashboard":
        st.header("Visão Geral")
        df = st.session_state['df_produtos']
        if not df.empty:
            repor = df[df['qtd_atual'] <= df['qtd_minima']]
            if not repor.empty:
                st.error("🚨 ESTOQUE MÍNIMO ATINGIDO:")
                st.dataframe(repor[['nome', 'qtd_atual', 'qtd_minima']])
            
            c1, c2 = st.columns(2)
            df['total'] = df['qtd_atual'] * df['preco_medio']
            c1.metric("Produtos", len(df))
            c2.metric("Valor Financeiro", f"R$ {df['total'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)

    # --- ABA 2: MOVIMENTAÇÃO ---
    elif menu == "🔄 Movimentação":
        st.header("Entrada / Saída")
        df = st.session_state['df_produtos']
        df_forn = st.session_state['df_fornecedores']
        
        if not df.empty:
            sel = st.selectbox("Produto:", df['nome'])
            idx = df.index[df['nome'] == sel].tolist()[0]
            item = df.loc[idx]
            st.info(f"Atual: {item['qtd_atual']} {item['unidade']} | Custo Médio: R$ {item['preco_medio']:.2f}")
            
            with st.form("mov_form"):
                c1, c2 = st.columns(2)
                tipo = c1.radio("Ação", ["Entrada (Compra)", "Saída (Uso)"])
                qtd = c2.number_input("Qtd", min_value=0.1)
                
                st.markdown("---")
                st.write("📦 Detalhes da Aquisição")
                
                lista_forn = ["Sem Fornecedor / Interno"] + df_forn['nome'].tolist() if not df_forn.empty else ["Cadastre Fornecedores Primeiro"]
                fornecedor = st.selectbox("Fornecedor:", lista_forn)
                preco_aq = st.number_input("Preço de Aquisição/Custo (R$)", min_value=0.0, value=float(item['preco_medio']))
                obs = st.text_input("Observação")
                
                if st.form_submit_button("Confirmar Movimentação"):
                    antigo = item['qtd_atual']
                    
                    if "Entrada" in tipo:
                        novo_estoque = antigo + qtd
                        novo_preco = preco_aq if preco_aq > 0 else item['preco_medio']
                        st.session_state['df_produtos'].at[idx, 'qtd_atual'] = novo_estoque
                        st.session_state['df_produtos'].at[idx, 'preco_medio'] = novo_preco
                        tipo_reg = "Entrada"
                    else:
                        novo_estoque = antigo - qtd
                        st.session_state['df_produtos'].at[idx, 'qtd_atual'] = novo_estoque
                        tipo_reg = "Saída"

                    hist_entry = pd.DataFrame([{
                        "data": datetime.now().strftime("%d/%m %H:%M"),
                        "produto": item['nome'],
                        "tipo": tipo_reg,
                        "quantidade": qtd,
                        "saldo_anterior": antigo,
                        "saldo_novo": novo_estoque,
                        "fornecedor": fornecedor,
                        "preco_aquisicao": preco_aq,
                        "obs": obs
                    }])
                    
                    st.session_state['df_historico'] = pd.concat([hist_entry, st.session_state['df_historico']], ignore_index=True)
                    
                    with st.spinner("Salvando..."):
                        salvar_dados("estoque.csv", st.session_state['df_produtos'], f"Mov: {tipo_reg} {item['nome']}")
                        salvar_dados("historico.csv", st.session_state['df_historico'], "Log Histórico")
                    
                    st.success("Registrado com sucesso!")
                    st.rerun()

    # --- ABA 3: FORNECEDORES ---
    elif menu == "🚚 Fornecedores":
        st.header("Gerenciar Fornecedores")
        tab1, tab2 = st.tabs(["Novo Fornecedor", "Lista Cadastrada"])
        
        with tab1:
            with st.form("form_forn"):
                nome_forn = st.text_input("Nome da Empresa")
                contato = st.text_input("Contato")
                obs_forn = st.text_input("Obs")
                if st.form_submit_button("Salvar Fornecedor"):
                    df = st.session_state['df_fornecedores']
                    novo_id = 1 if df.empty else df['id'].max() + 1
                    novo = pd.DataFrame([{"id": novo_id, "nome": nome_forn, "contato": contato, "obs": obs_forn}])
                    df_final = pd.concat([df, novo], ignore_index=True)
                    st.session_state['df_fornecedores'] = df_final
                    salvar_dados("fornecedores.csv", df_final, f"Novo Fornecedor: {nome_forn}")
                    st.success("Salvo!")
                    st.rerun()
        with tab2:
            st.dataframe(st.session_state['df_fornecedores'], use_container_width=True)
            if not st.session_state['df_fornecedores'].empty:
                f_exc = st.selectbox("Excluir:", st.session_state['df_fornecedores']['nome'])
                if st.button("🗑️ Excluir"):
                    df = st.session_state['df_fornecedores']
                    df = df[df['nome'] != f_exc]
                    st.session_state['df_fornecedores'] = df
                    salvar_dados("fornecedores.csv", df, "Exclusão Fornecedor")
                    st.success("Excluído.")
                    st.rerun()

    # --- ABA 4: FICHAS TÉCNICAS (COM A NOVA LISTA) ---
    elif menu == "👨‍🍳 Fichas & Cardápios":
        st.title("Planejamento de Cardápio")
        
        # AQUI FOI ADICIONADA A TERCEIRA ABA "📖 Lista de Receitas"
        tab_conferir, tab_cadastro, tab_lista = st.tabs(["✅ Conferir Estoque", "📝 Cadastrar Receitas", "📖 Lista de Receitas"])
        
        with tab_conferir:
            opcao_cardapio = st.selectbox("Escolha o Cardápio:", ["Cardápio
