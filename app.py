import streamlit as st
import pandas as pd
import requests
from google import genai

st.set_page_config(page_title="CryptoScalp AI - Bot Autónomo con Monitoreo", layout="wide")
st.title("⚡ CryptoScalp AI: Bot Autónomo de Futuros con Monitoreo de TP/SL & Telegram")

# Nueva API Key predeterminada configurada
DEFAULT_GEMINI_KEY = "AQ.Ab8RN6KeBis9-xaK9pTEYP60phvikSdZNXqhsIyYdgH1CKvFXw"
DEFAULT_TG_TOKEN = "8701955750:AAGa91am-9sLDbOuDfIuQSSDCEukO8XX2_0"
DEFAULT_TG_CHAT = "1690783827"

# Configuración de la barra lateral para credenciales dinámicas
st.sidebar.header("⚙️ Configuración del Sistema")

with st.sidebar.expander("🔑 Credenciales de API & Telegram"):
    input_gemini_key = st.text_input("Gemini API Key", value=DEFAULT_GEMINI_KEY, type="password")
    input_tg_token = st.text_input("Telegram Bot Token", value=DEFAULT_TG_TOKEN, type="password")
    input_tg_chat = st.text_input("Telegram Chat ID", value=DEFAULT_TG_CHAT)

# Inicializar cliente de Gemini con la llave activa
client = genai.Client(api_key=input_gemini_key)

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{input_tg_token}/sendMessage"
    payload = {"chat_id": input_tg_chat, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=15)
def obtener_mercado():
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=4)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            df = df[df['volume'] > 50000].sort_values(by='volume', ascending=False)
            if not df.empty:
                return df
    except Exception:
        pass

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
            df = df[df['volume'] > 50000].sort_values(by='volume', ascending=False)
            if not df.empty:
                return df
    except Exception:
        pass

    try:
        res = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 80}, timeout=6)
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
            return df_cleaned[df_cleaned['volume'] > 50000].sort_values(by='volume', ascending=False)
    except Exception:
        pass

    return pd.DataFrame()

df_mercado = obtener_mercado()

if "posicion_activa" not in st.session_state:
    st.session_state.posicion_activa = None

if df_mercado.empty:
    st.error("Error al conectar con el mercado de futuros. Por favor, recarga la página.")
