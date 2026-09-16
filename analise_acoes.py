# ==============================================================================
# PAINEL QUANT — ANÁLISE DE MERCADO DE AÇÕES (Swing Trade & Day Trade)
# ==============================================================================
#
# COMO INSTALAR (rode no terminal, dentro da pasta do projeto):
#
#   pip install streamlit yfinance pandas pandas-ta plotly numpy
#
# COMO RODAR:
#
#   streamlit run analise_acoes.py
#
# ------------------------------------------------------------------------------
# O que este app faz:
#   1) Permite explorar um catálogo de produtos da B3 organizado por painel
#      (Ações, FIIs, ETFs, BDRs) e segmento, ou digitar qualquer ticker manualmente;
#   2) Busca dados históricos/intraday do ativo escolhido via yfinance;
#   3) Calcula um painel de indicadores técnicos (tendência, osciladores,
#      volatilidade e volume) usando pandas-ta;
#   4) Aplica um motor de pontuação (score) que soma/subtrai pontos por
#      indicador e gera um ALERTA final: COMPRA FORTE, COMPRA, NEUTRO,
#      VENDA ou VENDA FORTE;
#   5) Sugere Stop Loss e Take Profit automaticamente com base no ATR
#      (volatilidade real do ativo).
# ==============================================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Correção de compatibilidade: versões recentes do numpy (>=1.24/2.0) removeram
# o alias "np.NaN" (mantendo apenas "np.nan"), mas o pandas-ta ainda depende
# dele internamente em algumas versões. Este "patch" evita erro de import.
if not hasattr(np, "NaN"):
    np.NaN = np.nan

import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA (precisa ser o primeiro comando Streamlit do script)
# ==============================================================================
st.set_page_config(page_title="Painel Quant — Análise de Ações", layout="wide", page_icon="📈")


# ==============================================================================
# CATÁLOGO DE PRODUTOS DA B3
# ==============================================================================
# Estrutura: PAINEL -> SEGMENTO -> { TICKER: "Nome do produto" }
# Esta é uma curadoria dos ativos mais líquidos/conhecidos de cada categoria —
# a B3 lista centenas de produtos, então nem todos cabem aqui. Se o ativo que
# você procura não estiver na lista, use a opção "Digitar ticker manualmente".
#
# IMPORTANTE: só entram aqui categorias de produtos NEGOCIADOS EM BOLSA, com
# histórico público de preço (OHLC) compatível com candlestick e osciladores
# técnicos. Produtos de renda fixa bancária (CDB, LCI/LCA), Tesouro Direto,
# cotas de fundos de investimento e direitos de subscrição não entram aqui —
# eles aparecem no dicionário PAINEIS_SEM_DADOS logo abaixo, com explicação.
PRODUTOS_B3 = {
    "Ações Brasileiras": {
        "Bancos e Serviços Financeiros": {
            "ITUB4": "Itaú Unibanco", "BBDC4": "Bradesco", "BBAS3": "Banco do Brasil",
            "SANB11": "Santander Brasil", "BPAC11": "BTG Pactual", "B3SA3": "B3",
            "ITSA4": "Itaúsa",
        },
        "Petróleo, Gás e Combustíveis": {
            "PETR4": "Petrobras PN", "PETR3": "Petrobras ON", "PRIO3": "PetroRio",
            "UGPA3": "Ultrapar", "VBBR3": "Vibra Energia", "RRRP3": "3R Petroleum",
        },
        "Mineração e Siderurgia": {
            "VALE3": "Vale", "CSNA3": "CSN", "GGBR4": "Gerdau", "USIM5": "Usiminas",
            "CMIN3": "CSN Mineração", "GOAU4": "Metalúrgica Gerdau",
        },
        "Energia Elétrica": {
            "ELET3": "Eletrobras ON", "ELET6": "Eletrobras PNB", "CMIG4": "Cemig",
            "CPLE6": "Copel", "EGIE3": "Engie Brasil", "EQTL3": "Equatorial",
            "TAEE11": "Taesa", "CPFE3": "CPFL Energia",
        },
        "Varejo e Consumo": {
            "MGLU3": "Magazine Luiza", "LREN3": "Lojas Renner", "ARZZ3": "Arezzo",
            "PETZ3": "Petz", "VIVA3": "Vivara", "ASAI3": "Assaí",
            "CRFB3": "Carrefour Brasil",
        },
        "Bebidas e Alimentos": {
            "ABEV3": "Ambev", "JBSS3": "JBS", "BRFS3": "BRF", "MRFG3": "Marfrig",
            "SMTO3": "São Martinho", "BEEF3": "Minerva",
        },
        "Papel e Celulose": {
            "SUZB3": "Suzano", "KLBN11": "Klabin",
        },
        "Bens de Capital e Industrial": {
            "WEGE3": "WEG", "EMBR3": "Embraer", "RAPT4": "Randon",
        },
        "Saúde": {
            "RDOR3": "Rede D'Or", "HAPV3": "Hapvida", "FLRY3": "Fleury", "RADL3": "Raia Drogasil",
            "QUAL3": "Qualicorp",
        },
        "Tecnologia e Telecom": {
            "TOTS3": "Totvs", "VIVT3": "Telefônica Brasil (Vivo)", "TIMS3": "TIM",
        },
        "Construção Civil": {
            "CYRE3": "Cyrela", "MRVE3": "MRV", "EZTC3": "Eztec", "TEND3": "Tenda",
        },
        "Transporte e Logística": {
            "RENT3": "Localiza", "RAIL3": "Rumo", "CCRO3": "CCR", "AZUL4": "Azul",
        },
        "Seguros": {
            "BBSE3": "BB Seguridade", "PSSA3": "Porto Seguro", "CXSE3": "Caixa Seguridade",
        },
        "Agronegócio": {
            "SLCE3": "SLC Agrícola", "AGRO3": "BrasilAgro",
        },
    },
    "Fundos Imobiliários (FIIs)": {
        "Papel / Recebíveis": {
            "MXRF11": "Maxi Renda", "KNCR11": "Kinea Rendimentos", "KNIP11": "Kinea Índices de Preços",
            "IRDM11": "Iridium Recebíveis", "CPTS11": "Capitânia Securities", "RECR11": "REC Recebíveis Imobiliários",
            "VGIP11": "Valora CRI Índice de Preços",
        },
        "Tijolo (Lajes, Shoppings e Logística)": {
            "KNRI11": "Kinea Renda Imobiliária", "HGLG11": "CSHG Logística", "XPML11": "XP Malls",
            "VISC11": "Vinci Shopping Centers", "HGRE11": "CSHG Real Estate", "BRCO11": "Bresco Logística",
            "VILG11": "Vinci Logística", "PVBI11": "Pátria Edifícios Corporativos",
        },
        "Fundo de Fundos (FOFs)": {
            "BCFF11": "BTG Pactual Fundo de Fundos", "HFOF11": "Hedge FOFII", "RBFF11": "Rio Bravo FoF",
        },
    },
    "Fundos de Índice (ETFs)": {
        "Índices e Renda Variável": {
            "BOVA11": "iShares Ibovespa", "SMAL11": "iShares Small Cap", "IVVB11": "iShares S&P 500",
            "DIVO11": "It Now IDIV (Dividendos)", "GOLD11": "It Now Ouro", "HASH11": "Hashdex Cripto",
            "FIND11": "It Now Financeiro", "ISUS11": "It Now ISE (Sustentabilidade)",
        },
    },
    "Ações Globais (BDRs)": {
        "Tecnologia": {
            "AAPL34": "Apple", "MSFT34": "Microsoft", "GOGL34": "Alphabet (Google)",
            "AMZO34": "Amazon", "NVDC34": "Nvidia", "META34": "Meta", "NFLX34": "Netflix",
            "TSLA34": "Tesla", "INTC34": "Intel",
        },
        "Consumo e Financeiro": {
            "DISB34": "Disney", "COCA34": "Coca-Cola", "MCDC34": "McDonald's",
            "JPMC34": "JPMorgan", "BOAC34": "Bank of America", "WALM34": "Walmart",
            "VISA34": "Visa", "MSCD34": "Mastercard",
        },
    },
}

