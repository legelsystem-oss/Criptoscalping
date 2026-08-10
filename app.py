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

client = genai.Client(api_key=input_gemini_key)

# --- SELECTOR AUTOMÁTICO DE MODELOS Y ANTI-SPAM ---
def consultar_gemini(prompt):
    tiempo_actual = time.time()
    
    if tiempo_actual - st.session_state.last_api_call < 15:
        return None, "⏳ *Protección Anti-Spam:* Espera al menos 15 segundos entre análisis.", None
    
    modelos_gratuitos = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    st.session_state.last_api_call = tiempo_actual
    ultimo_error = ""

    for modelo in modelos_gratuitos:
        try:
            response = client.models.generate_content(model=modelo, contents=prompt)
            return response.text, None, modelo 
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                return None, "⚠️ *Límite de API alcanzado:* Has superado las peticiones gratuitas. Espera 60 segundos.", None
            ultimo_error = str(e)
            continue
            
    return None, f"Error: Ningún modelo disponible en tu API Key. Detalle: {ultimo_error}", None

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
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=5)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            for col in ['lastPrice', 'priceChangePercent', 'quoteVolume']:
                df[col] = df[col].astype(float)
            df = df.rename(columns={'quoteVolume': 'volume'})
            return df[df['volume'] > 50000].sort_values(by='volume', ascending=False)
    except:
        pass
    
    # Respaldo CoinGecko ampliado a 100 pares
    try:
        res = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 100}, timeout=6)
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

