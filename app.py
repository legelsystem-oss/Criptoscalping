import streamlit as st
import pandas as pd
import requests
import time
from google import genai
import re

st.set_page_config(page_title="CryptoScalp AI - Bot Autónomo con Monitoreo", layout="wide")
st.title("⚡ CryptoScalp AI: Bot Autónomo de Futuros con Monitoreo de TP/SL & Telegram")

# API Key predeterminada
DEFAULT_GEMINI_KEY = "AQ.Ab8RN6LUqj-Gvo5BTJkz3QD4iuRsyVEiBUyHY5ECWkQS_6LBJg"
DEFAULT_TG_TOKEN = "8701955750:AAGa91am-9sLDbOuDfIuQSSDCEukO8XX2_0"
DEFAULT_TG_CHAT = "1690783827"

# --- INICIALIZACIÓN DE MEMORIA ---
if "posicion_activa" not in st.session_state:
    st.session_state.posicion_activa = None
if "last_api_call" not in st.session_state:
    st.session_state.last_api_call = 0 

# Configuración de la barra lateral para credenciales y parámetros globales
st.sidebar.header("⚙️ Configuración del Sistema")

with st.sidebar.expander("🔑 Credenciales de API & Telegram"):
    input_gemini_key = st.text_input("Gemini API Key", value=DEFAULT_GEMINI_KEY, type="password")
    input_tg_token = st.text_input("Telegram Bot Token", value=DEFAULT_TG_TOKEN, type="password")
    input_tg_chat = st.text_input("Telegram Chat ID", value=DEFAULT_TG_CHAT)

# Selector de temporalidad global
st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Parámetros de Tiempo")
temporalidad = st.sidebar.selectbox(
    "Temporalidad de Análisis:", 
    ["5m", "15m", "30m", "1h", "4h", "1d"], 
    index=1
)