# ==============================================================================
# PAINÉIS SEM DADOS DE MERCADO (renda fixa, cotas e direitos de subscrição)
# ==============================================================================
# Estes produtos existem no Toro, no Nubank e em outras corretoras, mas NÃO
# são negociados em bolsa com candlestick/OHLC público — por isso este painel
# técnico (RSI, MACD, Bollinger etc.) não se aplica a eles. Eles aparecem na
# lista de painéis só para explicar essa diferença, não para análise.
# ==============================================================================
# PAINÉIS SEM DADOS DE MERCADO (renda fixa, cotas e direitos de subscrição)
# ==============================================================================
# Estes produtos existem no Toro, no Nubank e em outras corretoras, mas NÃO
# são negociados em bolsa com candlestick/OHLC público — por isso este painel
# técnico (RSI, MACD, Bollinger etc.) não se aplica a eles. Eles aparecem na
# lista de painéis só para explicar essa diferença, não para análise.
PAINEIS_SEM_DADOS = {
    "Fundos de Investimento": (
        "Fundos de investimento (multimercado, renda fixa, ações etc.) têm o "
        "valor da cota divulgado diariamente pelo administrador, mas não há uma "
        "fonte pública e padronizada de dados históricos como o yfinance oferece "
        "para ações — cada fundo tem seu próprio CNPJ e a fonte de dados varia "
        "por administradora."
    ),
}

# ==============================================================================
# CORES POR CATEGORIA (para deixar o painel mais visual/interativo)
# ==============================================================================
# Cada painel (negociável ou não) recebe uma cor própria, usada nos selos
# exibidos na barra lateral e no topo da página principal.
CORES_PAINEL = {
    "Ações Brasileiras": "#2E7D32",           # verde
    "Fundos Imobiliários (FIIs)": "#8D6E63",  # marrom (tijolo)
    "Fundos de Índice (ETFs)": "#1565C0",     # azul
    "Ações Globais (BDRs)": "#6A1B9A",        # roxo
    "Fundos de Investimento": "#5D4037",      # marrom escuro
}
COR_PADRAO_PAINEL = "#607D8B"  # usada como fallback (modo "digitar ticker manualmente")


# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================

def col(df: pd.DataFrame, *prefixos: str):
    """
    Retorna o nome da primeira coluna do DataFrame que comece com um dos
    prefixos informados. Necessário porque a nomenclatura de colunas gerada
    pelo pandas-ta pode variar ligeiramente entre versões da biblioteca
    (ex: 'ATRr_14' vs 'ATR_14'). Evita que o app quebre por KeyError.
    """
    for prefixo in prefixos:
        for c in df.columns:
            if c.startswith(prefixo):
                return c
    return None


