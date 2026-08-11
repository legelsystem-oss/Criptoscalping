import streamlit as st
import pandas as pd
import requests
import time
from google import genai
import re
import websocket
import json
import threading

st.set_page_config(page_title="CryptoScalp AI - Bot Autónomo con Monitoreo", layout="wide")
st.title("⚡ CryptoScalp AI: Bot Autónomo de Futuros con Monitoreo WSS & Telegram")

# API Key y Tokens
DEFAULT_GEMINI_KEY = "AQ.Ab8RN6Jjk1BAF4lb0u00J_0cb-nRMEj0MHGHggm5WxVBgwiNgA"
DEFAULT_TG_TOKEN = "8701955750:AAGa91am-9sLDbOuDfIuQSSDCEukO8XX2_0"
DEFAULT_TG_CHAT = "1690783827"

# --- INICIALIZACIÓN DE MEMORIA Y ESTADOS ---
if "posicion_activa" not in st.session_state:
    st.session_state.posicion_activa = None
if "last_api_call" not in st.session_state:
    st.session_state.last_api_call = 0 
if "precios_ws" not in st.session_state:
    st.session_state.precios_ws = {} 

# Configuración de la barra lateral
st.sidebar.header("⚙️ Configuración del Sistema")

with st.sidebar.expander("🔑 Credenciales de API & Telegram"):
    input_gemini_key = st.text_input("Gemini API Key", value=DEFAULT_GEMINI_KEY, type="password")
    input_tg_token = st.text_input("Telegram Bot Token", value=DEFAULT_TG_TOKEN, type="password")
    input_tg_chat = st.text_input("Telegram Chat ID", value=DEFAULT_TG_CHAT)
    
    # Guardar en memoria para que el hilo secundario tenga acceso
    st.session_state.tg_token = input_tg_token
    st.session_state.tg_chat = input_tg_chat

# --- HILO EN SEGUNDO PLANO (WEBSOCKET) ---
def enviar_telegram_ws(mensaje):
    token = st.session_state.get('tg_token', "")
    chat = st.session_state.get('tg_chat', "")
    if token and chat:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat, "text": mensaje, "parse_mode": "Markdown"}, timeout=5)
        except: pass

def iniciar_websocket():
    def on_message(ws, mensaje):
        try:
            datos = json.loads(mensaje)
            for item in datos:
                simbolo = item['s']
                if simbolo.endswith('USDT'):
                    precio = float(item['c'])
                    st.session_state.precios_ws[simbolo] = precio
                    
                    pos = st.session_state.posicion_activa
                    if pos and pos['activo'] == simbolo:
                        cumplio_objetivo = False
                        
                        if pos['tipo'] == 'LONG':
                            if precio >= pos['tp2'] and not pos['tp2_alcanzado']:
                                enviar_telegram_ws(f"🎉 *¡TP2 ALCANZADO!* 🎯\n\nEl activo `{pos['activo']}` tocó el objetivo final.\n💰 *Precio:* `{precio}`")
                                pos['tp2_alcanzado'] = True
                                cumplio_objetivo = True
                            elif precio >= pos['tp1'] and not pos['tp1_alcanzado']:
                                enviar_telegram_ws(f"✅ *¡TP1 ALCANZADO!* 🎯\n\nEl activo `{pos['activo']}` tocó el primer objetivo.\n💰 *Precio:* `{precio}`")
                                pos['tp1_alcanzado'] = True
                            elif precio <= pos['sl']:
                                enviar_telegram_ws(f"❌ *¡STOP LOSS TOCADO!* 🛡️\n\nEl activo `{pos['activo']}` alcanzó la protección.\n📉 *Precio:* `{precio}`")
                                st.session_state.posicion_activa = None
                        else: # SHORT
                            if precio <= pos['tp2'] and not pos['tp2_alcanzado']:
                                enviar_telegram_ws(f"🎉 *¡TP2 ALCANZADO (SHORT)!* 🎯\n\nEl activo `{pos['activo']}` tocó el objetivo final.\n💰 *Precio:* `{precio}`")
                                pos['tp2_alcanzado'] = True
                                cumplio_objetivo = True
                            elif precio <= pos['tp1'] and not pos['tp1_alcanzado']:
                                enviar_telegram_ws(f"✅ *¡TP1 ALCANZADO (SHORT)!* 🎯\n\nEl activo `{pos['activo']}` tocó el primer objetivo.\n💰 *Precio:* `{precio}`")
                                pos['tp1_alcanzado'] = True
                            elif precio >= pos['sl']:
                                enviar_telegram_ws(f"❌ *¡STOP LOSS TOCADO (SHORT)!* 🛡️\n\nEl activo `{pos['activo']}` alcanzó la protección.\n📉 *Precio:* `{precio}`")
                                st.session_state.posicion_activa = None
                                
                        if cumplio_objetivo and pos['tp2_alcanzado']:
                            st.session_state.posicion_activa = None
        except:
            pass

    def run():
        ws = websocket.WebSocketApp("wss://fstream.binance.com/ws/!miniTicker@arr", on_message=on_message)
        ws.run_forever()

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()