tv_intervals = {"5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}
tv_interval = tv_intervals[temporalidad]

# Inicializar cliente de Gemini
client = genai.Client(api_key=input_gemini_key)

# --- SELECTOR AUTOMÁTICO DE MODELOS Y ANTI-SPAM ---
def consultar_gemini(prompt):
    """Función que selecciona automáticamente el mejor modelo gratuito disponible."""
    tiempo_actual = time.time()
    
    if tiempo_actual - st.session_state.last_api_call < 15:
        return None, "⏳ *Protección Anti-Spam:* Espera al menos 15 segundos entre análisis.", None
    
    # Lista de modelos en orden de prioridad (Flash es ideal para scalping rápido y cuota gratis)
    modelos_gratuitos = [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    st.session_state.last_api_call = tiempo_actual
    ultimo_error = ""

    # El bot prueba los modelos en cascada hasta que uno funcione
    for modelo in modelos_gratuitos:
        try:
            response = client.models.generate_content(model=modelo, contents=prompt)
            return response.text, None, modelo # Retorna el texto y el modelo que funcionó
        except Exception as e:
            error_str = str(e).lower()
            # Si el error es por límite de cuota (429), detenemos la cascada y avisamos al usuario
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                return None, "⚠️ *Límite de API alcanzado:* Has superado las peticiones gratuitas. Espera 60 segundos.", None
            
            # Si el modelo no existe o no tiene soporte (404 / 400), guardamos el error y probamos el siguiente
            ultimo_error = str(e)
            continue
            
    # Si falla con todos los modelos de la lista
    return None, f"Error: Ningún modelo gratuito está disponible en tu API Key. Detalle: {ultimo_error}", None

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
    urls_respaldo = [
        "https://fapi.binance.com/fapi/v1/ticker/24hr",
        "https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr"
    ]
    
    for url in urls_respaldo:
        try:
            response = requests.get(url, timeout=4)
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
        except:
            continue

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
    except:
        pass

    return pd.DataFrame()

df_mercado = obtener_mercado()

if df_mercado.empty:
    st.error("Error al conectar con el mercado de futuros. Por favor, recarga la página.")
else:
    with st.sidebar.expander("Estado de Telegram"):
        st.write(f"Chat ID Actual: {input_tg_chat}")
        if st.button("💬 Probar Conexión"):
            exito, det = enviar_telegram("🤖 *Prueba de conexión exitosa desde CryptoScalp AI*")
            if exito: st.success("¡Enviado!")
            else: st.error(f"Error: {det}")

    st.sidebar.markdown("---")
    modo = st.sidebar.radio("Modo de Operación:", ["🎛️ Manual y Gráficos", "🤖 Bot Autónomo con Monitoreo TP/SL"])

    if modo == "🎛️ Manual y Gráficos":
        estrategia = st.sidebar.selectbox("Estrategia:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_sel = st.sidebar.selectbox("Activo a Operar:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_sel].iloc[0]

        st.subheader(f"📊 Análisis Técnico: {par_sel} ({temporalidad})")
        if st.button(f"🚀 Analizar y Enviar a Telegram {par_sel}"):
            with st.spinner("Buscando el mejor modelo y procesando análisis..."):
                par_slash = par_sel.replace("USDT", "/USDT")
                prompt = f"""
                Actúa como trader institucional experto. Analiza el activo {par_sel}: Precio {datos_par['lastPrice']}, Cambio 24h {datos_par['priceChangePercent']}%, Volumen {datos_par['volume']} USD. 
                - Estrategia: {estrategia}.
                - Marco temporal: {temporalidad}.
                Ajusta la amplitud de los Take Profits y el Stop Loss según la temporalidad ({temporalidad}).
                
                Genera la respuesta respetando EXACTAMENTE este formato estricto:
                🚨 SEÑAL IA BINANCE
                Activo: {par_slash} | [🟢 LONG o 🔴 SHORT]
                📊 Mercado: Futuros | ⏱ Temp: {temporalidad}

                📍 Niveles Operativos:
                ➡️ Entrada: [Precio exacto numérico]
                🎯 TP1: [Valor exacto numérico] | TP2: [Valor exacto numérico]
                🛡️ SL: [Valor exacto numérico]

                💡 Análisis: [Explicación ultracorta y directa en 1 sola línea del porqué]
                """
                
                resultado_ia, error_api, modelo_usado = consultar_gemini(prompt)
                
                if error_api:
                    st.error(error_api)
                else:
                    st.success(f"✅ Análisis completado automáticamente usando el modelo: **{modelo_usado}**")
                    st.markdown(resultado_ia)
                    enviado, err = enviar_telegram(resultado_ia)
                    if enviado:
                        st.toast("¡Señal manual enviada a Telegram!", icon="✅")
                    else:
                        st.error(f"Error enviando a Telegram: {err}")

        st.markdown("---")
        st.subheader(f"📈 Gráfica: {par_sel} ({temporalidad})")
        sim_tv = f"BINANCE:{par_sel}"
        st.components.v1.html(f"""
        <div style="height:500px;width:100%"><div id="tc" style="height:100%;width:100%"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">new TradingView.widget({{autosize:true, symbol:"{sim_tv}", interval:"{tv_interval}", timezone:"Etc/UTC", theme:"dark", style:"1", locale:"es", container_id:"tc"}});</script>
        </div>""", height=520)

    else:
        st.subheader(f"🤖 Bot Autónomo de Alta Precisión (Monitoreo en Vivo - {temporalidad})")
        st.markdown(f"El bot analizará el mercado enfocado en operaciones de **{temporalidad}**, abrirá la posición, la reportará a Telegram y monitoreará el precio en tiempo real.")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            iniciar_bot = st.button("🚀 Iniciar Bot Autónomo")
        with col_btn2:
            detener_bot = st.button("🛑 Detener Bot")

        if detener_bot:
            st.session_state.posicion_activa = None
            st.warning("El bot autónomo ha sido detenido.")

        # MONITOREO DE LA POSICIÓN (Sin gastar API de Gemini)
        if st.session_state.posicion_activa is not None:
            pos = st.session_state.posicion_activa
            st.info(f"🛡️ **Monitoreando posición activa ({temporalidad}):** {pos['activo']} ({pos['tipo']}) | Entrada: {pos['entrada']} | TP1: {pos['tp1']} | TP2: {pos['tp2']} | SL: {pos['sl']}")
            
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
            with st.spinner("Seleccionando el mejor modelo de IA y escaneando mercado..."):
                candidato = df_mercado[(df_mercado['priceChangePercent'] > 2.0) & (df_mercado['priceChangePercent'] < 15.0)].sort_values(by='volume', ascending=False)
                
                if candidato.empty:
                    st.warning("No se encontraron activos bajo la estrategia óptima en este ciclo.")
                else:
                    mejor_par = candidato.iloc[0]
                    par_slash = mejor_par['symbol'].replace("USDT", "/USDT")
                    precio_actual = float(mejor_par['lastPrice'])

                    prompt_pro = f"""
                    Actúa como un algoritmo cuantitativo institucional y trader experto en futuros de criptomonedas.
                    El escáner matemático ha aislado la siguiente oportunidad de alta precisión:
                    - Activo a Operar: {mejor_par['symbol']}
                    - Precio Actual: {precio_actual}
                    - Variación 24h: {mejor_par['priceChangePercent']}%
                    - Marco temporal operativo: {temporalidad}
                    
                    Ajusta los Take Profits y el Stop Loss a la volatilidad esperada para la temporalidad de {temporalidad}.
                    
                    Genera la señal respetando EXACTAMENTE este formato:
                    🚨 SEÑAL IA BINANCE
                    Activo: {par_slash} | [🟢 LONG o 🔴 SHORT]
                    📊 Mercado: Futuros | ⏱ Temp: {temporalidad}

                    📍 Niveles Operativos:
                    ➡️ Entrada: {precio_actual}
                    🎯 TP1: [Valor exacto numérico] | TP2: [Valor exacto numérico]
                    🛡️ SL: [Valor exacto numérico]

                    💡 Análisis: [Explicación ultracorta y directa en 1 sola línea del porqué]
                    """

                    # Consultar usando el selector automático de modelos
                    resultado_ia, error_api, modelo_usado = consultar_gemini(prompt_pro)

                    if error_api:
                        st.error(error_api)
                    else:
                        nums = re.findall(r"[\d.]+", resultado_ia)
                        try:
                            entrada_val = float(precio_actual)
                            tp1_val = float(nums[-3]) if len(nums) >= 3 else precio_actual * 1.01
                            tp2_val = float(nums[-2]) if len(nums) >= 2 else precio_actual * 1.02
                            sl_val = float(nums[-1]) if len(nums) >= 1 else precio_actual * 0.99
                            tipo_sen = "LONG" if "LONG" in resultado_ia else "SHORT"
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

                        st.success(f"¡Bot activado con el modelo **{modelo_usado}**! Operación abierta en **{mejor_par['symbol']}**")
                        st.markdown(resultado_ia)

                        enviado, err = enviar_telegram(resultado_ia)
                        if enviado:
                            st.toast("¡Alerta enviada correctamente a Telegram!", icon="✅")
                        else:
                            st.error(f"Error enviando a Telegram: {err}")
