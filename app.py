import streamlit as st
import pandas as pd
import requests
from google import genai

# Configuración de la App
st.set_page_config(page_title="CryptoScalp AI", layout="wide")
st.title("🤖 CryptoScalp AI Analysis")

# Configura tu API Key aquí
API_KEY = "AQ.Ab8RN6IUU1HCyoTBJvilfLLEVH95L9oDAsukinvSs2yE28IVHQ"
client = genai.Client(api_key=API_KEY)

# Función de datos (la misma que ya tenías)
def get_data():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=10"
    response = requests.get(url)
    return pd.DataFrame(response.json())

# Interfaz
if st.button('Ejecutar Análisis de Mercado'):
    with st.spinner('Analizando datos...'):
        data = get_data()
        prompt = f"Actúa como trader experto. Analiza estos datos: {data[['symbol', 'current_price', 'total_volume']].to_string()}"
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        
        st.subheader("Reporte de IA")
        st.write(response.text)
        st.dataframe(data[['symbol', 'current_price', 'total_volume']])
