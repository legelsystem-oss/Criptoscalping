import streamlit as st
import pandas as pd
import requests
from google import genai

# Configuración de la página
st.set_page_config(page_title="CryptoScalp AI - Terminal de Futuros Alpha", layout="wide")
st.title("⚡ CryptoScalp AI: Terminal de Futuros, Alpha & Gráficos en Vivo")

# Configuración de la API Key de Gemini
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# 1. Función para obtener TODOS los pares de Binance Futures en tiempo real
@st.cache_data(ttl=15)
def obtener_mercado_futures_binance():
    # Usamos proxy y múltiples rutas de respaldo para asegurar los precios en vivo
    urls = [
        "https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr",
        "https://fapi.binance.com/fapi/v1/ticker/24hr"
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=6)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data)
                df = df[df['symbol'].str.endswith('USDT')].copy()
                df['lastPrice'] = df['lastPrice'].astype(float)
                df['priceChangePercent'] = df['priceChangePercent'].astype(float)
                df['volume'] = df['quoteVolume'].astype(float)
                df['highPrice'] = df['highPrice'].astype(float)
                df['lowPrice'] = df['lowPrice'].astype(float)
                
                # Filtrar tokens inactivos o delisted (volumen cero o nulo)
                df = df[df['volume'] > 1000]
                return df.sort_values(by='volume', ascending=False)
        except Exception:
            continue
            
    # Respaldo total si Binance no responde en la nube
    try:
        url_alt = "https://api.coingecko.com/api/v3/coins/markets"
        params = {'vs_currency': 'usd', 'order': 'volume_desc', 'per_page': 100, 'page': 1}
        res = requests.get(url_alt, params=params, timeout=8)
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
            return df_cleaned[df_cleaned['volume'] > 1000].sort_values(by='volume', ascending=False)
    except Exception:
        pass
        
    return pd.DataFrame()

with st.spinner("Sincronizando precios en vivo de Binance Futures..."):
    df_mercado = obtener_mercado_futures_binance()

if df_mercado.empty:
    st.error("No se pudo conectar con el mercado. Por favor, recarga la página.")
else:
    # 2. Panel Lateral de Configuración y Selección de Pares
    st.sidebar.header("⚙️ Configuración del Terminal")
    
    # Filtro de categoría: Todos vs Alpha
    tipo_mercado = st.sidebar.radio(
        "Filtrar Categoría:",
        ["Todos los Pares de Futuros", "🔥 Pares Alpha (Alto Impulso)"]
    )
    
    if tipo_mercado == "🔥 Pares Alpha (Alto Impulso)":
        # Filtramos activos con volumen moderado/alto característicos de pumps/alpha
        df_mercado = df_mercado[(df_mercado['volume'] > 100000) & (df_mercado['volume'] < 80000000)]
        if df_mercado.empty:
            df_mercado = obtener_mercado_futures_binance().tail(40)

    # Listado completo para el buscador interactivo
    lista_pares = df_mercado['symbol'].tolist()

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Buscador de Activos")
    
    # Selector interactivo avanzado (permite buscar escribiendo o desplegar la lista completa)
    par_seleccionado = st.sidebar.selectbox(
        "Elige o escribe el par USDT:",
        options=lista_pares,
        index=0
    )

    temporalidad = st.sidebar.selectbox(
        "Temporalidad del Gráfico:",
        ["1", "5", "15", "60", "240"],
        format_func=lambda x: {"1": "1 Minuto", "5": "5 Minutos", "15": "15 Minutos", "60": "1 Hora", "240": "4 Horas"}[x]
    )
    
    estrategia = st.sidebar.selectbox(
        "Estrategia de IA:",
        ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"]
    )

    # Obtener datos específicos del par seleccionado
    datos_par = df_mercado[df_mercado['symbol'] == par_seleccionado].iloc[0]

    # 3. Métricas de Precios en Vivo
    st.subheader(f"📊 Mercado en Vivo: {par_seleccionado}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Actual", f"${datos_par['lastPrice']:,.4f}")
    col2.metric("Cambio 24h", f"{datos_par['priceChangePercent']}%", delta=float(datos_par['priceChangePercent']))
    col3.metric("Volumen 24h", f"${datos_par['volume']:,.0f}")
    col4.metric("Rango 24h", f"${datos_par['lowPrice']:,.4f} - ${datos_par['highPrice']:,.4f}")

    # 4. Gráfica Interactiva Estilo TradingView Actualizable
    st.markdown(f"### 📈 Gráfica Técnica: {par_seleccionado}")
    
    simbolo_tv = f"BINANCE:{par_seleccionado}"
    
    html_tradingview = f"""
    <div class="tradingview-widget-container" style="height:520px;width:100%">
      <div id="tv_chart_container" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{simbolo_tv}",
        "interval": "{temporalidad}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "es",
        "toolbar_bg": "#1e222d",
        "enable_publishing": false,
        "allow_symbol_change": false,
        "container_id": "tv_chart_container"
      }});
      </script>
    </div>
    """
    st.components.v1.html(html_tradingview, height=540)

    # 5. Motor de Análisis y Señales Long/Short con IA
    st.markdown("---")
    if st.button(f"🚀 Ejecutar Análisis IA (Long / Short) para {par_seleccionado}"):
        with st.spinner(f"Analizando {par_seleccionado} con la estrategia {estrategia}..."):
            
            prompt = f"""
            Actúa como un trader institucional experto en futuros de criptomonedas y análisis técnico.
            Analiza el activo en tiempo real:
            - Activo: {par_seleccionado}
            - Precio Actual: {datos_par['lastPrice']}
            - Cambio 24h: {datos_par['priceChangePercent']}%
            - Volumen 24h: {datos_par['volume']} USD
            - Temporalidad seleccionada: {temporalidad} minutos
            - Estrategia técnica: {estrategia}
            
            Emite un veredicto operativo formal estructurado que contenga obligatoriamente:
            1. **SEÑAL DE OPERACIÓN:** (Indicar claramente en grande si es una señal **LONG 🟢** o **SHORT 🔴** o **NEUTRAL ⚪**).
            2. **Análisis Técnico:** Fundamenta la dirección según el precio actual, el volumen y la estrategia elegida.
            3. **Parámetros de Entrada y Salida:** 
               - Precio de Entrada Sugerido
               - Take Profit (TP) 1 y TP 2
               - Stop Loss (SL) estricto
            4. **Nivel de Riesgo / Apalancamiento recomendado**.
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
