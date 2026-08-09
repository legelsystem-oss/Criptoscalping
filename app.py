import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
from google import genai

# Configuración de la página
st.set_page_config(page_title="CryptoScalp AI - Mercado Cripto", layout="wide")
st.title("⚡ CryptoScalp AI: Analizador Cuantitativo en Vivo")

# Configuración de la API Key de Gemini
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# 1. Función robusta utilizando la API global de CoinGecko (Sin bloqueos de región)
@st.cache_data(ttl=60)
def obtener_mercado_global():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        'vs_currency': 'usd',
        'order': 'volume_desc',
        'per_page': 30,
        'page': 1,
        'sparkline': 'false'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            # Adaptar nombres de columnas para mantener la compatibilidad del dashboard
            df['symbol'] = df['symbol'].str.upper() + 'USDT'
            df_cleaned = pd.DataFrame({
                'symbol': df['symbol'],
                'lastPrice': df['current_price'],
                'priceChangePercent': df['price_change_percentage_24h'],
                'volume': df['total_volume'],
                'highPrice': df['high_24h'] if 'high_24h' in df else df['current_price'] * 1.02,
                'lowPrice': df['low_24h' ] if 'low_24h' in df else df['current_price'] * 0.98
            })
            return df_cleaned
    except Exception as e:
        st.error(f"Error de conexión con el proveedor de datos: {e}")
    return pd.DataFrame()

# Cargar datos del mercado
with st.spinner("Sincronizando datos del mercado en tiempo real..."):
    df_mercado = obtener_mercado_global()

if df_mercado.empty:
    st.warning("No se pudieron cargar los datos en este momento. Intenta recargar la página.")
else:
    # 2. Panel Lateral: Configuración y Estrategia
    st.sidebar.header("⚙️ Configuración de Scalping")
    
    temporalidad = st.sidebar.selectbox(
        "Temporalidad de Análisis:",
        ["5 Minutos (Scalping Rápido)", "15 Minutos (Scalping Tendencial)", "1 Hora (Intradía)", "4 Horas (Swing)"]
    )
    
    estrategia = st.sidebar.selectbox(
        "Estrategia de Trading:",
        ["Cruce de Medias (EMA 9/21) + RSI", "Ruptura de Rango y Volumen", "Reversión en Bandas de Bollinger"]
    )

    opciones_pares = df_mercado['symbol'].tolist()
    pares_seleccionados = st.sidebar.multiselect(
        "Selecciona los pares a analizar por la IA:",
        options=opciones_pares,
        default=opciones_pares[:3]
    )

    df_filtrado = df_mercado[df_mercado['symbol'].isin(pares_seleccionados)]

    # 3. Mostrar Resumen del Mercado
    st.subheader("📊 Panel de Activos en Vivo")
    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[['symbol', 'lastPrice', 'priceChangePercent', 'volume']]
            .rename(columns={
                'symbol': 'Símbolo',
                'lastPrice': 'Precio Actual ($)',
                'priceChangePercent': 'Cambio 24h (%)',
                'volume': 'Volumen USD'
            }),
            use_container_width=True
        )

        # 4. Gráfica Visual de Rendimiento
        st.subheader("📈 Gráfica de Variación (24h)")
        fig, ax = plt.subplots(figsize=(10, 4))
        colores = ['green' if x >= 0 else 'red' for x in df_filtrado['priceChangePercent']]
        ax.bar(df_filtrado['symbol'], df_filtrado['priceChangePercent'], color=colores)
        ax.axhline(0, color='grey', linewidth=0.8, linestyle='--')
        plt.xticks(rotation=45, ha='right')
        ax.set_ylabel("Variación %")
        ax.set_title("Comportamiento de los Activos Seleccionados")
        st.pyplot(fig)

        # 5. Análisis con IA Gemini
        if st.button("🚀 Ejecutar Análisis Cuantitativo con IA"):
            with st.spinner("La IA está procesando las métricas y aplicando la estrategia..."):
                datos_para_ia = df_filtrado.to_string()
                
                prompt = f"""
                Actúa como un trader institucional experto en criptomonedas y especialista en gestión de riesgo.
                Analiza los siguientes datos en vivo del mercado:
                {datos_para_ia}
                
                Parámetros de ejecución del usuario:
                - Temporalidad seleccionada: {temporalidad}
                - Estrategia elegida: {estrategia}
                
                Por favor, genera un informe profesional estructurado que incluya:
                1. **Evaluación de Tendencia:** Identifica cuál de los activos seleccionados muestra la mejor confluencia de volumen y volatilidad para aplicar la estrategia de {estrategia}.
                2. **Señales Operativas:** Sugiere puntos claros de entrada (Long/Short), niveles estimados de Take Profit (TP) y Stop Loss (SL).
                3. **Gestión de Riesgo:** Advertencia sobre el apalancamiento adecuado para esta temporalidad.
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
        st.info("Por favor, selecciona al menos un par en el menú lateral.")