# --- MOTOR DE ANÁLISIS TÉCNICO MATEMÁTICO ---
def obtener_indicadores_tecnicos(symbol, interval):
    """Descarga velas japonesas y calcula EMA 9, EMA 21 y RSI 14 reales."""
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=50"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            datos = res.json()
            df = pd.DataFrame(datos, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
            df['close'] = df['close'].astype(float)
            
            # Calcular Medias Móviles Exponenciales
            df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
            
            # Calcular RSI (14)
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # Extraer los datos de la última vela cerrada
            ultima_vela = df.iloc[-1]
            return {
                "valido": True,
                "ema9": ultima_vela['EMA_9'],
                "ema21": ultima_vela['EMA_21'],
                "rsi": ultima_vela['RSI'],
                "precio": ultima_vela['close']
            }
    except Exception as e:
        pass
    return {"valido": False}

df_mercado = obtener_mercado()

if df_mercado.empty:
    st.error("Error al conectar con Binance. Por favor, recarga la página.")
else:
    with st.sidebar.expander("Estado de Telegram"):
        st.write(f"Chat ID Actual: {input_tg_chat}")
        if st.button("💬 Probar Conexión"):
            exito, det = enviar_telegram("🤖 *Prueba de conexión exitosa desde CryptoScalp AI*")
            if exito: st.success("¡Enviado!")
            else: st.error(f"Error: {det}")

    st.sidebar.markdown("---")
    modo = st.sidebar.radio("Modo de Operación:", ["🎛️ Manual y Gráficos", "🤖 Bot Autónomo con Monitoreo TP/SL"])

    # --- SECCIÓN 1: MANUAL ---
    if modo == "🎛️ Manual y Gráficos":
        estrategia = st.sidebar.selectbox("Estrategia:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_sel = st.sidebar.selectbox("Activo a Operar:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_sel].iloc[0]

        st.subheader(f"📊 Análisis Técnico: {par_sel} ({temporalidad})")
        if st.button(f"🚀 Analizar y Enviar a Telegram {par_sel}"):
            with st.spinner("Descargando indicadores técnicos reales y procesando con IA..."):
                ind = obtener_indicadores_tecnicos(par_sel, temporalidad)
                datos_tec_str = f"EMA 9: {ind['ema9']:.4f}, EMA 21: {ind['ema21']:.4f}, RSI: {ind['rsi']:.2f}" if ind['valido'] else "Sin datos técnicos"

                par_slash = par_sel.replace("USDT", "/USDT")
                prompt = f"""
                Actúa como trader institucional experto. Analiza el activo {par_sel}: Precio {datos_par['lastPrice']}, Cambio 24h {datos_par['priceChangePercent']}%, Volumen {datos_par['volume']} USD. 
                DATOS TÉCNICOS ({temporalidad}): {datos_tec_str}.
                - Estrategia: {estrategia}.
                
                Ajusta la amplitud de los Take Profits y el Stop Loss según la temporalidad y los datos técnicos proporcionados.
                
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
                    st.success(f"✅ Análisis profundo completado usando: **{modelo_usado}**")
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

    # --- SECCIÓN 2: BOT AUTOMÁTICO (AMPLIADO A 100 PARES) ---
    else:
        st.subheader(f"🤖 Bot Autónomo PRO 8.5/10 (Monitoreo en Vivo - {temporalidad})")
        st.markdown(f"El algoritmo ahora **lee los gráficos reales de hasta 100 pares** buscando la mejor oportunidad matemática (EMA 9/21 + RSI) antes de solicitar la validación a la IA.")

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            iniciar_long = st.button("🟢 Iniciar Bot (Buscar LONG)")
        with col_btn2:
            iniciar_short = st.button("🔴 Iniciar Bot (Buscar SHORT)")
        with col_btn3:
            detener_bot = st.button("🛑 Detener Bot Actual")

        accion_iniciar = "LONG" if iniciar_long else ("SHORT" if iniciar_short else None)

        if detener_bot:
            st.session_state.posicion_activa = None
            st.warning("El bot autónomo ha sido detenido y la posición cerrada del sistema.")

        # MONITOREO DE LA POSICIÓN ACTIVA
        if st.session_state.posicion_activa is not None:
            pos = st.session_state.posicion_activa
            icono_dir = "🟢" if pos['tipo'] == 'LONG' else "🔴"
            st.info(f"🛡️ **Monitoreando posición activa ({temporalidad}):** {pos['activo']} {icono_dir} ({pos['tipo']}) | Entrada: {pos['entrada']} | TP1: {pos['tp1']} | TP2: {pos['tp2']} | SL: {pos['sl']}")
            
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

        # INICIAR NUEVO ANÁLISIS AUTOMÁTICO 
        if accion_iniciar and st.session_state.posicion_activa is None:
            with st.spinner(f"Filtro Avanzado: Escaneando gráficas del TOP 100 de Binance buscando {accion_iniciar}..."):
                
                # Pre-filtrado por volumen para asegurar liquidez (AHORA REVISA HASTA 100 PARES)
                candidatos = df_mercado.head(100) 
                activo_encontrado = None
                datos_tecnicos = None

                # Búsqueda iterativa del setup perfecto
                for index, row in candidatos.iterrows():
                    simbolo = row['symbol']
                    ind = obtener_indicadores_tecnicos(simbolo, temporalidad)
                    
                    if not ind['valido']:
                        continue
                        
                    # Lógica Cuantitativa del Setup
                    if accion_iniciar == "LONG":
                        # Tendencia alcista (EMA 9 > EMA 21) y RSI con espacio para subir (< 70 y > 40)
                        if ind['ema9'] > ind['ema21'] and ind['rsi'] < 70 and ind['rsi'] > 40:
                            activo_encontrado = row
                            datos_tecnicos = ind
                            break # Encontramos el candidato ideal, detiene la búsqueda
                    else: # SHORT
                        # Tendencia bajista (EMA 9 < EMA 21) y RSI con espacio para caer (> 30 y < 60)
                        if ind['ema9'] < ind['ema21'] and ind['rsi'] > 30 and ind['rsi'] < 60:
                            activo_encontrado = row
                            datos_tecnicos = ind
                            break

                if activo_encontrado is None:
                    st.warning(f"No se detectó ningún cruce técnico limpio (EMA 9/21 + RSI) para {accion_iniciar} en los **100 principales pares** en este momento. El mercado puede estar consolidando o sin fuerza. Intenta otra temporalidad.")
                else:
                    simbolo_operar = activo_encontrado['symbol']
                    par_slash = simbolo_operar.replace("USDT", "/USDT")
                    precio_actual = datos_tecnicos['precio']
                    
                    st.success(f"🎯 Confluencia Matemática Encontrada en el Top 100: **{simbolo_operar}** (EMA 9: {datos_tecnicos['ema9']:.4f}, EMA 21: {datos_tecnicos['ema21']:.4f}, RSI: {datos_tecnicos['rsi']:.1f})")

                    prompt_pro = f"""
                    Actúa como un algoritmo cuantitativo institucional y trader experto en futuros.
                    El escáner matemático ha aislado esta oportunidad de alta precisión {accion_iniciar} tras analizar más de 100 activos:
                    - Activo: {simbolo_operar}
                    - Precio Actual: {precio_actual}
                    - Marco temporal operativo: {temporalidad}
                    - DATOS TÉCNICOS REALES: EMA 9 = {datos_tecnicos['ema9']}, EMA 21 = {datos_tecnicos['ema21']}, RSI (14) = {datos_tecnicos['rsi']}.
                    
                    Basándote en estos indicadores exactos, calcula los Take Profits y el Stop Loss milimétricos respetando la estructura técnica.
                    
                    Genera la señal respetando EXACTAMENTE este formato:
                    🚨 SEÑAL IA BINANCE
                    Activo: {par_slash} | [{'🟢 LONG' if accion_iniciar == 'LONG' else '🔴 SHORT'}]
                    📊 Mercado: Futuros | ⏱ Temp: {temporalidad}

                    📍 Niveles Operativos:
                    ➡️ Entrada: {precio_actual}
                    🎯 TP1: [Valor exacto numérico] | TP2: [Valor exacto numérico]
                    🛡️ SL: [Valor exacto numérico]

                    💡 Análisis: [Explicación ultracorta y directa en 1 sola línea del porqué basados en el cruce de EMA y RSI]
                    """

                    resultado_ia, error_api, modelo_usado = consultar_gemini(prompt_pro)

                    if error_api:
                        st.error(error_api)
                    else:
                        nums = re.findall(r"[\d.]+", resultado_ia)
                        try:
                            entrada_val = float(precio_actual)
                            # Extraemos los valores de TP y SL de la respuesta generada
                            tp1_val = float(nums[-3]) if len(nums) >= 3 else (precio_actual * 1.01 if accion_iniciar == 'LONG' else precio_actual * 0.99)
                            tp2_val = float(nums[-2]) if len(nums) >= 2 else (precio_actual * 1.02 if accion_iniciar == 'LONG' else precio_actual * 0.98)
                            sl_val = float(nums[-1]) if len(nums) >= 1 else (datos_tecnicos['ema21'] if accion_iniciar == 'LONG' else datos_tecnicos['ema21'])
                            tipo_sen = accion_iniciar
                        except Exception:
                            # Valores por defecto de seguridad si falla el parseo
                            entrada_val = precio_actual
                            tp1_val = precio_actual * 1.01 if accion_iniciar == 'LONG' else precio_actual * 0.99
                            tp2_val = precio_actual * 1.02 if accion_iniciar == 'LONG' else precio_actual * 0.98
                            sl_val = precio_actual * 0.99 if accion_iniciar == 'LONG' else precio_actual * 1.01
                            tipo_sen = accion_iniciar

                        # Guardamos la posición en memoria para que el sistema la empiece a monitorear
                        st.session_state.posicion_activa = {
                            "activo": simbolo_operar,
                            "tipo": tipo_sen,
                            "entrada": entrada_val,
                            "tp1": tp1_val,
                            "tp2": tp2_val,
                            "sl": sl_val,
                            "tp1_alcanzado": False,
                            "tp2_alcanzado": False
                        }

                        st.markdown(resultado_ia)

                        enviado, err = enviar_telegram(resultado_ia)
                        if enviado:
                            st.toast("¡Alerta enviada correctamente a Telegram!", icon="✅")
                        else:
                            st.error(f"Error enviando a Telegram: {err}")