if "ws_iniciado" not in st.session_state:
    iniciar_websocket()
    st.session_state.ws_iniciado = True

# --- SELECTORES DE INTERFAZ ---
st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Mercado a Operar")
tipo_mercado = st.sidebar.radio("Selecciona el Mercado:", ["📊 Futuros Tradicional (Top 100 Liquidez)", "🚀 Alpha Futures (Gemas/Alta Volatilidad)"])

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Parámetros de Tiempo")
temporalidad = st.sidebar.selectbox("Temporalidad de Análisis:", ["5m", "15m", "30m", "1h", "4h", "1d"], index=1)

st.sidebar.subheader("🎯 Gestión de Riesgo (Manual)")
ratio_rr = st.sidebar.selectbox("Ratio Riesgo/Beneficio (R:R) exigido:", ["1:1", "1:1.5", "1:2", "1:3"], index=1)

tv_intervals = {"5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}
tv_interval = tv_intervals[temporalidad]

client = genai.Client(api_key=input_gemini_key)

# --- MOTOR CORREGIDO IA ---
def consultar_gemini(prompt):
    tiempo_actual = time.time()
    if tiempo_actual - st.session_state.last_api_call < 15:
        return None, "⏳ *Protección Anti-Spam:* Espera al menos 15 segundos entre análisis.", None
    
    # Modelos vigentes y estables (Soluciona el Error 404)
    modelos_gratuitos = ["gemini-1.5-flash", "gemini-1.5-pro"]
    
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
            
    return None, f"Error real de conexión con la IA. Detalle: {ultimo_error}", None

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{input_tg_token}/sendMessage"
    payload = {"chat_id": input_tg_chat, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

# --- CONEXIÓN ROBUSTA AL MERCADO ---
@st.cache_data(ttl=15)
def obtener_mercado():
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=10)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df = df[df['symbol'].str.endswith('USDT')].copy()
            for col in ['lastPrice', 'priceChangePercent', 'quoteVolume']:
                df[col] = df[col].astype(float)
            df = df.rename(columns={'quoteVolume': 'volume'})
            return df[df['volume'] > 50000].sort_values(by='volume', ascending=False)
        else:
            st.warning(f"Binance devolvió el código de error: {response.status_code}")
    except Exception as e:
        st.error(f"Fallo de red al conectar con Binance: {e}")
    
    try:
        res = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 200}, timeout=10)
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
        else:
            st.warning(f"CoinGecko devolvió el código de error: {res.status_code}")
    except Exception as e:
        st.error(f"Fallo de red al conectar con CoinGecko: {e}")
        
    return pd.DataFrame()

