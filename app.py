import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime, date
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Restaurante V5", layout="wide", page_icon="👨‍🍳")

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

    # Menu Lateral
    st.sidebar.title("🥘 Joel Gastronomia")
    menu = st.sidebar.radio("Menu", 
        ["👨‍🍳 Fichas & Cardápios", # NOVO
         "🚨 Dashboard", 
         "🔄 Movimentação", 
         "📝 Estoque (Cadastro)", 
         "📜 Histórico"])
    
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    # --- ABA NOVA: FICHAS TÉCNICAS ---
    if menu == "👨‍🍳 Fichas & Cardápios":
        st.title("Planejamento de Cardápio")
        st.info("Defina o que é usado em cada dia para o sistema calcular as compras automaticamente.")
        
        tab_conferir, tab_cadastro = st.tabs(["✅ Conferir Estoque p/ Dia", "📝 Cadastrar Receitas"])
        
        # --- SUB-ABA: CONFERIR ESTOQUE ---
        with tab_conferir:
            st.subheader("O que vamos servir hoje?")
            opcao_cardapio = st.selectbox("Escolha o Cardápio:", 
                ["Cardápio 1 (Seg/Ter)", "Cardápio 2 (Qua/Qui)", "Cardápio 3 (Sex/Sab)"])
            
            if st.button("🔍 Verificar Estoque Necessário", type="primary"):
                df_fichas = st.session_state['df_fichas']
                df_estoque = st.session_state['df_produtos']
                
                if df_fichas.empty or df_estoque.empty:
                    st.warning("Cadastre produtos e fichas técnicas primeiro.")
                else:
                    # 1. Filtra só as fichas do cardápio selecionado
                    itens_necessarios = df_fichas[df_fichas['cardapio'] == opcao_cardapio]
                    
                    if itens_necessarios.empty:
                        st.warning(f"Nenhuma receita cadastrada para o {opcao_cardapio}.")
                    else:
                        # 2. Agrupa (caso o mesmo ingrediente seja usado em dois pratos diferentes)
                        resumo_necessidade = itens_necessarios.groupby('ingrediente')['qtd_necessaria'].sum().reset_index()
                        
                        # 3. Cruza com o Estoque Atual
                        # Fazemos um 'merge' para trazer a quantidade atual do estoque
                        analise = pd.merge(resumo_necessidade, df_estoque[['nome', 'qtd_atual', 'unidade']], 
                                         left_on='ingrediente', right_on='nome', how='left')
                        
                        # 4. Analisa faltas
                        analise['saldo'] = analise['qtd_atual'] - analise['qtd_necessaria']
                        analise['status'] = analise['saldo'].apply(lambda x: "🟢 OK" if x >= 0 else "🔴 FALTA")
                        analise['comprar'] = analise['saldo'].apply(lambda x: abs(x) if x < 0 else 0)
                        
                        # Exibe Resultados
                        faltantes = analise[analise['status'] == "🔴 FALTA"]
                        
                        if not faltantes.empty:
                            st.error(f"🚨 ATENÇÃO: Faltam ingredientes para o {opcao_cardapio}!")
                            st.dataframe(
                                faltantes[['ingrediente', 'qtd_necessaria', 'qtd_atual', 'comprar', 'unidade']],
                                use_container_width=True,
                                column_config={
                                    "qtd_necessaria": st.column_config.NumberColumn("Preciso de:", format="%.2f"),
                                    "qtd_atual": st.column_config.NumberColumn("Tenho:", format="%.2f"),
                                    "comprar": st.column_config.NumberColumn("COMPRAR:", format="%.2f"),
                                }
                            )
                        else:
                            st.success(f"✅ Tudo pronto! Estoque suficiente para o {opcao_cardapio}.")
                            st.balloons()
                        
                        with st.expander("Ver lista completa (Detalhada)"):
                            st.dataframe(analise[['ingrediente', 'qtd_necessaria', 'qtd_atual', 'status']])

        # --- SUB-ABA: CADASTRAR RECEITA ---
        with tab_cadastro:
            st.write("Vincule ingredientes aos cardápios.")
            df_prod = st.session_state['df_produtos']
            
            if not df_prod.empty:
                with st.form("form_ficha"):
                    c1, c2 = st.columns(2)
                    cardapio = c1.selectbox("Qual Cardápio?", ["Cardápio 1 (Seg/Ter)", "Cardápio 2 (Qua/Qui)", "Cardápio 3 (Sex/Sab)"])
                    prato = c2.text_input("Nome do Prato (ex: Feijoada)")
                    
                    c3, c4 = st.columns(2)
                    # Dropdown com os produtos do estoque para evitar erro de digitação
                    ingrediente = c3.selectbox("Ingrediente do Estoque:", df_prod['nome'].unique())
                    qtd = c4.number_input("Quantidade Necessária (Total p/ o dia):", min_value=0.1)
                    
                    if st.form_submit_button("Salvar Ingrediente na Ficha"):
                        nova_ficha = pd.DataFrame([{
                            "cardapio": cardapio,
                            "prato": prato,
                            "ingrediente": ingrediente,
                            "qtd_necessaria": qtd
                        }])
                        
                        # Salva
                        df_atual = st.session_state['df_fichas']
                        df_final = pd.concat([df_atual, nova_ficha], ignore_index=True)
                        st.session_state['df_fichas'] = df_final
                        
                        with st.spinner("Gravando..."):
                            salvar_dados("fichas.csv", df_final, f"Ficha: {prato} - {ingrediente}")
                        
                        st.success("Ingrediente adicionado à ficha técnica!")
                        st.rerun()
                
                # Botão para limpar fichas (caso erre)
                if not st.session_state['df_fichas'].empty:
                    st.divider()
                    st.subheader("Itens Cadastrados")
                    st.dataframe(st.session_state['df_fichas'])
                    
                    ing_exc = st.selectbox("Selecione para excluir:", st.session_state['df_fichas']['ingrediente'] + " - " + st.session_state['df_fichas']['cardapio'])
                    if st.button("Excluir Item da Ficha"):
                        # Logica simples de exclusão pelo index ou match string
                        # Aqui vamos simplificar recarregando sem o item
                        # (Num sistema real usariamos ID, mas string serve pro MVP)
                        temp = st.session_state['df_fichas']
                        # Gambiarra segura: Recria a coluna de seleção pra filtrar
                        temp['sel'] = temp['ingrediente'] + " - " + temp['cardapio']
                        temp = temp[temp['sel'] != ing_exc].drop(columns=['sel'])
                        
                        st.session_state['df_fichas'] = temp
                        salvar_dados("fichas.csv", temp, "Exclusão Ficha")
                        st.success("Removido.")
                        st.rerun()
            else:
                st.warning("Cadastre produtos no estoque antes de criar fichas.")

    # --- ABA 2: DASHBOARD ---
    elif menu == "🚨 Dashboard":
        st.header("Visão Geral")
        df = st.session_state['df_produtos']
        if not df.empty:
            # Alertas Básicos (Minimo)
            repor = df[df['qtd_atual'] <= df['qtd_minima']]
            if not repor.empty:
                st.error("🚨 ESTOQUE MÍNIMO ATINGIDO:")
                st.dataframe(repor[['nome', 'qtd_atual', 'qtd_minima']])
            
            c1, c2 = st.columns(2)
            df['total'] = df['qtd_atual'] * df['preco_medio']
            c1.metric("Produtos", len(df))
            c2.metric("Valor Financeiro", f"R$ {df['total'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)

    # --- ABA 3: MOVIMENTAÇÃO ---
    elif menu == "🔄 Movimentação":
        st.header("Entrada / Saída")
        df = st.session_state['df_produtos']
        if not df.empty:
            sel = st.selectbox("Produto:", df['nome'])
            idx = df.index[df['nome'] == sel].tolist()[0]
            item = df.loc[idx]
            st.info(f"Atual: {item['qtd_atual']} {item['unidade']}")
            
            c1, c2 = st.columns(2)
            tipo = c1.radio("Ação", ["Saída", "Entrada"])
            qtd = c2.number_input("Qtd", min_value=0.1)
            
            if st.button("Confirmar"):
                antigo = item['qtd_atual']
                novo = antigo + qtd if tipo == "Entrada" else antigo - qtd
                st.session_state['df_produtos'].at[idx, 'qtd_atual'] = novo
                
                # Histórico
                hist_entry = pd.DataFrame([{
                    "data": datetime.now().strftime("%d/%m %H:%M"),
                    "produto": item['nome'],
                    "tipo": tipo,
                    "quantidade": qtd,
                    "saldo_novo": novo,
                    "obs": "Manual"
                }])
                st.session_state['df_historico'] = pd.concat([hist_entry, st.session_state['df_historico']], ignore_index=True)
                
                salvar_dados("estoque.csv", st.session_state['df_produtos'], "Movimentação")
                salvar_dados("historico.csv", st.session_state['df_historico'], "Histórico")
                st.success("Ok!")
                st.rerun()

    # --- ABA 4: CADASTRO ESTOQUE ---
    elif menu == "📝 Estoque (Cadastro)":
        st.header("Cadastrar Novo Produto no Estoque")
        with st.form("cad_prod"):
            nome = st.text_input("Nome")
            un = st.selectbox("Unidade", ["kg", "un", "lt", "pct"])
            qtd = st.number_input("Estoque Inicial", min_value=0.0)
            minimo = st.number_input("Minimo", min_value=0.0)
            preco = st.number_input("Preço Médio", min_value=0.0)
            validade = st.date_input("Validade")
            if st.form_submit_button("Salvar Produto"):
                novo = pd.DataFrame([{"id": len(st.session_state['df_produtos'])+1, "nome": nome, "unidade": un, "qtd_atual": qtd, "qtd_minima": minimo, "preco_medio": preco, "validade": validade}])
                df_final = pd.concat([st.session_state['df_produtos'], novo], ignore_index=True)
                st.session_state['df_produtos'] = df_final
                salvar_dados("estoque.csv", df_final, "Novo Produto")
                st.success("Cadastrado!")
                st.rerun()

    # --- ABA 5: HISTÓRICO ---
    elif menu == "📜 Histórico":
        st.dataframe(st.session_state['df_historico'], use_container_width=True)
