import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
from google import genai

# Configuración de la página
st.set_page_config(page_title="CryptoScalp AI - Futuros Binance", layout="wide")
st.title("⚡ CryptoScalp AI: Analizador de Futuros Binance")

# Configuración de la API Key de Gemini
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# 1. Función para obtener datos de la API pública de Binance Futures (Ticker 24h)
@st.cache_data(ttl=60)
def obtener_mercado_futuros():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            # Limpiar y filtrar datos relevantes para futuros (pares USDT)
            df = df[df['symbol'].str.endswith('USDT')].copy()
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['volume'] = df['quoteVolume'].astype(float) # Volumen en USDT
            df['highPrice'] = df['highPrice'].astype(float)
            df['lowPrice'] = df['lowPrice'].astype(float)
            
            # Ordenar por volumen descendente
            df = df.sort_values(by='volume', ascending=False)
            return df
    except Exception as e:
        st.error(f"Error al conectar con Binance Futures: {e}")
    return pd.DataFrame()

# Cargar datos del mercado en vivo
with st.spinner("Conectando con el mercado de futuros de Binance..."):
    df_mercado = obtener_mercado_futuros()

if df_mercado.empty:
    st.warning("No se pudieron cargar los datos en vivo. Revisa tu conexión.")
else:
    # 2. Panel Lateral: Selección de Pares y Configuración de Estrategia
    st.sidebar.header("⚙️ Configuración de Scalping")
    
    # Selector de temporalidad para la estrategia
    temporalidad = st.sidebar.selectbox(
        "Temporalidad de Análisis:",
        ["5 Minutos (Scalping Rápido)", "15 Minutos (Scalping Tendencial)", "1 Hora (Intradía)", "4 Horas (Swing)"]
    )
    
    # Estrategia a aplicar
    estrategia = st.sidebar.selectbox(
        "Estrategia de Trading:",
        ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"]
    )

    # Selector de pares (Muestra los 30 principales por defecto para elegir)
    opciones_pares = df_mercado['symbol'].head(30).tolist()
    pares_seleccionados = st.sidebar.multiselect(
        "Selecciona los pares a analizar por la IA:",
        options=opciones_pares,
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )

    # Filtrar el DataFrame con los pares elegidos por el usuario
    df_filtrado = df_mercado[df_mercado['symbol'].isin(pares_seleccionados)]

    # 3. Mostrar Resumen de Mercado en Vivo
    st.subheader("📊 Mercado de Futuros en Vivo")
    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[['symbol', 'lastPrice', 'priceChangePercent', 'volume', 'highPrice', 'lowPrice']]
            .rename(columns={
                'symbol': 'Símbolo',
                'lastPrice': 'Precio Actual ($)',
                'priceChangePercent': 'Cambio 24h (%)',
                'volume': 'Volumen USDT',
                'highPrice': 'Máximo 24h',
                'lowPrice': 'Mínimo 24h'
            }),
            use_container_width=True
        )

        # 4. Gráfica Visual de Variación de Precios de los pares seleccionados
        st.subheader("📈 Gráfica de Rendimiento (24h)")
        fig, ax = plt.subplots(figsize=(10, 4))
        colores = ['green' if x >= 0 else 'red' for x in df_filtrado['priceChangePercent']]
        ax.bar(df_filtrado['symbol'], df_filtrado['priceChangePercent'], color=colores)
        ax.axhline(0, color='grey', linewidth=0.8, linestyle='--')
        ax.set_xticklabels(df_filtrado['symbol'], rotation=45, ha='right')
        ax.set_ylabel("Variación %")
        ax.set_title(f"Variación Porcentual de los Activos Seleccionados")
        st.pyplot(fig)

        # 5. Motor de Análisis con Gemini IA
        if st.button("🚀 Ejecutar Análisis Cuantitativo con IA"):
            with st.spinner("La IA está procesando las métricas y aplicando la estrategia..."):
                # Preparar los datos en texto plano para que la IA los analice profundamente
                datos_para_ia = df_filtrado[['symbol', 'lastPrice', 'priceChangePercent', 'volume', 'highPrice', 'lowPrice']].to_string()
                
                prompt = f"""
                Actúa como un trader institucional experto en futuros de criptomonedas y especialista en gestión de riesgo.
                Analiza los siguientes datos en vivo del mercado de futuros de Binance:
                {datos_para_ia}
                
                Parámetros de ejecución del usuario:
                - Temporalidad seleccionada: {temporalidad}
                - Estrategia elegida: {estrategia}
                
                Por favor, genera un informe profesional estructurado que incluya:
                1. **Evaluación de Tendencia:** Identifica cuál de los activos seleccionados muestra la mejor confluencia de volumen y volatilidad para aplicar la estrategia de {estrategia}.
                2. **Señales Operativas:** Sugiere puntos claros de entrada (Long/Short), niveles estimados de Take Profit (TP) y Stop Loss (SL) basados en el rango de precios actuales (High/Low).
                3. **Gestión de Riesgo:** Una advertencia sobre el apalancamiento adecuado para esta temporalidad.
                """

                try:
                    response = client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=prompt,
                    )
                    
                    st.success("¡Análisis completado con éxito!")
                    st.markdown("### 🤖 Reporte de IA y Señales")
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"Error al generar la respuesta con Gemini: {e}")
    else:
        st.info("Por favor, selecciona al menos un par en el menú lateral para ver las gráficas y activar el análisis de la IA.")
