import streamlit as st
import pandas as pd
import requests
from google import genai

st.set_page_config(page_title="CryptoScalp AI - Bot Automático & Manual", layout="wide")
st.title("⚡ CryptoScalp AI: Terminal Manual, Gráfica & Bot Automático Telegram")

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
        response = requests.get("https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=5)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            df = df[df['volume'] > 10000].sort_values(by='volume', ascending=False)
            if not df.empty:
                return df
    except Exception:
        pass

    try:
        res = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 50}, timeout=6)
        if res.status_code == 200:
            data = res.json()
            df_alt = pd.DataFrame(data)
            df_alt['symbol'] = df_alt['symbol'].str.upper() + 'USDT'
            df_cleaned = pd.DataFrame({
                'symbol': df_alt['symbol'],
                'lastPrice': df_alt['current_price'],
                'priceChangePercent': df_alt['price_change_percentage_24h'],
                'volume': df_alt['total_volume'],
                'highPrice': df_alt['current_price'] * 1.02,
                'lowPrice': df_alt['current_price'] * 0.98
            })
            return df_cleaned[df_cleaned['volume'] > 10000].sort_values(by='volume', ascending=False)
    except Exception:
        pass

    return pd.DataFrame()

df_mercado = obtener_mercado()

if df_mercado.empty:
    st.error("Error al conectar con el mercado. Revisa tu red o intenta recargar en unos segundos.")
else:
    st.sidebar.header("⚙️ Configuración del Sistema")
    input_token = st.sidebar.text_input("Bot Token Telegram", value=TELEGRAM_BOT_TOKEN, type="password")
    input_chat = st.sidebar.text_input("Chat ID Telegram", value=TELEGRAM_CHAT_ID)
    if input_token: TELEGRAM_BOT_TOKEN = input_token
    if input_chat: TELEGRAM_CHAT_ID = input_chat

    modo_operacion = st.sidebar.radio("Modo de Operación:", ["🎛️ Panel Manual y Gráficos", "🤖 Bot Automático (Escáner & Alertas)"])

    if modo_operacion == "🎛️ Panel Manual y Gráficos":
        st.sidebar.markdown("---")
        estrategia = st.sidebar.selectbox("Estrategia Técnica:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_seleccionado = st.sidebar.selectbox("Seleccionar Activo Manual:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_seleccionado].iloc[0]

        st.subheader(f"📊 Análisis Manual para: {par_seleccionado}")
        
        if st.button(f"🚀 Ejecutar Análisis Completo de IA para {par_seleccionado}"):
            with st.spinner("Analizando activo en profundidad..."):
                prompt = f"""
                Actúa como un trader institucional experto en futuros de criptomonedas y análisis técnico avanzado.
                Analiza el siguiente activo del mercado de futuros:
                - Activo: {par_seleccionado}
                - Precio Actual: {datos_par['lastPrice']}
                - Cambio 24h: {datos_par['priceChangePercent']}%
                - Volumen 24h: {datos_par['volume']} USD
                - Máximo / Mínimo 24h: {datos_par['highPrice']} / {datos_par['lowPrice']}
                - Estrategia técnica aplicada: {estrategia}
                
                Por favor, emite un veredicto operativo formal, profundo y detallado que contenga obligatoriamente:
                1. **SEÑAL DE OPERACIÓN:** (Indicar claramente en grande si es una señal **LONG 🟢** o **SHORT 🔴** o **NEUTRAL ⚪**).
                2. **Análisis Técnico Completo:** Fundamenta la dirección basándote en la acción del precio, el volumen, la volatilidad y la estrategia elegida.
                3. **Parámetros de Entrada y Salida:** 
                   - Precio de Entrada Sugerido
                   - Take Profit (TP) 1 y TP 2
                   - Stop Loss (SL) estricto
                4. **Nivel de Riesgo / Apalancamiento recomendado**.
                """

                try:
                    response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    st.success("¡Análisis completado!")
                    st.markdown("### 🎯 Reporte Institucional y Gestión de Riesgo")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Error al conectar con Gemini: {e}")

        st.markdown("---")
        st.subheader(f"📈 Gráfica en Vivo: {par_seleccionado}")
        simbolo_tv = f"BINANCE:{par_seleccionado}"
        
        html_tradingview = f"""
        <div class="tradingview-widget-container" style="height:500px;width:100%">
          <div id="tv_chart_container" style="height:100%;width:100%"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{"autosize": true, "symbol": "{simbolo_tv}", "interval": "15", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "es", "toolbar_bg": "#1e222d", "container_id": "tv_chart_container"}});
          </script>
        </div>
        """
        st.components.v1.html(html_tradingview, height=520)

    else:
        st.subheader("🤖 Bot Automático de Alertas (Telegram)")
        st.markdown("Este bot escanea de forma autónoma el mercado buscando las mejores oportunidades de scalping, realiza el análisis completo con IA y envía la señal directo a tu Telegram sin agotar tus recursos.")

        estrategia_bot = st.selectbox("Estrategia del Bot:", ["Momentum (Ruptura de Volumen)", "Reversión Extrema"])

        if st.button("🚀 Activar Escaneo Automático y Enviar Alerta"):
            with st.spinner("Escaneando mercado y procesando con IA..."):
                candidato = df_mercado.sort_values(by='priceChangePercent', ascending=False).iloc[0] if estrategia_bot == "Momentum (Ruptura de Volumen)" else df_mercado.sort_values(by='priceChangePercent', ascending=True).iloc[0]

                prompt = f"""
                Actúa como un trader institucional experto en futuros de criptomonedas.
                El bot automático ha detectado una oportunidad en:
                - Activo: {candidato['symbol']}
                - Precio Actual: {candidato['lastPrice']}
                - Cambio 24h: {candidato['priceChangePercent']}%
                - Volumen 24h: {candidato['volume']} USD
                
                Emite un veredicto operativo formal, detallado y profesional que contenga:
                1. **SEÑAL DE OPERACIÓN:** (LONG 🟢 o SHORT 🔴).
                2. **Análisis Técnico Completo:** Fundamenta la oportunidad detectada.
                3. **Parámetros:** Precio de Entrada, Take Profit (TP) y Stop Loss (SL).
                4. **Gestión de Riesgo y Apalancamiento.**
                """

                try:
                    response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    resultado_ia = response.text
                    
                    st.success(f"¡Oportunidad detectada y analizada en {candidato['symbol']}!")
                    st.markdown("### 📊 Reporte del Bot Automático")
                    st.markdown(resultado_ia)

                    mensaje_telegram = f"🚨 *BOT AUTOMÁTICO - SEÑAL DE SCALPING* 🚨\n\n{resultado_ia}"
                    enviado = enviar_telegram(mensaje_telegram)
                    if enviado:
                        st.toast("¡Alerta enviada exitosamente a tu Telegram!", icon="✅")
                    else:
                        st.warning("El análisis se generó, pero verifica tus credenciales de Telegram.")
                except Exception as e:
                    st.error(f"Error al procesar con Gemini: {e}")
