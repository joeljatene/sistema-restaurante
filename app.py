import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime, date
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Restaurante V6", layout="wide", page_icon="🚚")

# --- 2. FUNÇÕES PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatorio de Estoque e Compras', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def gerar_pdf(df):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    # Cabeçalho
    pdf.set_fill_color(200, 220, 255)
    cols = [("Produto", 60), ("Qtd Atual", 30), ("Status", 40), ("A Comprar", 30)]
    for col, width in cols:
        pdf.cell(width, 10, col, 1, 0, 'C', 1)
    pdf.ln()
    # Dados
    for _, row in df.iterrows():
        nome = str(row['nome']).encode('latin-1', 'replace').decode('latin-1')
        status = str(row['status']).encode('latin-1', 'replace').decode('latin-1')
        comprar = f"{row['comprar']:.2f}" if row['comprar'] > 0 else "-"
        
        pdf.cell(60, 10, nome, 1)
        pdf.cell(30, 10, f"{row['qtd_atual']:.2f}", 1, 0, 'C')
        pdf.cell(40, 10, status, 1, 0, 'C')
        pdf.cell(30, 10, comprar, 1, 1, 'C')
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
    st.sidebar.title("🥘 Joel Gastronomia")
    menu = st.sidebar.radio("Menu", 
        ["🚨 Dashboard", 
         "🔄 Movimentação", 
         "🚚 Fornecedores", # NOVO
         "👨‍🍳 Fichas & Cardápios", 
         "📝 Estoque (Cadastro)", 
         "📜 Histórico"])
    
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

    # --- ABA 2: MOVIMENTAÇÃO (COM FORNECEDOR E PREÇO) ---
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
                st.write("📦 Detalhes da Aquisição (Opcional para Saídas)")
                
                # Lista de Fornecedores
                lista_forn = ["Sem Fornecedor / Interno"] + df_forn['nome'].tolist() if not df_forn.empty else ["Cadastre Fornecedores Primeiro"]
                fornecedor = st.selectbox("Fornecedor:", lista_forn)
                
                # Preço de Aquisição (Sugere o atual)
                preco_aq = st.number_input("Preço de Aquisição/Custo (R$)", min_value=0.0, value=float(item['preco_medio']))
                
                obs = st.text_input("Observação (NF, Lote, Motivo)")
                
                if st.form_submit_button("Confirmar Movimentação"):
                    antigo = item['qtd_atual']
                    
                    # Lógica de Entrada
                    if "Entrada" in tipo:
                        novo_estoque = antigo + qtd
                        # Atualiza preço médio (opcional, mas recomendado manter o último pago ou média ponderada)
                        # Aqui vamos atualizar para o preço pago agora se for diferente de zero
                        novo_preco = preco_aq if preco_aq > 0 else item['preco_medio']
                        
                        st.session_state['df_produtos'].at[idx, 'qtd_atual'] = novo_estoque
                        st.session_state['df_produtos'].at[idx, 'preco_medio'] = novo_preco
                        
                        tipo_reg = "Entrada"
                    
                    # Lógica de Saída
                    else:
                        novo_estoque = antigo - qtd
                        st.session_state['df_produtos'].at[idx, 'qtd_atual'] = novo_estoque
                        tipo_reg = "Saída"

                    # Gravar no Histórico COM os novos campos
                    hist_entry = pd.DataFrame([{
                        "data": datetime.now().strftime("%d/%m %H:%M"),
                        "produto": item['nome'],
                        "tipo": tipo_reg,
                        "quantidade": qtd,
                        "saldo_anterior": antigo,
                        "saldo_novo": novo_estoque,
                        "fornecedor": fornecedor,      # Novo
                        "preco_aquisicao": preco_aq,   # Novo
                        "obs": obs
                    }])
                    
                    # Salvar
                    st.session_state['df_historico'] = pd.concat([hist_entry, st.session_state['df_historico']], ignore_index=True)
                    
                    with st.spinner("Salvando..."):
                        salvar_dados("estoque.csv", st.session_state['df_produtos'], f"Mov: {tipo_reg} {item['nome']}")
                        salvar_dados("historico.csv", st.session_state['df_historico'], "Log Histórico")
                    
                    st.success("Registrado com sucesso!")
                    st.rerun()

    # --- ABA 3: FORNECEDORES (NOVA) ---
    elif menu == "🚚 Fornecedores":
        st.header("Gerenciar Fornecedores")
        
        tab1, tab2 = st.tabs(["Novo Fornecedor", "Lista Cadastrada"])
        
        with tab1:
            with st.form("form_forn"):
                nome_forn = st.text_input("Nome da Empresa / Fornecedor")
                contato = st.text_input("Contato (Tel/Email)")
                obs_forn = st.text_input("Observação (ex: Entrega só terça)")
                
                if st.form_submit_button("Salvar Fornecedor"):
                    df = st.session_state['df_fornecedores']
                    novo_id = 1 if df.empty else df['id'].max() + 1
                    novo = pd.DataFrame([{
                        "id": novo_id, 
                        "nome": nome_forn, 
                        "contato": contato, 
                        "obs": obs_forn
                    }])
                    
                    df_final = pd.concat([df, novo], ignore_index=True)
                    st.session_state['df_fornecedores'] = df_final
                    salvar_dados("fornecedores.csv", df_final, f"Novo Fornecedor: {nome_forn}")
                    st.success("Fornecedor cadastrado!")
                    st.rerun()
        
        with tab2:
            st.dataframe(st.session_state['df_fornecedores'], use_container_width=True)
            
            # Botão excluir simples
            if not st.session_state['df_fornecedores'].empty:
                f_exc = st.selectbox("Excluir:", st.session_state['df_fornecedores']['nome'])
                if st.button("🗑️ Excluir Selecionado"):
                    df = st.session_state['df_fornecedores']
                    df = df[df['nome'] != f_exc]
                    st.session_state['df_fornecedores'] = df
                    salvar_dados("fornecedores.csv", df, "Exclusão Fornecedor")
                    st.success("Excluído.")
                    st.rerun()

    # --- ABA 4: FICHAS TÉCNICAS ---
    elif menu == "👨‍🍳 Fichas & Cardápios":
        st.title("Planejamento de Cardápio")
        tab_conferir, tab_cadastro = st.tabs(["✅ Conferir Estoque", "📝 Cadastrar Receitas"])
        
        with tab_conferir:
            opcao_cardapio = st.selectbox("Escolha o Cardápio:", ["Cardápio 1 (Seg/Ter)", "Cardápio 2 (Qua/Qui)", "Cardápio 3 (Sex/Sab)"])
            if st.button("🔍 Verificar Estoque"):
                df_fichas = st.session_state['df_fichas']
                df_estoque = st.session_state['df_produtos']
                if df_fichas.empty or df_estoque.empty:
                    st.warning("Sem dados.")
                else:
                    itens = df_fichas[df_fichas['cardapio'] == opcao_cardapio]
                    if itens.empty: st.warning("Cardápio vazio.")
                    else:
                        resumo = itens.groupby('ingrediente')['qtd_necessaria'].sum().reset_index()
                        analise = pd.merge(resumo, df_estoque[['nome', 'qtd_atual', 'unidade']], left_on='ingrediente', right_on='nome', how='left')
                        analise['saldo'] = analise['qtd_atual'] - analise['qtd_necessaria']
                        analise['comprar'] = analise['saldo'].apply(lambda x: abs(x) if x < 0 else 0)
                        
                        faltantes = analise[analise['saldo'] < 0]
                        if not faltantes.empty:
                            st.error(f"🚨 FALTAM INGREDIENTES!")
                            st.dataframe(faltantes[['ingrediente', 'qtd_necessaria', 'qtd_atual', 'comprar']])
                        else:
                            st.success("✅ Estoque OK!")

        with tab_cadastro:
            df_prod = st.session_state['df_produtos']
            if not df_prod.empty:
                with st.form("form_ficha"):
                    card = st.selectbox("Cardápio", ["Cardápio 1 (Seg/Ter)", "Cardápio 2 (Qua/Qui)", "Cardápio 3 (Sex/Sab)"])
                    prato = st.text_input("Prato")
                    ing = st.selectbox("Ingrediente", df_prod['nome'].unique())
                    q = st.number_input("Qtd", min_value=0.1)
                    if st.form_submit_button("Salvar"):
                        novo = pd.DataFrame([{"cardapio": card, "prato": prato, "ingrediente": ing, "qtd_necessaria": q}])
                        st.session_state['df_fichas'] = pd.concat([st.session_state['df_fichas'], novo], ignore_index=True)
                        salvar_dados("fichas.csv", st.session_state['df_fichas'], "Ficha")
                        st.success("Salvo!")
                        st.rerun()

    # --- ABA 5: CADASTRO ESTOQUE ---
    elif menu == "📝 Estoque (Cadastro)":
        st.header("Cadastrar Produto")
        with st.form("cad_prod"):
            nome = st.text_input("Nome")
            un = st.selectbox("Unidade", ["kg", "un", "lt", "pct"])
            qtd = st.number_input("Estoque Inicial", min_value=0.0)
            minimo = st.number_input("Minimo", min_value=0.0)
            preco = st.number_input("Preço Médio", min_value=0.0)
            validade = st.date_input("Validade")
            if st.form_submit_button("Salvar Produto"):
                novo = pd.DataFrame([{"id": len(st.session_state['df_produtos'])+1, "nome": nome, "unidade": un, "qtd_atual": qtd, "qtd_minima": minimo, "preco_medio": preco, "validade": validade}])
                st.session_state['df_produtos'] = pd.concat([st.session_state['df_produtos'], novo], ignore_index=True)
                salvar_dados("estoque.csv", st.session_state['df_produtos'], "Novo Produto")
                st.success("Cadastrado!")
                st.rerun()

    # --- ABA 6: HISTÓRICO ---
    elif menu == "📜 Histórico":
        st.dataframe(st.session_state['df_historico'], use_container_width=True)
