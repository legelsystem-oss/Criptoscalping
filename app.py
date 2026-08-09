import streamlit as st
import pandas as pd
import requests
from google import genai

# Configuración de la página
st.set_page_config(page_title="CryptoScalp AI - Terminal de Futuros Alpha", layout="wide")
st.title("⚡ CryptoScalp AI: Terminal de Futuros, Alpha & Gráficos")

# Configuración de la API Key de Gemini
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# 1. Obtener y filtrar datos del mercado eliminando pares inactivos
@st.cache_data(ttl=30)
def obtener_mercado_filtrado():
    # Intento con la API de Binance Futures vía proxy para evitar bloqueos
    url_proxy = "https://corsproxy.io/?https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        response = requests.get(url_proxy, timeout=8)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            # Filtrar exclusivamente pares USDT y descartar los que tengan volumen 0 o estén inactivos (delisted)
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float)
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            
            # FILTRO CRÍTICO: Descartar tokens inactivos, con volumen cero o suspendidos
            df = df[df['volume'] > 1000] 
            return df.sort_values(by='volume', ascending=False)
    except Exception:
        pass

    # Respaldo con CoinGecko si falla Binance
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
            return df_cleaned[df_cleaned['volume'] > 1000].sort_values(by='volume', ascending=False)
    except Exception:
        pass
            
    return pd.DataFrame()

with st.spinner("Sincronizando mercado de futuros y filtrando activos activos..."):
    df_mercado = obtener_mercado_filtrado()

if df_mercado.empty:
    st.error("No se pudo conectar con el mercado. Recarga la página en unos segundos.")
else:
    # 2. Panel Lateral de Configuración
    st.sidebar.header("⚙️ Configuración de Scalping")
    
    # Filtro especial de categoría (Todos vs Pares Alpha / Alta Volatilidad)
    tipo_mercado = st.sidebar.radio(
        "Filtrar Mercado:",
        ["Todos los Pares Líquidos", "🔥 Solo Pares Alpha (Alto Impulso)"]
    )
    
    # Lógica para aislar pares Alpha (ejemplos de tokens de alta volatilidad/baja cap o seleccionados del top)
    if tipo_mercado == "🔥 Solo Pares Alpha (Alto Impulso)":
        # Consideramos Alpha a los pares del ranking medio-alto con alta variación o tokens específicos de tendencia
        df_mercado = df_mercado[(df_mercado['volume'] > 500000) & (df_mercado['volume'] < 50000000)]
        if df_mercado.empty:
            df_mercado = obtener_mercado_filtrado().tail(30) # Respaldo si el filtro es muy estricto
            
    temporalidad = st.sidebar.selectbox(
        "Temporalidad:",
        ["5 Minutos (Scalping)", "15 Minutos (Scalping Tendencial)", "1 Hora (Intradía)", "4 Horas (Swing)"]
    )
    
    estrategia = st.sidebar.selectbox(
        "Estrategia:",
        ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"]
    )

    lista_pares = df_mercado['symbol'].tolist()
    
    par_seleccionado = st.sidebar.selectbox(
        "Selecciona el Activo:",
        options=lista_pares,
        index=0
    )

    datos_par = df_mercado[df_mercado['symbol'] == par_seleccionado].iloc[0]

    # 3. Widget de Gráfica Interactiva con Manejo de Errores de Símbolo
    st.subheader(f"📈 Gráfica en Vivo: {par_seleccionado} (Binance Futures)")
    
    # Asegurar formato correcto para TradingView
    simbolo_tv = f"BINANCE:{par_seleccionado}"
    
    html_tradingview = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:500px;width:100%">
      <div id="tradingview_widget" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      try {
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
          }});
      } catch(e) {{
          console.log("Error cargando widget de gráfico");
      }}
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    st.components.v1.html(html_tradingview, height=520)

    # 4. Métricas del par
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Actual", f"${datos_par['lastPrice']:,.4f}")
    col2.metric("Cambio 24h", f"{datos_par['priceChangePercent']}%", delta=float(datos_par['priceChangePercent']))
    col3.metric("Volumen 24h", f"${datos_par['volume']:,.0f}")
    col4.metric("Rango 24h", f"${datos_par['lowPrice']:,.4f} - ${datos_par['highPrice']:,.4f}")

    # 5. Análisis de Señales con la IA de Gemini
    st.markdown("---")
    if st.button(f"🚀 Generar Señal IA (Long / Short) para {par_seleccionado}"):
        with st.spinner(f"Analizando {par_seleccionado} con estrategia {estrategia}..."):
            
            prompt = f"""
            Actúa como un trader institucional experto en futuros de criptomonedas.
            Analiza el siguiente activo del mercado de futuros:
            - Activo: {par_seleccionado}
            - Precio Actual: {datos_par['lastPrice']}
            - Cambio 24h: {datos_par['priceChangePercent']}%
            - Volumen 24h: {datos_par['volume']} USD
            - Temporalidad: {temporalidad}
            - Estrategia técnica: {estrategia}
            
            Emite un veredicto operativo formal que contenga obligatoriamente:
            1. **SEÑAL DE OPERACIÓN:** (Indicar claramente en grande si es una señal **LONG 🟢** o **SHORT 🔴** o **NEUTRAL ⚪**).
            2. **Análisis Técnico:** Fundamenta la dirección según el volumen y la estrategia elegida.
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
