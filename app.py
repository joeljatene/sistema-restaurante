import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime, date
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Restaurante V4", layout="wide", page_icon="🛡️")

# --- 2. CLASSE PARA PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatorio de Estoque e Auditoria', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def gerar_pdf(df):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    pdf.set_fill_color(200, 220, 255)
    cols = [("Produto", 60), ("Qtd", 25), ("Unid", 20), ("Validade", 30), ("Total R$", 35)]
    for col, width in cols:
        pdf.cell(width, 10, col, 1, 0, 'C', 1)
    pdf.ln()
    
    total_geral = 0
    for _, row in df.iterrows():
        nome = str(row['nome']).encode('latin-1', 'replace').decode('latin-1')
        total_item = row['qtd_atual'] * row['preco_medio']
        total_geral += total_item
        
        pdf.cell(60, 10, nome, 1)
        pdf.cell(25, 10, f"{row['qtd_atual']:.2f}", 1, 0, 'C')
        pdf.cell(20, 10, str(row['unidade']), 1, 0, 'C')
        pdf.cell(30, 10, str(row['validade']), 1, 0, 'C')
        pdf.cell(35, 10, f"{total_item:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"VALOR TOTAL: R$ {total_geral:,.2f}", 0, 1, 'R')
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
            st.title("🔐 Acesso Seguro")
            st.info("Seus dados estão protegidos. Faça login para continuar.")
            senha = st.text_input("Senha de Acesso:", type="password")
            if st.button("Acessar Sistema", type="primary"):
                if senha == "admin123": # <--- SUA SENHA
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

    # Menu
    st.sidebar.title("🥘 Gestão Joel V4")
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("Navegação", 
        ["🚨 Dashboard & Alertas", 
         "🔄 Movimentação", 
         "📝 Cadastrar/Excluir", 
         "📜 Histórico Completo", 
         "📄 Relatórios PDF"])
    
    if st.sidebar.button("Sair (Logout)"):
        st.session_state['logado'] = False
        st.rerun()

    # --- ABA 1: DASHBOARD (COM ALERTA) ---
    if menu == "🚨 Dashboard & Alertas":
        st.title("Visão Geral do Estoque")
        df = st.session_state['df_produtos']
        
        if not df.empty:
            # Cálculos
            df['total'] = df['qtd_atual'] * df['preco_medio']
            
            # --- ALERTA DE REPOSIÇÃO (O que você pediu) ---
            repor = df[df['qtd_atual'] <= df['qtd_minima']]
            
            if not repor.empty:
                st.error(f"🚨 ATENÇÃO: {len(repor)} PRODUTOS PRECISAM DE REPOSIÇÃO IMEDIATA!")
                st.write("Lista de compras urgente:")
                # Mostra tabela vermelha
                st.dataframe(
                    repor[['nome', 'qtd_atual', 'qtd_minima', 'unidade']], 
                    use_container_width=True
                )
            else:
                st.success("✅ Estoque em dia! Nenhum item abaixo do mínimo.")
            
            st.divider()
            
            # Cards Informativos
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Itens", len(df))
            c2.metric("Valor Patrimonial", f"R$ {df['total'].sum():,.2f}")
            
            hoje = date.today()
            df['validade_dt'] = pd.to_datetime(df['validade'], errors='coerce').dt.date
            vencidos = len(df[df['validade_dt'] < hoje])
            c3.metric("⚠️ Produtos Vencidos", vencidos, delta_color="inverse")

            st.subheader("Estoque Geral")
            st.dataframe(df[['nome', 'qtd_atual', 'unidade', 'validade', 'total']], use_container_width=True)
            
        else:
            st.warning("Nenhum dado encontrado.")

    # --- ABA 2: MOVIMENTAÇÃO (GRAVA NO HISTÓRICO) ---
    elif menu == "🔄 Movimentação":
        st.title("Registrar Entrada/Saída")
        df = st.session_state['df_produtos']
        
        if not df.empty:
            escolha = st.selectbox("Selecione o Produto:", df['nome'] + " (ID: " + df['id'].astype(str) + ")")
            id_sel = int(escolha.split("ID: ")[1].replace(")", ""))
            idx = df.index[df['id'] == id_sel].tolist()[0]
            item = df.loc[idx]
            
            st.info(f"Produto: **{item['nome']}** | Atual: {item['qtd_atual']} {item['unidade']}")
            
            with st.form("mov"):
                c1, c2 = st.columns(2)
                tipo = c1.radio("Operação", ["Saída (Uso)", "Entrada (Compra)"])
                qtd = c2.number_input("Quantidade", min_value=0.1)
                obs = st.text_input("Observação (Quem pegou? Motivo?)")
                
                if st.form_submit_button("Confirmar e Salvar"):
                    # 1. Atualiza Estoque
                    qtd_antiga = item['qtd_atual']
                    if "Saída" in tipo:
                        nova_qtd = qtd_antiga - qtd
                        tipo_txt = "Saída"
                    else:
                        nova_qtd = qtd_antiga + qtd
                        tipo_txt = "Entrada"
                    
                    st.session_state['df_produtos'].at[idx, 'qtd_atual'] = nova_qtd
                    
                    # 2. Grava no Histórico (Segurança do registro)
                    novo_hist = pd.DataFrame([{
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "produto": item['nome'],
                        "tipo": tipo_txt,
                        "quantidade": qtd,
                        "saldo_anterior": qtd_antiga,
                        "saldo_novo": nova_qtd,
                        "obs": obs
                    }])
                    
                    # Concatena com o histórico existente
                    if st.session_state['df_historico'].empty:
                         st.session_state['df_historico'] = novo_hist
                    else:
                         st.session_state['df_historico'] = pd.concat([novo_hist, st.session_state['df_historico']], ignore_index=True)

                    # 3. Salva no GitHub (Os 2 arquivos)
                    with st.spinner("Salvando alterações..."):
                        salvar_dados("estoque.csv", st.session_state['df_produtos'], f"Upd: {item['nome']}")
                        salvar_dados("historico.csv", st.session_state['df_historico'], "Log Historico")
                    
                    st.success("✅ Movimentação registrada com sucesso!")
                    st.rerun()

    # --- ABA 3: CADASTRO ---
    elif menu == "📝 Cadastrar/Excluir":
        tab1, tab2 = st.tabs(["Novo Item", "Excluir"])
        with tab1:
            with st.form("novo"):
                nome = st.text_input("Nome")
                un = st.selectbox("Unidade", ["kg", "un", "lt", "cx"])
                qtd = st.number_input("Qtd Inicial", min_value=0.0)
                minimo = st.number_input("Estoque Mínimo (Para Alerta)", min_value=0.0)
                preco = st.number_input("Preço Custo", min_value=0.0)
                validade = st.date_input("Validade")
                
                if st.form_submit_button("Salvar"):
                    df = st.session_state['df_produtos']
                    novo_id = 1 if df.empty else df['id'].max() + 1
                    novo = pd.DataFrame([{
                        "id": novo_id, "nome": nome, "unidade": un, 
                        "qtd_atual": qtd, "qtd_minima": minimo, 
                        "preco_medio": preco, "validade": validade
                    }])
                    st.session_state['df_produtos'] = pd.concat([df, novo], ignore_index=True)
                    salvar_dados("estoque.csv", st.session_state['df_produtos'], "Cadastro")
                    st.success("Cadastrado!")
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

    # --- ABA 4: HISTÓRICO (AUDITORIA) ---
    elif menu == "📜 Histórico Completo":
        st.title("Auditoria de Movimentações")
        st.info("Aqui fica registrado tudo que acontece no sistema.")
        
        hist = st.session_state['df_historico']
        if not hist.empty:
            st.dataframe(hist, use_container_width=True)
        else:
            st.warning("Nenhuma movimentação registrada ainda.")

    # --- ABA 5: PDF ---
    elif menu == "📄 Relatórios PDF":
        st.title("Imprimir Relatórios")
        df = st.session_state['df_produtos']
        if not df.empty:
            pdf_data = gerar_pdf(df)
            st.download_button("📥 Baixar PDF do Estoque", data=pdf_data, file_name="estoque.pdf", mime="application/pdf")
