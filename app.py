import streamlit as st
import pandas as pd
import requests
from google import genai

st.set_page_config(page_title="CryptoScalp AI - Bot Cuantitativo Pro", layout="wide")
st.title("⚡ CryptoScalp AI: Bot Cuantitativo Autónomo de Alta Precisión")

API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

TELEGRAM_BOT_TOKEN = "8701955750:AAGa91am-9sLDbOuDfIuQSSDCEukO8XX2_0"
TELEGRAM_CHAT_ID = "1690783827"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=15)
def obtener_mercado():
    try:
        response = requests.get("https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=5)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            # Filtro estricto de liquidez para descartar ruido
            df = df[df['volume'] > 500000].sort_values(by='volume', ascending=False)
            if not df.empty:
                return df
    except Exception:
        pass
    return pd.DataFrame()

df_mercado = obtener_mercado()

if df_mercado.empty:
    st.error("Error al conectar con el mercado de futuros.")
else:
    st.sidebar.header("⚙️ Configuración del Sistema")
    
    with st.sidebar.expander("Estado de Telegram"):
        st.write("Estado: Conectado (Chat ID: 1690783827)")
        if st.button("💬 Probar Conexión"):
            exito, det = enviar_telegram("🤖 *Prueba de conexión exitosa*")
            if exito: st.success("¡Enviado!")
            else: st.error(f"Error: {det}")

    modo = st.sidebar.radio("Modo:", ["🎛️ Manual y Gráficos", "🤖 Bot Cuantitativo Autónomo"])

    if modo == "🎛️ Manual y Gráficos":
        estrategia = st.sidebar.selectbox("Estrategia:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_sel = st.sidebar.selectbox("Activo:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_sel].iloc[0]

        st.subheader(f"📊 Análisis Técnico: {par_sel}")
        if st.button(f"🚀 Analizar {par_sel}"):
            with st.spinner("Procesando..."):
                prompt = f"""
                Actúa como trader institucional experto. Analiza el activo {par_sel}: Precio {datos_par['lastPrice']}, Cambio 24h {datos_par['priceChangePercent']}%, Volumen {datos_par['volume']} USD, Rango [{datos_par['lowPrice']} - {datos_par['highPrice']}]. Estrategia: {estrategia}.
                Da un reporte institucional completo con:
                1. **SEÑAL DE OPERACIÓN** (LONG 🟢 / SHORT 🔴).
                2. **Análisis Técnico Profundo**.
                3. **Parámetros de Entrada, TP 1, TP 2 y Stop Loss**.
                4. **Gestión de Riesgo y Apalancamiento**.
                """
                try:
                    res = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    st.markdown(res.text)
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader(f"📈 Gráfica: {par_sel}")
        sim_tv = f"BINANCE:{par_sel}"
        st.components.v1.html(f"""
        <div style="height:500px;width:100%"><div id="tc" style="height:100%;width:100%"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">new TradingView.widget({{autosize:true, symbol:"{sim_tv}", interval:"15", timezone:"Etc/UTC", theme:"dark", style:"1", locale:"es", container_id:"tc"}});</script>
        </div>""", height=520)

    else:
        st.subheader("🤖 Bot Cuantitativo de Alta Precisión (Ahorro de API)")
        st.markdown("Filtra localmente todo el mercado mediante reglas estrictas de scalping y **solo consulta a Gemini cuando encuentra una oportunidad perfecta de alta probabilidad**, evitando agotar tus recursos.")

        filtro_estrategia = st.selectbox("Filtro Cuantitativo:", [
            "Breakout de Alto Volumen (Ruptura alcista con volumen institucional)",
            "Short Squeeze / Desplome Agresivo (Reversión a la baja por sobrecompra)",
            "Rebote en Soporte Extremo (Sobreventa con alto volumen acumulado)"
        ])

        if st.button("🔍 Escanear Mercado y Ejecutar Algoritmo"):
            with st.spinner("Escaneando y filtrando todo el mercado de futuros localmente..."):
                
                # FILTRADO LOCAL MATEMÁTICO (0 consumo de API de Gemini)
                if "Breakout" in filtro_estrategia:
                    # Busca el activo con mayor volumen y variación positiva sólida
                    candidato = df_mercado[(df_mercado['priceChangePercent'] > 2.0) & (df_mercado['priceChangePercent'] < 15.0)].sort_values(by='volume', ascending=False)
                elif "Short Squeeze" in filtro_estrategia:
                    # Busca sobrecompra extrema con giros de volumen
                    candidato = df_mercado[df_mercado['priceChangePercent'] > 5.0].sort_values(by='priceChangePercent', ascending=False)
                else:
                    # Reversión / Sobreventa (caídas fuertes con volumen)
                    candidato = df_mercado[df_mercado['priceChangePercent'] < -3.0].sort_values(by='priceChangePercent', ascending=True)

                if candidato.empty:
                    st.warning("El escaneo no encontró activos cumpliendo los parámetros estrictos en este ciclo. Intenta de nuevo en unos minutos.")
                else:
                    mejor_par = candidato.iloc[0]
                    
                    # ÚNICA CONSULTA A GEMINI (Solo por el candidato exacto validado)
                    prompt_pro = f"""
                    Actúa como un algoritmo cuantitativo institucional y trader experto en futuros de criptomonedas.
                    El escáner matemático ha aislado la siguiente oportunidad de alta precisión:
                    - Activo: {mejor_par['symbol']}
                    - Precio Actual: {mejor_par['lastPrice']}
                    - Variación 24h: {mejor_par['priceChangePercent']}%
                    - Volumen Negociado: {mejor_par['volume']} USDT
                    - Filtro Aplicado: {filtro_estrategia}
                    
                    Proporciona una señal altamente precisa, concisa y profesional estructurada estrictamente así:
                    1. **SEÑAL:** (LONG 🟢 o SHORT 🔴)
                    2. **ANÁLISIS TÉCNICO:** (Explicación concisa y directa de por qué el algoritmo seleccionó este setup).
                    3. **PRECIO DE ENTRADA:** [Valor exacto]
                    4. **TAKE PROFIT (TP):** [TP 1 y TP 2]
                    5. **STOP LOSS (SL):** [Valor estricto]
                    6. **APALANCAMIENTO RECOMENDADO:** [Ej: 10x - 20x]
                    """

                    response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt_pro)
                    senal_generada = response.text

                    st.success(f"¡Oportunidad validada con éxito en **{mejor_par['symbol']}**!")
                    st.markdown("### 🎯 Reporte de Señal Cuantitativa")
                    st.markdown(senal_generada)

                    # Envío automático a Telegram
                    msg_tg = f"🚨 *ALERTA CUANTITATIVA PRO* 🚨\n\n{senal_generada}"
                    enviado, err = enviar_telegram(msg_tg)
                    if enviado:
                        st.toast("¡Alerta enviada correctamente a Telegram!", icon="✅")
                    else:
                        st.error(f"No se pudo enviar a Telegram: {err}")