@st.cache_data(ttl=300, show_spinner=False)
def buscar_dados(ticker: str, periodo: str, intervalo: str) -> pd.DataFrame:
    """
    Busca os dados OHLCV (Open, High, Low, Close, Volume) do ativo no Yahoo
    Finance. Resultado é cacheado por 5 minutos para evitar múltiplas
    chamadas desnecessárias à API a cada interação do usuário na interface.
    """
    acao = yf.Ticker(ticker)
    df = acao.history(period=periodo, interval=intervalo)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.dropna(how="all")
    return df


def calcular_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o VWAP (Volume Weighted Average Price) manualmente, reiniciando
    o cálculo a cada novo pregão (dia). Essa é a forma correta de calcular
    VWAP para day trade — diferente de uma média móvel comum, ele acumula
    (preço típico x volume) desde a abertura do dia.

    Observação: em timeframes diários (1d) ou maiores, o VWAP tende a ficar
    muito próximo do preço típico da própria vela, pois cada "dia" tem
    apenas uma barra — sua utilidade real é em gráficos intraday (5m/15m/1h).
    """
    df = df.copy()
    preco_tipico = (df["High"] + df["Low"] + df["Close"]) / 3
    tpv = preco_tipico * df["Volume"]

    dia = df.index.date
    cum_tpv = tpv.groupby(dia).cumsum()
    cum_vol = df["Volume"].groupby(dia).cumsum().replace(0, np.nan)

    df["VWAP"] = cum_tpv / cum_vol
    return df


def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula todo o painel de indicadores técnicos sobre o DataFrame de preços,
    usando a biblioteca pandas-ta, e anexa as colunas resultantes ao próprio
    DataFrame.
    """
    df = df.copy()

    # --- A) Rastreadores de Tendência ---
    df.ta.ema(length=9, append=True)     # EMA_9  (curtíssimo prazo)
    df.ta.ema(length=21, append=True)    # EMA_21 (curto prazo)
    df.ta.sma(length=200, append=True)   # SMA_200 (tendência de longo prazo)
    df = calcular_vwap(df)               # VWAP (essencial para day trade)

    # --- B) Osciladores (momento / sobrecompra-sobrevenda) ---
    df.ta.rsi(length=14, append=True)                       # IFR / RSI 14
    df.ta.stoch(k=14, d=3, smooth_k=3, append=True)          # Estocástico %K / %D
    df.ta.macd(fast=12, slow=26, signal=9, append=True)      # MACD / Sinal / Histograma

    # --- C) Indicadores de Volatilidade ---
    df.ta.bbands(length=20, std=2, append=True)  # Bandas de Bollinger
    df.ta.atr(length=14, append=True)            # ATR (para stop/take)

    # --- D) Indicadores de Volume e Fluxo ---
    df["VOL_MA20"] = df["Volume"].rolling(window=20).mean()  # Média de volume
    df.ta.obv(append=True)                                    # OBV
    obv_col = col(df, "OBV")
    if obv_col:
        df["OBV_MA10"] = df[obv_col].rolling(window=10).mean()

    return df


def gerar_sinais(df: pd.DataFrame):
    """
    MOTOR DE RECOMENDAÇÃO (sistema de pontuação / score).

    Cada indicador contribui com +1 ponto (viés de COMPRA) ou -1 ponto
    (viés de VENDA) para o score final. Retorna:
      - score total (inteiro)
      - dicionário com o detalhamento de cada critério avaliado, para
        exibição em uma tabela de transparência do sinal.
    """
    detalhes = {}
    score = 0

    if len(df) < 2:
        return score, detalhes

    atual = df.iloc[-1]
    anterior = df.iloc[-2]

    rsi_col = col(df, "RSI")
    k_col = col(df, "STOCHk")
    d_col = col(df, "STOCHd")
    macd_col = col(df, "MACD_")
    macds_col = col(df, "MACDs")

    # --- 1) RSI: sobrevendido (<30) = compra | sobrecomprado (>70) = venda ---
    if rsi_col and pd.notna(atual[rsi_col]):
        rsi = atual[rsi_col]
        if rsi < 30:
            score += 1
            detalhes[f"IFR/RSI sobrevendido ({rsi:.1f} < 30)"] = "+1 (compra)"
        elif rsi > 70:
            score -= 1
            detalhes[f"IFR/RSI sobrecomprado ({rsi:.1f} > 70)"] = "-1 (venda)"
        else:
            detalhes[f"IFR/RSI neutro ({rsi:.1f})"] = "0"

    # --- 2) Estocástico: cruzamento de 20 (compra) ou de 80 (venda) ---
    if k_col and pd.notna(atual[k_col]) and pd.notna(anterior[k_col]):
        k_atual, k_ant = atual[k_col], anterior[k_col]
        if k_ant <= 20 < k_atual:
            score += 1
            detalhes["Estocástico cruzou ACIMA de 20 (saindo da sobrevenda)"] = "+1 (compra)"
        elif k_ant >= 80 > k_atual:
            score -= 1
            detalhes["Estocástico cruzou ABAIXO de 80 (saindo da sobrecompra)"] = "-1 (venda)"
        else:
            detalhes[f"Estocástico sem cruzamento relevante (%K={k_atual:.1f})"] = "0"

    # --- 3) Preço vs VWAP ---
    if "VWAP" in df.columns and pd.notna(atual["VWAP"]):
        if atual["Close"] > atual["VWAP"]:
            score += 1
            detalhes["Preço ACIMA da VWAP"] = "+1 (compra)"
        else:
            score -= 1
            detalhes["Preço ABAIXO da VWAP"] = "-1 (venda)"

    # --- 4) MACD: cruzamento da linha MACD com a linha de sinal ---
    if macd_col and macds_col and pd.notna(atual[macd_col]) and pd.notna(anterior[macd_col]):
        macd_atual, sig_atual = atual[macd_col], atual[macds_col]
        macd_ant, sig_ant = anterior[macd_col], anterior[macds_col]
        if macd_ant <= sig_ant and macd_atual > sig_atual:
            score += 1
            detalhes["MACD cruzou PARA CIMA do sinal"] = "+1 (compra)"
        elif macd_ant >= sig_ant and macd_atual < sig_atual:
            score -= 1
            detalhes["MACD cruzou PARA BAIXO do sinal"] = "-1 (venda)"
        else:
            detalhes["MACD sem cruzamento no candle atual"] = "0"

    # --- 5) Preço vs SMA 200 (tendência de longo prazo) ---
    if "SMA_200" in df.columns and pd.notna(atual["SMA_200"]):
        if atual["Close"] > atual["SMA_200"]:
            score += 1
            detalhes["Preço ACIMA da SMA 200 (tendência de alta)"] = "+1 (compra)"
        else:
            score -= 1
            detalhes["Preço ABAIXO da SMA 200 (tendência de baixa)"] = "-1 (venda)"
    else:
        detalhes["SMA 200 indisponível (histórico insuficiente no período)"] = "0"

    # --- 6) OBV: dinheiro institucional entrando (acumulação) ou saindo ---
    obv_col = col(df, "OBV")
    if obv_col and "OBV_MA10" in df.columns and pd.notna(atual.get("OBV_MA10")):
        if atual[obv_col] > atual["OBV_MA10"]:
            score += 1
            detalhes["OBV em alta (acumulação institucional)"] = "+1 (compra)"
        else:
            score -= 1
            detalhes["OBV em baixa (distribuição institucional)"] = "-1 (venda)"

    return score, detalhes


