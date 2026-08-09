import streamlit as st
import pandas as pd
import requests
from google import genai

st.set_page_config(page_title="CryptoScalp AI - Directo al Grano", layout="wide")
st.title("⚡ CryptoScalp AI: Escáner Rápido & Alertas Telegram")

API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

TELEGRAM_BOT_TOKEN = "AQUÍ_TU_TOKEN_DE_TELEGRAM"
TELEGRAM_CHAT_ID = "AQUÍ_TU_CHAT_ID"

def enviar_telegram(mensaje):
    if TELEGRAM_BOT_TOKEN == "AQUÍ_TU_TOKEN_DE_TELEGRAM":
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=15)
def obtener_mercado():
    try:
        response = requests.get("https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=6)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            return df[df['volume'] > 100000].sort_values(by='volume', ascending=False)
    except Exception:
        pass
    return pd.DataFrame()

df_mercado = obtener_mercado()

if df_mercado.empty:
    st.error("Error al conectar con el mercado.")
else:
    st.sidebar.header("⚙️ Configuración")
    input_token = st.sidebar.text_input("Bot Token Telegram", value=TELEGRAM_BOT_TOKEN, type="password")
    input_chat = st.sidebar.text_input("Chat ID Telegram", value=TELEGRAM_CHAT_ID)
    if input_token: TELEGRAM_BOT_TOKEN = input_token
    if input_chat: TELEGRAM_CHAT_ID = input_chat

    estrategia = st.sidebar.selectbox("Estrategia:", ["Momentum (Volumen)", "Reversión"])
    lista_pares = df_mercado['symbol'].tolist()
    par_seleccionado = st.sidebar.selectbox("Activo Manual:", options=lista_pares)
    datos_par = df_mercado[df_mercado['symbol'] == par_seleccionado].iloc[0]

    st.subheader("🤖 Escáner Rápido (Directo al Grano)")
    
    if st.button("🚀 Escanear y Obtener Señal"):
        with st.spinner("Analizando..."):
            candidato = df_mercado.sort_values(by='priceChangePercent', ascending=False).iloc[0] if estrategia == "Momentum (Volumen)" else df_mercado.sort_values(by='priceChangePercent', ascending=True).iloc[0]

            prompt = f"""
            Actúa como trader experto en futuros. Analiza brevemente este activo: {candidato['symbol']}, Precio: {candidato['lastPrice']}, Cambio 24h: {candidato['priceChangePercent']}%.
            Da una respuesta EXTREMADAMENTE BREVE y directa al grano con este formato exacto:
            - **SEÑAL:** (LONG 🟢 / SHORT 🔴)
            - **ENTRADA:** [Precio]
            - **TP:** [Precio objetivo]
            - **SL:** [Precio límite]
            Nada de explicaciones largas.
            """

            try:
                response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                resultado_ia = response.text
                
                st.markdown(f"### 🎯 Señal para {candidato['symbol']}")
                st.markdown(resultado_ia)

                mensaje_telegram = f"🚨 *SEÑAL SCALPING* 🚨\n\n{resultado_ia}"
                enviado = enviar_telegram(mensaje_telegram)
                if enviado:
                    st.toast("¡Enviado a Telegram!", icon="✅")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.subheader(f"📈 Gráfica: {par_seleccionado}")
    simbolo_tv = f"BINANCE:{par_seleccionado}"
    
    html_tradingview = f"""
    <div class="tradingview-widget-container" style="height:450px;width:100%">
      <div id="tv_chart_container" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{"autosize": true, "symbol": "{simbolo_tv}", "interval": "15", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "es", "toolbar_bg": "#1e222d", "container_id": "tv_chart_container"}});
      </script>
    </div>
    """
    st.components.v1.html(html_tradingview, height=470)