def obtener_indicadores_tecnicos(symbol, interval):
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=50"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            datos = res.json()
            df = pd.DataFrame(datos, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
            for col in ['close', 'high', 'low']:
                df[col] = df[col].astype(float)
            
            df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
            
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            df['RSI'] = 100 - (100 / (1 + rs))

            df['SMA_20'] = df['close'].rolling(window=20).mean()
            df['STD_20'] = df['close'].rolling(window=20).std()
            df['BB_UPPER'] = df['SMA_20'] + (df['STD_20'] * 2)
            df['BB_LOWER'] = df['SMA_20'] - (df['STD_20'] * 2)

            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['ATR'] = df['tr'].rolling(14).mean()
            
            ultima_vela = df.iloc[-1]
            return {
                "valido": True, "ema9": ultima_vela['EMA_9'], "ema21": ultima_vela['EMA_21'],
                "rsi": ultima_vela['RSI'], "bb_upper": ultima_vela['BB_UPPER'], "bb_lower": ultima_vela['BB_LOWER'],
                "sma20": ultima_vela['SMA_20'], "atr": ultima_vela['ATR'], "precio": ultima_vela['close']
            }
    except Exception as e:
        pass
    return {"valido": False}

ALPHA_FUTURES_SYMBOLS = [
    'PLAYUSDT', 'TACUSDT', 'HUSDT', 'GRVTUSDT', 'DOODUSDT', 'MOODENGUSDT', 'GOATUSDT', 
    'ACTUSDT', 'PNUTUSDT', 'CETUSUSDT', 'COWUSDT', 'TROYUSDT', 'SWELLUSDT', '1000CATUSDT', 
    'HMSTRUSDT', 'NEIROUSDT', 'NEIROETHUSDT', 'BANANAUSDT', 'TONUSDT', 'NOTUSDT', 'DOGSUSDT', 
    'POLUSDT', 'ZROUSDT', 'LISTAUSDT', 'IOUSDT', 'BBUSDT', 'REZUSDT', 'OMNIUSDT', 'TAOUSDT', 
    'ENAUSDT', 'ETHFIUSDT', 'BOMEUSDT', 'AEVOUSDT', 'PORTALUSDT', 'PIXELUSDT', 'ALTUSDT', 
    'MANTAUSDT', 'XAIUSDT', 'AIUSDT', 'NFPUSDT', 'ACEUSDT', 'JTOUSDT', 'ORDIUSDT', '1000RATSUSDT', 
    '1000SATSUSDT', 'WIFUSDT', 'MYROUSDT', 'TOKENUSDT', 'MEMEUSDT', 'TIAUSDT', 'PYTHUSDT', 
    'JUPUSDT', 'ZETAUSDT', 'STRKUSDT', 'ONDOUSDT', 'MAVIAUSDT', 'BIGTIMEUSDT', 'POLYXUSDT', 
    'METISUSDT', 'BICOUSDT', 'ARKMUSDT', 'PENDLEUSDT', 'SEIUSDT', 'SUIUSDT', 'EDUUSDT', 'IDUSDT',
    'HOOKUSDT', 'GALUSDT', 'LOKAUSDT', 'VOXELUSDT', 'HIGHUSDT', 'LITUSDT', 'SFPUSDT', 'TWTUSDT',
    'MEWUSDT', 'TURBOUSDT', 'POPCATUSDT', '1000PEPEUSDT', '1000FLOKIUSDT', '1000BONKUSDT',
    'CLOUSDT', 'ONUSDT'
]

df_mercado = obtener_mercado()

if not df_mercado.empty:
    if "Alpha" in tipo_mercado:
        df_mercado = df_mercado[df_mercado['symbol'].isin(ALPHA_FUTURES_SYMBOLS)]
    else:
        df_mercado = df_mercado.head(100)

if df_mercado.empty:
    st.error("No se pudo cargar el mercado. Revisa los mensajes de error superiores para depurar la conexión.")
else:
    with st.sidebar.expander("Estado de Telegram"):
        st.write(f"Chat ID Actual: {input_tg_chat}")
        if st.button("💬 Probar Conexión"):
            exito, det = enviar_telegram("🤖 *Prueba de conexión exitosa desde CryptoScalp AI*")
            if exito: st.success("¡Enviado!")
            else: st.error(f"Error: {det}")

    mercado_contexto = "Mercado Tradicional" if "Tradicional" in tipo_mercado else "Binance Alpha Futures (Activos emergentes con extrema volatilidad. Calcula Stop Loss ligeramente más amplios)."

    st.sidebar.markdown("---")
    modo = st.sidebar.radio("Modo de Operación:", ["🎛️ Manual PRO y Gráficos", "🤖 Bot Autónomo con Monitoreo TP/SL"])

    # --- SECCIÓN 1: MANUAL PRO (Mantenida intacta como solicitaste) ---
    if modo == "🎛️ Manual PRO y Gráficos":
        estrategia = st.sidebar.selectbox("Estrategia:", ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango (ATR) y Volumen", "Reversión en Bandas de Bollinger"])
        lista_pares = df_mercado['symbol'].tolist()
        par_sel = st.sidebar.selectbox("Activo a Operar:", options=lista_pares)
        datos_par = df_mercado[df_mercado['symbol'] == par_sel].iloc[0]

        if "Cruce" in estrategia: tv_studies = '["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]'
        elif "Bollinger" in estrategia: tv_studies = '["BB@tv-basicstudies", "RSI@tv-basicstudies"]'
        else: tv_studies = '["Volume@tv-basicstudies"]'

        st.subheader(f"📊 Análisis Técnico PRO: {par_sel} ({temporalidad})")
        st.caption(f"Mercado Seleccionado: {tipo_mercado}")
        
        if st.button(f"🚀 Analizar y Enviar a Telegram {par_sel}"):
            with st.spinner("Realizando análisis Top-Down y calculando riesgo estricto..."):
                ind = obtener_indicadores_tecnicos(par_sel, temporalidad)
                macro_ind = obtener_indicadores_tecnicos(par_sel, "4h")
                
                tendencia_macro = "Alcista 🟢" if macro_ind['valido'] and macro_ind['precio'] > macro_ind['ema21'] else "Bajista 🔴"

                if ind['valido']:
                    if "Bollinger" in estrategia: datos_tec_str = f"BB Upper: {ind['bb_upper']:.4f}, BB Lower: {ind['bb_lower']:.4f}, SMA 20: {ind['sma20']:.4f}, RSI: {ind['rsi']:.2f}"
                    elif "Ruptura" in estrategia: datos_tec_str = f"ATR (Volatilidad): {ind['atr']:.4f}, Precio: {ind['precio']:.4f}"
                    else: datos_tec_str = f"EMA 9: {ind['ema9']:.4f}, EMA 21: {ind['ema21']:.4f}, RSI: {ind['rsi']:.2f}"
                else: datos_tec_str = "Sin datos técnicos"

                par_slash = par_sel.replace("USDT", "/USDT")
                prompt = f"""
                Actúa como trader institucional experto. Analiza el activo {par_sel}: Precio {datos_par['lastPrice']}, Cambio {datos_par['priceChangePercent']}%, Volumen {datos_par['volume']}. 
                ENTORNO: {mercado_contexto}
                MACRO (4H): La tendencia es {tendencia_macro}.
                DATOS TÉCNICOS ({temporalidad}): {datos_tec_str}.
                Estrategia Seleccionada: {estrategia}.
                R:R exigido: {ratio_rr}.
                
                Instrucciones: Define LONG o SHORT. Calcula Take Profits y Stop Loss respetando el Ratio Riesgo/Beneficio estricto de {ratio_rr}.
                Formato EXACTO:
                🚨 SEÑAL IA BINANCE
                Activo: {par_slash} | [🟢 LONG o 🔴 SHORT]
                📊 Mercado: {'Alpha Futures' if 'Alpha' in tipo_mercado else 'Futuros'} | ⏱ Temp: {temporalidad}

                📍 Niveles Operativos:
                ➡️ Entrada: [Precio numérico]
                🎯 TP1: [Valor numérico] | TP2: [Valor numérico]
                🛡️ SL: [Valor numérico]

                💡 Análisis: [1 línea de explicación de la estrategia]
                """
                
                resultado_ia, error_api, modelo_usado = consultar_gemini(prompt)
                
                if error_api: st.error(error_api)
                else:
                    st.success(f"✅ Análisis completado usando: **{modelo_usado}**")
                    st.markdown(resultado_ia)
                    enviado, err = enviar_telegram(resultado_ia)
                    if enviado: st.toast("¡Señal enviada a Telegram!", icon="✅")

        st.markdown("---")
        st.subheader(f"📈 Gráfica Inteligente: {par_sel} ({temporalidad})")
        st.components.v1.html(f"""
        <div style="height:500px;width:100%"><div id="tc" style="height:100%;width:100%"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
            autosize:true, symbol:"BINANCE:{par_sel}", interval:"{tv_interval}", timezone:"Etc/UTC", theme:"dark", style:"1", locale:"es", studies: {tv_studies}, container_id:"tc"
        }});
        </script></div>""", height=520)

    # --- SECCIÓN 2: BOT AUTOMÁTICO (WSS) ---
    else:
        st.subheader(f"🤖 Bot Autónomo de Futuros (Monitoreo en Vivo - {temporalidad})")
        st.caption(f"Escaneando: **{tipo_mercado}** | API Status: 🟢 Protegido por WebSocket")
        
        tipo_motor = st.radio("🧠 Elige el Motor de Búsqueda:", ["🔥 Básico (Rápido: Busca solo por Volumen y Momentum)", "🧠 PRO (Estricto: Busca cruce de EMA 9/21 y RSI)"])

        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1: iniciar_long = st.button("🟢 Buscar Oportunidad LONG")
        with col_btn2: iniciar_short = st.button("🔴 Buscar Oportunidad SHORT")
        with col_btn3: detener_bot = st.button("🛑 Detener Bot Actual")

        accion_iniciar = "LONG" if iniciar_long else ("SHORT" if iniciar_short else None)

        if detener_bot:
            st.session_state.posicion_activa = None
            st.warning("El bot autónomo ha sido detenido.")

        if st.session_state.posicion_activa is not None:
            pos = st.session_state.posicion_activa
            icono_dir = "🟢" if pos['tipo'] == 'LONG' else "🔴"
            st.info(f"🛡️ **Monitoreando posición en 2º plano:** {pos['activo']} {icono_dir} ({pos['tipo']}) | Entrada: {pos['entrada']} | TP1: {pos['tp1']} | TP2: {pos['tp2']} | SL: {pos['sl']}")
            
            precio_en_vivo = st.session_state.precios_ws.get(pos['activo'], 0.0)
            if precio_en_vivo > 0:
                st.metric(label=f"Precio en vivo de {pos['activo']}", value=f"${precio_en_vivo:,.4f}")
                st.caption("⚡ Actualizando por WebSocket (Cero latencia).")
            else:
                st.warning("Esperando primeros datos del servidor de Binance...")

        if accion_iniciar and st.session_state.posicion_activa is None:
            with st.spinner(f"Escaneando el mercado con el motor: {tipo_motor.split(' ')[1]}..."):
                activo_encontrado, datos_tecnicos, precio_actual, prompt_pro = None, None, 0.0, ""
                
                if "Básico" in tipo_motor:
                    candidatos = df_mercado.copy()
                    if accion_iniciar == "LONG": candidatos = candidatos[(candidatos['priceChangePercent'] > 2.0) & (candidatos['priceChangePercent'] < 15.0)]
                    else: candidatos = candidatos[candidatos['priceChangePercent'] < -2.0]
                    
                    if not candidatos.empty:
                        activo_encontrado = candidatos.iloc[0]
                        simbolo_operar = activo_encontrado['symbol']
                        precio_actual = float(activo_encontrado['lastPrice'])
                        prompt_pro = f"Escáner MOMENTUM {accion_iniciar}: {simbolo_operar}, Precio: {precio_actual}. Genera señal LONG/SHORT con TP/SL exactos."
                    else: st.warning(f"No se encontraron activos para {accion_iniciar}.")

                else:
                    candidatos = df_mercado.copy()
                    for index, row in candidatos.iterrows():
                        simbolo = row['symbol']
                        ind = obtener_indicadores_tecnicos(simbolo, temporalidad)
                        
                        if not ind['valido']: continue
                        if accion_iniciar == "LONG" and (ind['ema9'] > ind['ema21'] and 40 < ind['rsi'] < 70):
                            activo_encontrado, datos_tecnicos = row, ind
                            break
                        elif accion_iniciar == "SHORT" and (ind['ema9'] < ind['ema21'] and 30 < ind['rsi'] < 60):
                            activo_encontrado, datos_tecnicos = row, ind
                            break
                                
                    if activo_encontrado is not None:
                        simbolo_operar = activo_encontrado['symbol']
                        precio_actual = datos_tecnicos['precio']
                        prompt_pro = f"Escáner PRO {accion_iniciar}: {simbolo_operar}, Precio: {precio_actual}. EMA9={datos_tecnicos['ema9']}, EMA21={datos_tecnicos['ema21']}. Genera señal completa de trading con TP/SL."
                    else: st.warning(f"No se detectó cruce limpio para {accion_iniciar}.")

                if activo_encontrado is not None and prompt_pro != "":
                    st.success(f"🎯 Oportunidad aislada: **{simbolo_operar}**. Solicitando IA...")
                    resultado_ia, error_api, modelo_usado = consultar_gemini(prompt_pro)

                    if error_api: st.error(error_api)
                    else:
                        nums = re.findall(r"[\d.]+", resultado_ia)
                        try:
                            entrada_val = float(precio_actual)
                            tp1_val = float(nums[-3]) if len(nums) >= 3 else (precio_actual * 1.01 if accion_iniciar == 'LONG' else precio_actual * 0.99)
                            tp2_val = float(nums[-2]) if len(nums) >= 2 else (precio_actual * 1.02 if accion_iniciar == 'LONG' else precio_actual * 0.98)
                            sl_val = float(nums[-1]) if len(nums) >= 1 else (precio_actual * 0.99 if accion_iniciar == 'LONG' else precio_actual * 1.01)
                        except:
                            entrada_val, tp1_val, tp2_val, sl_val = precio_actual, precio_actual * 1.01, precio_actual * 1.02, precio_actual * 0.99

                        st.session_state.posicion_activa = {
                            "activo": simbolo_operar, "tipo": accion_iniciar,
                            "entrada": entrada_val, "tp1": tp1_val, "tp2": tp2_val, "sl": sl_val,
                            "tp1_alcanzado": False, "tp2_alcanzado": False
                        }
                        st.markdown(resultado_ia)
                        enviado, err = enviar_telegram(resultado_ia)
                        if enviado: st.toast("¡Alerta enviada a Telegram!", icon="✅")