def classificar_score(score: int):
    """
    Converte o score numérico em uma classificação textual + cores para o
    card de sinal (fundo, texto), conforme as faixas definidas no projeto.
    """
    if score >= 4:
        return "🟢 COMPRA FORTE", "#0B6623", "#FFFFFF"
    elif score >= 2:
        return "🟢 COMPRA", "#A8E6A3", "#0B3D0B"
    elif score >= -1:
        return "🟡 NEUTRO / AGUARDAR", "#FFD966", "#3D3000"
    elif score >= -3:
        return "🔴 VENDA", "#F4A6A6", "#5C0000"
    else:
        return "🔴 VENDA FORTE", "#8B0000", "#FFFFFF"


def sugerir_stop_take(preco_atual: float, atr: float, score: int):
    """
    GERENCIAMENTO DE RISCO AUTOMATIZADO.

    Usa o ATR (volatilidade real e atual do ativo, em R$/US$ por ação) para
    sugerir onde posicionar Stop Loss e Take Profit, mantendo uma relação
    risco:retorno fixa de 1:2 (2x ATR de risco contra 4x ATR de retorno).

    A direção sugerida (compra ou venda) segue o viés indicado pelo score:
      - score >= 2  -> cenário de COMPRA (stop abaixo, alvo acima)
      - score <= -2 -> cenário de VENDA  (stop acima, alvo abaixo)
      - caso contrário, não há convicção suficiente para sugerir uma operação.
    """
    if atr is None or pd.isna(atr) or atr == 0:
        return None

    if score >= 2:
        return {
            "direcao": "COMPRA",
            "stop": preco_atual - 2 * atr,
            "alvo": preco_atual + 4 * atr,
            "atr": atr,
        }
    elif score <= -2:
        return {
            "direcao": "VENDA",
            "stop": preco_atual + 2 * atr,
            "alvo": preco_atual - 4 * atr,
            "atr": atr,
        }
    else:
        return {"direcao": "NEUTRO", "stop": None, "alvo": None, "atr": atr}


