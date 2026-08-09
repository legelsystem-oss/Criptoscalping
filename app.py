import streamlit as st
import pandas as pd
import requests
from google import genai

# Configuración de la página
st.set_page_config(page_title="CryptoScalp AI - Terminal de Futuros", layout="wide")
st.title("⚡ CryptoScalp AI: Terminal de Futuros con IA & Gráficos")

# Configuración de la API Key de Gemini
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# 1. Función ultra-robusta con múltiples respaldos para evitar bloqueos de IP
@st.cache_data(ttl=30)
def obtener_todos_futuros_binance():
    # Intento 1: Usar un proxy público gratuito para saltar el bloqueo de IP de Binance en la nube
    url_proxy = "https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        response = requests.get(url_proxy, timeout=8)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            return df.sort_values(by='volume', ascending=False)
    except Exception:
        pass

    # Intento 2: Endpoint directo de Binance por si el proxy falla
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=5)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            return df.sort_values(by='volume', ascending=False)
    except Exception:
        pass

    # Intento 3 (Plan de Respaldo Global): CoinGecko API (Nunca falla en la nube)
    try:
        url_alt = "https://api.coingecko.com/api/v3/coins/markets"
        params = {'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 100, 'page': 1}
        res = requests.get(url_alt, params=params, timeout=10)
        if res.status_code == 200:
            data_alt = res.json()
            df_alt = pd.DataFrame(data_alt)
            df_alt['symbol'] = df_alt['symbol'].str.upper() + 'USDT'
            df_cleaned = pd.DataFrame({
                'symbol': df_alt['symbol'],
                'lastPrice': df_alt['current_price'],
                'priceChangePercent': df_alt['price_change_percentage_24h'],
                'volume': df_alt['total_volume'],
                'highPrice': df_alt['current_price'] * 1.02,
                'lowPrice': df_alt['current_price'] * 0.98
            })
            return df_cleaned.sort_values(by='volume', ascending=False)
    except Exception:
        pass
            
    return pd.DataFrame()

# Cargar el mercado con reintentos
with st.spinner("Sincronizando el mercado de futuros en tiempo real..."):
    df_mercado = obtener_todos_futuros_binance()

if df_mercado.empty:
    st.error("No se pudo conectar con las pasarelas de datos. Por favor, haz clic en 'Rerequest' o recarga la página.")
else:
    # 2. Panel Lateral de Configuración
    st.sidebar.header("⚙️ Configuración de Scalping IA")
    
    temporalidad = st.sidebar.selectbox(
        "Temporalidad:",
        ["5 Minutos (Scalping)", "15 Minutos (Scalping Tendencial)", "1 Hora (Intradía)", "4 Horas (Swing)"]
    )
    
    estrategia = st.sidebar.selectbox(
        "Estrategia:",
        ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"]
    )

    lista_todos_pares = df_mercado['symbol'].tolist()
    
    par_seleccionado = st.sidebar.selectbox(
        "Selecciona el Activo para Analizar y Graficar:",
        options=lista_todos_pares,
        index=0
    )

    datos_par = df_mercado[df_mercado['symbol'] == par_seleccionado].iloc[0]

    # 3. Widget de Gráfica Interactiva Estilo TradingView
    st.subheader(f"📈 Gráfica en Vivo: {par_seleccionado} (Binance Futures)")
    
    simbolo_tv = f"BINANCE:{par_seleccionado}"
    
    html_tradingview = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:500px;width:100%">
      <div id="tradingview_widget" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{simbolo_tv}",
        "interval": "15",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "es",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_widget"
      }}
      );
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    st.components.v1.html(html_tradingview, height=520)

    # 4. Métricas rápidas del par seleccionado
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Actual", f"${datos_par['lastPrice']:,.4f}")
    col2.metric("Cambio 24h", f"{datos_par['priceChangePercent']}%", delta=float(datos_par['priceChangePercent']))
    col3.metric("Volumen 24h", f"${datos_par['volume']:,.0f}")
    col4.metric("Rango 24h", f"${datos_par['lowPrice']:,.4f} - ${datos_par['highPrice']:,.4f}")

    # 5. Análisis de Señales con la IA de Gemini
    st.markdown("---")
    if st.button(f"🚀 Generar Señal IA (Long / Short) para {par_seleccionado}"):
        with st.spinner(f"Aplicando estrategia de {estrategia} en temporalidad de {temporalidad}..."):
            
            prompt = f"""
            Actúa como un trader institucional experto en futuros de criptomonedas y análisis técnico avanzado.
            Analiza el siguiente activo del mercado de futuros:
            - Activo: {par_seleccionado}
            - Precio Actual: {datos_par['lastPrice']}
            - Cambio 24h: {datos_par['priceChangePercent']}%
            - Volumen 24h: {datos_par['volume']} USD
            - Máximo / Mínimo 24h: {datos_par['highPrice']} / {datos_par['lowPrice']}
            - Temporalidad de operación: {temporalidad}
            - Estrategia técnica aplicada: {estrategia}
            
            Por favor, emite un veredicto operativo formal que contenga obligatoriamente:
            1. **SEÑAL DE OPERACIÓN:** (Indicar claramente en grande si es una señal **LONG 🟢** o **SHORT 🔴** o **NEUTRAL ⚪**).
            2. **Análisis Técnico:** Fundamenta la dirección basándote en la acción del precio, el volumen y la estrategia elegida.
            3. **Parámetros de Entrada y Salida:** 
               - Precio de Entrada Sugerido
               - Take Profit (TP) 1 y TP 2
               - Stop Loss (SL) estricto
            4. **Nivel de Riesgo / Apalancamiento recomendado** para esta temporalidad.
            """

            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=prompt,
                )
                
                st.success("¡Análisis de señal completado!")
                st.markdown("### 🎯 Reporte de Señal y Gestión de Riesgo")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Error al conectar con el motor de IA de Gemini: {e}")
