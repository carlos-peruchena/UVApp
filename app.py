import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from suntime import Sun, sun
import requests
from bs4 import BeautifulSoup
import geopandas as gpd
from shapely.geometry import Point
import pydeck as pdk

# Configuración de la aplicación
st.set_page_config(page_title="UVApp - SERIM", layout="wide")

# Datos
provincias = [
    "A Coruña", "Álava", "Albacete", "Alicante/Alacant", "Almería", "Asturias", "Ávila", "Badajoz", "Barcelona",
    "Burgos", "Cáceres", "Cádiz", "Cantabria", "Castellón/Castelló", "Ceuta", "Ciudad Real", "Córdoba", "Cuenca",
    "Girona", "Granada", "Guadalajara", "Guipúzcoa", "Huelva", "Huesca", "Illes Balears", "Jaén", "La Rioja",
    "Las Palmas", "León", "Lleida", "Lugo", "Madrid", "Málaga", "Melilla", "Murcia", "Navarra", "Ourense",
    "Palencia", "Pontevedra", "Salamanca", "Santa Cruz de Tenerife", "Segovia", "Sevilla", "Soria", "Tarragona",
    "Teruel", "Toledo", "Valencia/València", "Valladolid", "Vizcaya", "Zamora", "Zaragoza"
]

municipios = pd.read_table("municipios.txt", header=0)

# Funciones
def leer_lista_desde_txt(nombre_archivo):
    with open(nombre_archivo, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    lista = {}
    nombre_provincia = None

    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("$"):
            nombre_provincia = linea[1:]
            lista[nombre_provincia] = []
        elif linea:
            lista[nombre_provincia].append(linea)

    return lista

localidades = leer_lista_desde_txt("localidades.txt")

def obtener_fechas_disponibles():
    url_dia_0 = "https://www.aemet.es/es/eltiempo/prediccion/radiacionuv.csv?w=0&datos=det"
    response = requests.get(url_dia_0)
    soup = BeautifulSoup(response.text, "html.parser")
    fecha_dia_0 = datetime.strptime(soup.find("pre").text.split("\n")[1], "%d %B %Y a las %H:%M").date()
    fechas_disponibles = [fecha_dia_0 + timedelta(days=i) for i in range(5)]
    fechas_disponibles = [fecha for fecha in fechas_disponibles if fecha >= date.today()]
    return fechas_disponibles

fechas_disponibles = obtener_fechas_disponibles()

def obtener_datos_uv(fecha):
    dia = (fecha - fechas_disponibles[0]).days
    url = f"https://www.aemet.es/es/eltiempo/prediccion/radiacionuv?w={dia}&datos=det"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    tabla = soup.find("table")
    filas = tabla.find_all("tr")
    datos = []
    for fila in filas[1:]:
        celdas = fila.find_all("td")
        if celdas:
            poblacion = celdas[0].text.strip()
            uva = celdas[1].text.strip()
            datos.append({"Población": poblacion, "UVA": uva})
    df = pd.DataFrame(datos)
    df = df.merge(municipios, on="Población", how="left")
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitud, df.Latitud))
    return df

def interpolar_datos_uv(df):
    datos_conocidos = df[~df["UVA"].isna()]
    datos_desconocidos = df[df["UVA"].isna()]
    datos_conocidos = datos_conocidos.astype({"UVA": float})
    modelo_interpolacion = datos_conocidos.interpolate(method="nearest")
    valores_interpolados = modelo_interpolacion["UVA"].reindex(datos_desconocidos.index)
    df.loc[datos_desconocidos.index, "UVA"] = valores_interpolados
    return df

# Sidebar
st.sidebar.title("Configuración")
provincia_seleccionada = st.sidebar.selectbox("Provincia", provincias, index=provincias.index("Sevilla"))
localidades_provincia = localidades.get(provincia_seleccionada, [])
localidad_seleccionada = st.sidebar.selectbox("Localidad", localidades_provincia, index=localidades_provincia.index("Sevilla") if "Sevilla" in localidades_provincia else 0)
fecha_seleccionada = st.sidebar.date_input("Fecha", min_value=min(fechas_disponibles), max_value=max(fechas_disponibles), value=date.today())

# Obtener y procesar datos
df_uv = obtener_datos_uv(fecha_seleccionada)
df_uv = interpolar_datos_uv(df_uv)

# Mapa
st.subheader(f"Radiación UV en {provincia_seleccionada} el {fecha_seleccionada.strftime('%d/%m/%Y')}")
view_state = pdk.ViewState(latitude=df_uv.geometry.y.mean(), longitude=df_uv.geometry.x.mean(), zoom=7)
layer = pdk.Layer("ScatterplotLayer", data=df_uv, get_position="position", get_radius=100, get_fill_color="[200, 30, 0, 160]", pickable=True)
tooltip = {"html": "<b>{Población}</b><br/>UVA: {UVA}"}
r = pdk.Deck(map_style="mapbox://styles/mapbox/light-v9", initial_view_state=view_state, layers=[layer], tooltip=tooltip)
st.pydeck_chart(r)

# Información adicional
st.subheader("Información adicional")
st.write("""
Esta aplicación ha sido creada por la Sociedad Española de Recursos Energéticos Renovables e Inteligencia Meteorológica (SERIM). Utiliza predicciones de radiación ultravioleta proporcionadas por la Agencia Estatal de Meteorología española (Aemet), disponibles para 59 ciudades e interpoladas para 8.114 municipios en todo el territorio nacional. Los modelos utilizados en esta aplicación han sido publicados en revistas científicas. No obstante, estas recomendaciones no constituyen un consejo médico. Ante cualquier duda consulte con su médico.

Para usarla adecuadamente, debe:
- Seleccionar su provincia, localidad y la fecha a calcular.
- Introducir información en la pestaña "Fototipo" para personalizar el modelo.
- Seleccionar la hora de comienzo de exposición al sol.
- Seleccionar el grado de exposición.
- Seleccionar el factor de protección.

SERIM es una sociedad científica sin ánimo de lucro, cuyo objetivo es promover la investigación y el desarrollo de las energías renovables y la inteligencia meteorológica en España. Nuestro equipo está formado por investigadores de diferentes universidades y centros de investigación, con una amplia experiencia en los campos de las energías renovables, meteorología e inteligencia artificial.

Esperamos que esta aplicación sea de utilidad para conocer los niveles de radiación ultravioleta en su localidad y contribuya a tomar las medidas de protección adecuadas. Si tiene cualquier duda o sugerencia, no dude en ponerse en contacto con nosotros a través de nuestro [sitio web](https://serim.es).
""")