def montar_visao_geral(df: pd.DataFrame) -> dict:
    """
    Monta os dados do painel "Visão Geral" (estilo dashboard): agrupa TODOS
    os indicadores técnicos em 4 categorias (Tendência, Osciladores,
    Volatilidade, Volume e Fluxo) — inclusive os que não entram no score
    (Bandas de Bollinger, ATR, EMA 9/21) — cada um com seu valor atual e um
    status visual (verde = favorável, vermelho = desfavorável, cinza = neutro).

    Retorna um dicionário {categoria: [(nome, valor_formatado, cor), ...]}.
    """
    if len(df) < 2:
        return {}

    atual = df.iloc[-1]

    rsi_col_n = col(df, "RSI")
    k_col_n = col(df, "STOCHk")
    macdh_col_n = col(df, "MACDh")
    bbl_col_n = col(df, "BBL")
    bbu_col_n = col(df, "BBU")
    atr_col_n = col(df, "ATR")
    obv_col_n = col(df, "OBV")

    VERDE, VERMELHO, CINZA = "#2E7D32", "#C62828", "#757575"
    categorias: dict = {}

    # --- A) Tendência ---
    tendencia = []
    if "EMA_9" in df.columns and "EMA_21" in df.columns and pd.notna(atual["EMA_9"]) and pd.notna(atual["EMA_21"]):
        alta = atual["EMA_9"] > atual["EMA_21"]
        tendencia.append(("EMA 9 vs EMA 21", "Alinhamento de alta" if alta else "Alinhamento de baixa", VERDE if alta else VERMELHO))
    if "SMA_200" in df.columns and pd.notna(atual["SMA_200"]):
        acima = atual["Close"] > atual["SMA_200"]
        tendencia.append(("Preço vs SMA 200", f"{atual['SMA_200']:.2f} ({'acima' if acima else 'abaixo'})", VERDE if acima else VERMELHO))
    if "VWAP" in df.columns and pd.notna(atual["VWAP"]):
        acima = atual["Close"] > atual["VWAP"]
        tendencia.append(("Preço vs VWAP", f"{atual['VWAP']:.2f} ({'acima' if acima else 'abaixo'})", VERDE if acima else VERMELHO))
    categorias["📈 Tendência"] = tendencia

    # --- B) Osciladores ---
    osciladores = []
    if rsi_col_n and pd.notna(atual[rsi_col_n]):
        rsi = atual[rsi_col_n]
        cor = VERMELHO if rsi > 70 else (VERDE if rsi < 30 else CINZA)
        osciladores.append(("RSI / IFR (14)", f"{rsi:.1f}", cor))
    if k_col_n and pd.notna(atual[k_col_n]):
        k = atual[k_col_n]
        cor = VERMELHO if k > 80 else (VERDE if k < 20 else CINZA)
        osciladores.append(("Estocástico %K", f"{k:.1f}", cor))
    if macdh_col_n and pd.notna(atual[macdh_col_n]):
        h = atual[macdh_col_n]
        cor = VERDE if h > 0 else VERMELHO
        osciladores.append(("MACD (histograma)", f"{h:+.3f}", cor))
    categorias["🌊 Osciladores"] = osciladores

    # --- C) Volatilidade ---
    volatilidade = []
    if atr_col_n and pd.notna(atual[atr_col_n]) and atual["Close"]:
        atr_pct = atual[atr_col_n] / atual["Close"] * 100
        if atr_pct > 3:
            cor, rotulo = VERMELHO, "alta"
        elif atr_pct > 1:
            cor, rotulo = CINZA, "moderada"
        else:
            cor, rotulo = VERDE, "baixa"
        volatilidade.append(("ATR (14)", f"{atual[atr_col_n]:.2f} — volatilidade {rotulo} ({atr_pct:.1f}%)", cor))
    if bbl_col_n and bbu_col_n and pd.notna(atual[bbl_col_n]) and pd.notna(atual[bbu_col_n]):
        largura = atual[bbu_col_n] - atual[bbl_col_n]
        pos = (atual["Close"] - atual[bbl_col_n]) / largura if largura else 0.5
        if pos > 0.8:
            cor, rotulo = VERMELHO, "perto da banda superior"
        elif pos < 0.2:
            cor, rotulo = VERDE, "perto da banda inferior"
        else:
            cor, rotulo = CINZA, "região central"
        volatilidade.append(("Posição nas Bandas de Bollinger", f"{pos * 100:.0f}% — {rotulo}", cor))
    categorias["📊 Volatilidade"] = volatilidade

    # --- D) Volume e Fluxo ---
    volume = []
    if "VOL_MA20" in df.columns and pd.notna(atual["VOL_MA20"]):
        acima = atual["Volume"] > atual["VOL_MA20"]
        volume.append(("Volume vs Média 20", "Acima da média" if acima else "Abaixo da média", VERDE if acima else CINZA))
    if obv_col_n and "OBV_MA10" in df.columns and pd.notna(atual.get("OBV_MA10")):
        subindo = atual[obv_col_n] > atual["OBV_MA10"]
        volume.append(("OBV", "Acumulação institucional" if subindo else "Distribuição institucional", VERDE if subindo else VERMELHO))
    categorias["📦 Volume e Fluxo"] = volume

    return categorias