else:
    with st.sidebar.expander("Estado de Telegram"):
        st.write(f"Chat ID Actual: {input_tg_chat}")
        if st.button("💬 Probar Conexión"):
            exito, det = enviar_telegram("🤖 *Prueba de conexión exitosa*")
            if exito: st.success("¡Enviado!")
            else: st.error(f"Error: {det}")

    modo = st.sidebar.radio("Modo:", ["🎛️ Manual y Gráficos", "🤖 Bot Autónomo con Monitoreo TP/SL"])

    if modo == "🎛️ Manual y Gráficos":
        estrategia = st.sidebar.selectbox("Estrategia:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_sel = st.sidebar.selectbox("Activo:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_sel].iloc[0]

        st.subheader(f"📊 Análisis Técnico: {par_sel}")
        if st.button(f"🚀 Analizar y Enviar a Telegram {par_sel}"):
            with st.spinner("Procesando análisis con IA..."):
                par_slash = par_sel.replace("USDT", "/USDT")
                prompt = f"""
                Actúa como trader institucional experto. Analiza el activo {par_sel}: Precio {datos_par['lastPrice']}, Cambio 24h {datos_par['priceChangePercent']}%, Volumen {datos_par['volume']} USD, Rango [{datos_par['lowPrice']} - {datos_par['highPrice']}]. Estrategia: {estrategia}.
                Genera la respuesta respetando EXACTAMENTE este formato estricto:
                🚨 SEÑAL IA BINANCE
                Activo: {par_slash} | [🟢 LONG o 🔴 SHORT]
                📊 Mercado: Futuros | ⏱ Temp: 15m

                📍 Niveles Operativos:
                ➡️ Entrada: [Precio exacto]
                🎯 TP1: [Valor exacto] | TP2: [Valor exacto]
                🛡️ SL: [Valor exacto]

                💡 Análisis: [Explicación ultracorta y directa en 1 sola línea del porqué]
                """
                try:
                    res = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    senal_manual = res.text
                    st.markdown(senal_manual)

                    enviado, err = enviar_telegram(senal_manual)
                    if enviado:
                        st.toast("¡Señal manual enviada a Telegram!", icon="✅")
                    else:
                        st.error(f"Error enviando a Telegram: {err}")
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
        st.subheader("🤖 Bot Autónomo de Alta Precisión con Monitoreo en Vivo")
        st.markdown("El bot analiza el mercado automáticamente con la estrategia óptima, abre la operación, la reporta a Telegram y **monitorea el precio en tiempo real para avisarte cuando se alcance el TP1, TP2 o Stop Loss**.")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            iniciar_bot = st.button("🚀 Iniciar Bot Autónomo")
        with col_btn2:
            detener_bot = st.button("🛑 Detener Bot")

        if detener_bot:
            st.session_state.posicion_activa = None
            st.warning("El bot autónomo ha sido detenido.")

        if st.session_state.posicion_activa is not None:
            pos = st.session_state.posicion_activa
            st.info(f"🛡️ **Monitoreando posición activa:** {pos['activo']} ({pos['tipo']}) | Entrada: {pos['entrada']} | TP1: {pos['tp1']} | TP2: {pos['tp2']} | SL: {pos['sl']}")
            
            df_actual = obtener_mercado()
            if not df_actual.empty and pos['activo'] in df_actual['symbol'].values:
                precio_actual = float(df_actual[df_actual['symbol'] == pos['activo']]['lastPrice'].values[0])
                st.metric(label=f"Precio en vivo de {pos['activo']}", value=f"${precio_actual:,.4f}")

                cumplio_objetivo = False
                if pos['tipo'] == 'LONG':
                    if precio_actual >= pos['tp2'] and not pos['tp2_alcanzado']:
                        msg = f"🎉 *¡TP2 ALCANZADO!* 🎯\n\nEl activo `{pos['activo']}` tocó el objetivo final de Take Profit 2.\n💰 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.success(msg)
                        pos['tp2_alcanzado'] = True
                        cumplio_objetivo = True
                    elif precio_actual >= pos['tp1'] and not pos['tp1_alcanzado']:
                        msg = f"✅ *¡TP1 ALCANZADO!* 🎯\n\nEl activo `{pos['activo']}` tocó el primer objetivo.\n💰 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.success(msg)
                        pos['tp1_alcanzado'] = True
                    elif precio_actual <= pos['sl']:
                        msg = f"❌ *¡STOP LOSS TOCADO!* 🛡️\n\nEl activo `{pos['activo']}` alcanzó el límite de protección.\n📉 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.error(msg)
                        st.session_state.posicion_activa = None
                else:
                    if precio_actual <= pos['tp2'] and not pos['tp2_alcanzado']:
                        msg = f"🎉 *¡TP2 ALCANZADO (SHORT)!* 🎯\n\nEl activo `{pos['activo']}` tocó el objetivo final.\n💰 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.success(msg)
                        pos['tp2_alcanzado'] = True
                        cumplio_objetivo = True
                    elif precio_actual <= pos['tp1'] and not pos['tp1_alcanzado']:
                        msg = f"✅ *¡TP1 ALCANZADO (SHORT)!* 🎯\n\nEl activo `{pos['activo']}` tocó el primer objetivo.\n💰 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.success(msg)
                        pos['tp1_alcanzado'] = True
                    elif precio_actual >= pos['sl']:
                        msg = f"❌ *¡STOP LOSS TOCADO (SHORT)!* 🛡️\n\nEl activo `{pos['activo']}` alcanzó el límite de protección.\n📉 *Precio Actual:* `{precio_actual}`"
                        enviar_telegram(msg)
                        st.error(msg)
                        st.session_state.posicion_activa = None

                if cumplio_objetivo and pos['tp2_alcanzado']:
                    st.session_state.posicion_activa = None

        if iniciar_bot and st.session_state.posicion_activa is None:
            with st.spinner("Ejecutando análisis automático del mercado de futuros..."):
                candidato = df_mercado[(df_mercado['priceChangePercent'] > 2.0) & (df_mercado['priceChangePercent'] < 15.0)].sort_values(by='volume', ascending=False)
                
                if candidato.empty:
                    st.warning("No se encontraron activos bajo la estrategia óptima en este ciclo.")
                else:
                    mejor_par = candidato.iloc[0]
                    par_slash = mejor_par['symbol'].replace("USDT", "/USDT")
                    precio_actual = float(mejor_par['lastPrice'])

                    prompt_pro = f"""
                    Actúa como un algoritmo cuantitativo institucional y trader experto en futuros de criptomonedas.
                    Selecciona los parámetros óptimos para la estrategia de Breakout de Alto Volumen en el activo:
                    - Activo: {mejor_par['symbol']}
                    - Precio Actual: {precio_actual}
                    - Variación 24h: {mejor_par['priceChangePercent']}%
                    
                    Genera la señal respetando EXACTAMENTE este formato:
                    🚨 SEÑAL IA BINANCE
                    Activo: {par_slash} | [🟢 LONG o 🔴 SHORT]
                    📊 Mercado: Futuros | ⏱ Temp: 15m

                    📍 Niveles Operativos:
                    ➡️ Entrada: [Precio exacto numérico]
                    🎯 TP1: [Valor exacto numérico] | TP2: [Valor exacto numérico]
                    🛡️ SL: [Valor exacto numérico]

                    💡 Análisis: [Explicación ultracorta y directa en 1 sola línea del porqué]
                    """

                    response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt_pro)
                    senal_generada = response.text

                    import re
                    nums = re.findall(r"[\d.]+", senal_generada)
                    try:
                        entrada_val = float(nums[0]) if len(nums) > 0 else precio_actual
                        tp1_val = float(nums[1]) if len(nums) > 1 else precio_actual * 1.01
                        tp2_val = float(nums[2]) if len(nums) > 2 else precio_actual * 1.02
                        sl_val = float(nums[3]) if len(nums) > 3 else precio_actual * 0.99
                        tipo_sen = "LONG" if "LONG" in senal_generada else "SHORT"
                    except Exception:
                        entrada_val = precio_actual
                        tp1_val = precio_actual * 1.01
                        tp2_val = precio_actual * 1.02
                        sl_val = precio_actual * 0.99
                        tipo_sen = "LONG"

                    st.session_state.posicion_activa = {
                        "activo": mejor_par['symbol'],
                        "tipo": tipo_sen,
                        "entrada": entrada_val,
                        "tp1": tp1_val,
                        "tp2": tp2_val,
                        "sl": sl_val,
                        "tp1_alcanzado": False,
                        "tp2_alcanzado": False
                    }

                    st.success(f"¡Bot Autónomo activado! Operación abierta en **{mejor_par['symbol']}**")
                    st.markdown(senal_generada)

                    enviado, err = enviar_telegram(senal_generada)
                    if enviado:
                        st.toast("¡Alerta enviada correctamente a Telegram!", icon="✅")
                    else:
                        st.error(f"Error enviando a Telegram: {err}")