def renderizar_card_categoria(titulo: str, itens: list) -> None:
    """Renderiza um card de categoria (usado na aba Visão Geral) com uma linha por indicador."""
    linhas_html = "".join(
        f'<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; '
        f'padding:7px 0; border-bottom:1px solid rgba(128,128,128,0.18);">'
        f'<span>{nome}</span>'
        f'<span style="color:{cor}; font-weight:700; text-align:right;">{valor}</span>'
        f'</div>'
        for nome, valor, cor in itens
    )
    if not linhas_html:
        linhas_html = '<div style="opacity:0.6;">Sem dados suficientes neste período.</div>'
    st.markdown(
        f"""
        <div style="border:1px solid rgba(128,128,128,0.25); border-radius:12px;
                    padding:16px 20px; margin-bottom:16px;">
            <div style="font-size:16px; font-weight:700; margin-bottom:6px;">{titulo}</div>
            {linhas_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def montar_grafico(df: pd.DataFrame, ticker: str, modo_escuro: bool = False) -> go.Figure:
    """
    Monta o gráfico interativo completo (Plotly) com 7 painéis empilhados,
    todos compartilhando o mesmo eixo X (tempo):
      1. Candlestick + EMA9 + EMA21 + SMA200 + VWAP + Bandas de Bollinger
      2. Volume financeiro + média móvel de volume (20)
      3. IFR / RSI
      4. Oscilador Estocástico (%K, %D)
      5. MACD (linha, sinal, histograma)
      6. OBV
      7. ATR
    """
    rsi_col = col(df, "RSI")
    k_col = col(df, "STOCHk")
    d_col = col(df, "STOCHd")
    macd_col = col(df, "MACD_")
    macds_col = col(df, "MACDs")
    macdh_col = col(df, "MACDh")
    bbl_col = col(df, "BBL")
    bbu_col = col(df, "BBU")
    atr_col = col(df, "ATR")
    obv_col = col(df, "OBV")

    fig = make_subplots(
        rows=7, cols=1, shared_xaxes=True, vertical_spacing=0.012,
        row_heights=[0.30, 0.10, 0.115, 0.115, 0.13, 0.11, 0.11],
        subplot_titles=(
            f"{ticker} — Preço, Médias, VWAP e Bandas de Bollinger",
            "Volume Financeiro",
            "IFR / RSI (14)",
            "Oscilador Estocástico (%K / %D)",
            "MACD",
            "OBV — On-Balance Volume",
            "ATR — Volatilidade",
        ),
    )

    # --- Painel 1: Candlestick + overlays de tendência ---
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Preço", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    if "EMA_9" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA_9"], line=dict(width=1.2, color="#1f77b4"), name="EMA 9"), row=1, col=1)
    if "EMA_21" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA_21"], line=dict(width=1.2, color="#ff7f0e"), name="EMA 21"), row=1, col=1)
    if "SMA_200" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_200"], line=dict(width=1.6, color="#9467bd"), name="SMA 200"), row=1, col=1)
    if "VWAP" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], line=dict(width=1.3, color="#17becf", dash="dot"), name="VWAP"), row=1, col=1)
    if bbu_col and bbl_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[bbu_col], line=dict(width=1, color="rgba(150,150,150,0.55)"), name="BB Superior"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[bbl_col], line=dict(width=1, color="rgba(150,150,150,0.55)"),
                                  name="BB Inferior", fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1)

    # --- Painel 2: Volume ---
    cores_vol = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=cores_vol, name="Volume"), row=2, col=1)
    if "VOL_MA20" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["VOL_MA20"], line=dict(width=1.3, color="#000000"), name="Média Vol. 20"), row=2, col=1)

    # --- Painel 3: RSI ---
    if rsi_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[rsi_col], line=dict(width=1.3, color="#8e44ad"), name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # --- Painel 4: Estocástico ---
    if k_col and d_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[k_col], line=dict(width=1.2, color="#2980b9"), name="%K"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[d_col], line=dict(width=1.2, color="#e67e22"), name="%D"), row=4, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", row=4, col=1)

    # --- Painel 5: MACD ---
    if macd_col and macds_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[macd_col], line=dict(width=1.2, color="#2980b9"), name="MACD"), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[macds_col], line=dict(width=1.2, color="#e67e22"), name="Sinal"), row=5, col=1)
        if macdh_col:
            cores_hist = ["#26a69a" if v >= 0 else "#ef5350" for v in df[macdh_col].fillna(0)]
            fig.add_trace(go.Bar(x=df.index, y=df[macdh_col], marker_color=cores_hist, name="Histograma"), row=5, col=1)

    # --- Painel 6: OBV ---
    if obv_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[obv_col], line=dict(width=1.3, color="#16a085"), name="OBV"), row=6, col=1)
        if "OBV_MA10" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["OBV_MA10"], line=dict(width=1, color="#7f8c8d", dash="dot"), name="Média OBV 10"), row=6, col=1)

    # --- Painel 7: ATR ---
    if atr_col:
        fig.add_trace(go.Scatter(x=df.index, y=df[atr_col], line=dict(width=1.3, color="#c0392b"), name="ATR"), row=7, col=1)

    fig.update_layout(
        height=1400,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.015, xanchor="right", x=1),
        hovermode="x unified",
        template="plotly_dark" if modo_escuro else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",  # fundo transparente: acompanha o fundo da página
        plot_bgcolor="rgba(0,0,0,0)" if modo_escuro else "white",
    )
    return fig


# ==============================================================================
# INTERFACE — BARRA LATERAL (PARÂMETROS DE ENTRADA)
# ==============================================================================
st.sidebar.title("⚙️ Parâmetros de Análise")

modo_escuro = st.sidebar.toggle("🌙 Modo escuro", value=False)

if modo_escuro:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; }
        section[data-testid="stSidebar"] { background-color: #161A23; }
        section[data-testid="stSidebar"] * { color: #FAFAFA !important; }
        .stApp, .stApp p, .stApp span, .stApp label, .stApp li { color: #FAFAFA; }
        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { color: #FAFAFA !important; }
        div[data-testid="stDataFrame"] { filter: invert(0.92) hue-rotate(180deg); }

        /* Caixas dos menus (Painel / Segmento / Produto / Período / Intervalo) */
        div[data-baseweb="select"] > div {
            background-color: #262730 !important;
            color: #FAFAFA !important;
            border-color: #3A3B45 !important;
        }
        div[data-baseweb="select"] svg { fill: #FAFAFA !important; }

        /* Lista de opções que abre ao clicar (fica fora da sidebar, por isso é à parte) */
        div[data-baseweb="popover"] li,
        ul[role="listbox"] li {
            background-color: #262730 !important;
            color: #FAFAFA !important;
        }
        div[data-baseweb="popover"] li:hover,
        ul[role="listbox"] li:hover {
            background-color: #3A3B45 !important;
        }

        /* Campo de texto manual do ticker */
        div[data-testid="stTextInput"] input {
            background-color: #262730 !important;
            color: #FAFAFA !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

modo_escolha = st.sidebar.radio(
    "Como deseja escolher o ativo?",
    options=["Explorar por painel", "Digitar ticker manualmente"],
    horizontal=False,
)

if modo_escolha == "Explorar por painel":
    todos_os_paineis = list(PRODUTOS_B3.keys()) + list(PAINEIS_SEM_DADOS.keys())
    painel_escolhido = st.sidebar.selectbox("📂 Painel", options=todos_os_paineis)

    cor_painel = CORES_PAINEL.get(painel_escolhido, COR_PADRAO_PAINEL)
    st.sidebar.markdown(
        f'<span style="background:{cor_painel}; color:white; padding:3px 12px; '
        f'border-radius:14px; font-size:13px; font-weight:600;">📂 {painel_escolhido}</span>',
        unsafe_allow_html=True,
    )

    if painel_escolhido in PAINEIS_SEM_DADOS:
        # Painel informativo: produto de renda fixa/cota, sem candlestick disponível.
        ticker = None
        st.sidebar.warning(PAINEIS_SEM_DADOS[painel_escolhido])
    else:
        segmentos_do_painel = PRODUTOS_B3[painel_escolhido]
        segmento_escolhido = st.sidebar.selectbox("📁 Segmento", options=list(segmentos_do_painel.keys()))
        produtos_do_segmento = segmentos_do_painel[segmento_escolhido]
        opcoes_produto = [f"{tk} — {nome}" for tk, nome in produtos_do_segmento.items()]
        produto_escolhido = st.sidebar.selectbox("🏷️ Produto", options=opcoes_produto)
        ticker_base = produto_escolhido.split(" — ")[0]
        ticker = f"{ticker_base}.SA"
        st.sidebar.caption(f"Ticker selecionado: **{ticker}**")
else:
    ticker = st.sidebar.text_input(
        "Ticker da ação",
        value="PETR4.SA",
        help="Ações brasileiras (B3) precisam do sufixo .SA. Ex: PETR4.SA, VALE3.SA, ITUB4.SA. Ações americanas: AAPL, MSFT, TSLA.",
    ).strip().upper()

periodo = st.sidebar.selectbox(
    "Período histórico",
    options=["1d", "5d", "1mo", "6mo", "1y", "2y"],
    index=2,
)

intervalo = st.sidebar.selectbox(
    "Intervalo (timeframe)",
    options=["5m", "15m", "1h", "1d"],
    index=3,
)

st.sidebar.caption(
    "⚠️ O Yahoo Finance limita o histórico disponível para intervalos curtos "
    "(ex: 5m/15m geralmente só retornam os últimos ~60 dias, independente do "
    "período escolhido). Se o gráfico vier vazio, tente um período menor."
)

analisar = st.sidebar.button("🔍 Analisar Ação", use_container_width=True, type="primary")

with st.sidebar.expander("ℹ️ Como funciona o score"):
    st.markdown(
        """
        Cada indicador vota **+1** (viés de compra) ou **-1** (viés de venda):

        - IFR/RSI < 30 (compra) / > 70 (venda)
        - Estocástico cruzando 20 (compra) / 80 (venda)
        - Preço acima (compra) / abaixo (venda) da VWAP
        - Cruzamento do MACD para cima (compra) / para baixo (venda)
        - Preço acima (compra) / abaixo (venda) da SMA 200
        - OBV subindo (compra) / caindo (venda)

        **Faixas finais:**
        - `>= +4`: 🟢 Compra Forte
        - `+2 a +3`: 🟢 Compra
        - `-1 a +1`: 🟡 Neutro / Aguardar
        - `-2 a -3`: 🔴 Venda
        - `<= -4`: 🔴 Venda Forte
        """
    )

# ==============================================================================
# CORPO PRINCIPAL DO APP
# ==============================================================================
st.title("📈 Painel Quant — Análise de Ações")
st.caption("Swing Trade & Day Trade · Sinais baseados em painel multindicadores")

if modo_escolha == "Explorar por painel":
    _cor_topo = CORES_PAINEL.get(painel_escolhido, COR_PADRAO_PAINEL)
    st.markdown(
        f'<span style="background:{_cor_topo}; color:white; padding:4px 14px; '
        f'border-radius:16px; font-size:14px; font-weight:600;">📂 {painel_escolhido}</span>',
        unsafe_allow_html=True,
    )

if not ticker:
    if modo_escolha == "Explorar por painel" and painel_escolhido in PAINEIS_SEM_DADOS:
        st.info(
            f"**{painel_escolhido}** não possui candlestick nem indicadores técnicos "
            "neste painel — veja a explicação na barra lateral. Escolha outro painel "
            "(Ações, FIIs, ETFs ou BDRs) para rodar a análise."
        )
    else:
        st.info("Digite um ticker na barra lateral e clique em **Analisar Ação** para começar.")
    st.stop()

with st.spinner(f"Buscando dados de {ticker}..."):
    df_bruto = buscar_dados(ticker, periodo, intervalo)

if df_bruto.empty:
    st.error(
        f"Não foi possível obter dados para **{ticker}** com período='{periodo}' e "
        f"intervalo='{intervalo}'. Verifique o ticker (ações da B3 precisam do sufixo "
        f"'.SA', ex: PETR4.SA) ou tente uma combinação diferente de período/intervalo."
    )
    st.stop()

df = calcular_indicadores(df_bruto)

score, detalhes_sinais = gerar_sinais(df)
classificacao, cor_fundo, cor_texto = classificar_score(score)

preco_atual = df["Close"].iloc[-1]
preco_anterior = df["Close"].iloc[-2] if len(df) > 1 else preco_atual
variacao = preco_atual - preco_anterior
variacao_pct = (variacao / preco_anterior * 100) if preco_anterior else 0
atr_col_nome = col(df, "ATR")
atr_atual = df[atr_col_nome].iloc[-1] if atr_col_nome else None

# --- Linha de métricas principais ---
col_a, col_b, col_c = st.columns(3)
col_a.metric(
    label=f"Preço Atual — {ticker}",
    value=f"{preco_atual:,.2f}",
    delta=f"{variacao:+.2f} ({variacao_pct:+.2f}%)",
)
col_b.metric(label="ATR (14) — Volatilidade", value=f"{atr_atual:.2f}" if atr_atual is not None else "N/D")
col_c.metric(label="Score do Motor de Sinais", value=f"{score:+d} pontos")

# --- Card de sinal / ALERTA (COMPRA / VENDA / NEUTRO) ---
st.subheader("🔔 Alerta de Sinal")
st.markdown(
    f"""
    <div style="background-color:{cor_fundo}; color:{cor_texto}; padding:18px 24px;
                border-radius:12px; text-align:center; font-size:26px; font-weight:700;
                margin: 10px 0 20px 0;">
        {classificacao} — {ticker} <span style="font-size:16px; font-weight:400;">(score: {score:+d})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Notificação rápida (toast) reforçando o alerta, para dar uma resposta mais viva/interativa
st.toast(f"{classificacao} — {ticker} (score {score:+d})", icon="🔔")

# --- Navegação por abas: deixa o painel mais organizado e interativo ---
aba_visao, aba_grafico, aba_sinais, aba_risco = st.tabs(
    ["📋 Visão Geral", "📊 Gráfico Técnico", "🧮 Motor de Sinais", "🛡️ Gerenciamento de Risco"]
)

with aba_visao:
    st.subheader("📋 Visão Geral — Painel de Indicadores")
    st.caption("Todos os indicadores organizados por categoria, com o valor atual e o status de cada um.")
    visao = montar_visao_geral(df)
    if visao:
        categorias_lista = list(visao.items())
        coluna_esq, coluna_dir = st.columns(2)
        colunas_grid = [coluna_esq, coluna_dir]
        for i, (titulo_cat, itens_cat) in enumerate(categorias_lista):
            with colunas_grid[i % 2]:
                renderizar_card_categoria(titulo_cat, itens_cat)
    else:
        st.info("Dados insuficientes para montar a visão geral neste período/intervalo.")

with aba_grafico:
    st.plotly_chart(montar_grafico(df, ticker, modo_escuro), use_container_width=True)

with aba_sinais:
    st.subheader("🧮 Detalhamento do Motor de Sinais")
    if detalhes_sinais:
        df_detalhes = pd.DataFrame(
            [{"Critério": k, "Contribuição": v} for k, v in detalhes_sinais.items()]
        )
        st.dataframe(df_detalhes, use_container_width=True, hide_index=True)
    else:
        st.info("Dados insuficientes para calcular os critérios de sinal neste período/intervalo.")

with aba_risco:
    st.subheader("🛡️ Gerenciamento de Risco Automatizado (baseado em ATR)")

    sugestao = sugerir_stop_take(preco_atual, atr_atual, score)

    if sugestao is None:
        st.warning("ATR indisponível — não é possível calcular sugestão de Stop Loss / Take Profit.")
    elif sugestao["direcao"] == "NEUTRO":
        st.info(
            "O score atual está na faixa **neutra** — o motor não recomenda entrada agora, "
            "portanto nenhuma sugestão de Stop Loss / Take Profit é exibida. Aguarde um "
            "sinal de Compra ou Venda mais definido."
        )
    else:
        risco_r = abs(preco_atual - sugestao["stop"])
        retorno_r = abs(sugestao["alvo"] - preco_atual)
        rr_ratio = retorno_r / risco_r if risco_r else 0

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Direção Sugerida", sugestao["direcao"])
        r2.metric("Stop Loss (2x ATR)", f"{sugestao['stop']:,.2f}")
        r3.metric("Take Profit (4x ATR)", f"{sugestao['alvo']:,.2f}")
        r4.metric("Relação Risco:Retorno", f"1 : {rr_ratio:.1f}")

        st.caption(
            f"Cálculo: preço atual ({preco_atual:,.2f}) "
            f"{'−' if sugestao['direcao'] == 'COMPRA' else '+'} 2 × ATR ({sugestao['atr']:.2f}) = Stop · "
            f"{'+' if sugestao['direcao'] == 'COMPRA' else '−'} 4 × ATR = Take Profit. "
            "Esta é uma sugestão automática baseada em volatilidade, não uma recomendação de investimento."
        )

st.divider()
st.caption(
    "⚠️ Este aplicativo é uma ferramenta de apoio à análise técnica e não constitui "
    "recomendação de investimento. Os dados são fornecidos pelo Yahoo Finance via "
    "yfinance e podem apresentar atrasos ou imprecisões. Sempre faça sua própria análise "
    "e considere seu perfil de risco antes de operar."
)
