import streamlit as st
from pymongo import MongoClient
import pandas as pd

# ─── Configuración de página ───
st.set_page_config(page_title="Airbnb Analytics", page_icon="🏠", layout="wide")

st.title("🏠 Airbnb Analytics — Sample Data")
st.caption("Explora listados de alojamiento y sus metadatos vía MongoDB Atlas")

# ─── Conexión a MongoDB Atlas vía secrets ───
# Configurado en .streamlit/secrets.toml
try:
    mongo_uri = st.secrets["mongo"]["uri"]
except KeyError:
    st.error(
        "❌ No se encontró el secreto `mongo.uri`. "
        )
    st.stop()

with st.sidebar:
    st.header("🔌 MongoDB Atlas")
    st.markdown(
        "**Conexión:** vía `st.secrets`\n\n"
        "**Requisitos:**\n"
        "- Dataset `sample_airbnb` cargado\n"
        "- Colección `listingsAndReviews`\n"
        "- Índice `2dsphere` en `address.location`"
    )

# ─── Conectar ───
@st.cache_resource
def get_client(uri):
    return MongoClient(uri)

try:
    client = get_client(mongo_uri)
    db = client["sample_airbnb"]
    col_listings = db["listingsAndReviews"]
    # Test de conexión
    client.admin.command("ping")
    st.sidebar.success("✅ Conectado a MongoDB Atlas")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# ─── Asegurar índice geoespacial ───
try:
    # Útil para escalar a consultas $near o $geoWithin en el futuro
    col_listings.create_index([("address.location", "2dsphere")])
except Exception:
    pass

# ─── Búsqueda y Filtros ───
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    nombre_busqueda = st.text_input(
        "🔍 Buscar por nombre del listado",
        placeholder="Ej: Apartment, Ocean view, Loft"
    )

with col2:
    # Mercados comunes en el sample dataset
    mercado = st.selectbox(
        "📍 Área / Mercado", 
        ["Cualquiera", "New York", "Sydney", "Porto", "Rio de Janeiro", "Istanbul", "Hong Kong"]
    )

with col3:
    limite = st.selectbox("Resultados máx.", [10, 20, 50, 100], index=1)

# ─── Construcción del Query ───
query = {}

if nombre_busqueda:
    query["name"] = {"$regex": nombre_busqueda, "$options": "i"}

if mercado != "Cualquiera":
    query["address.market"] = mercado

# Ejecutar consulta
listados = list(col_listings.find(query).limit(limite))

if not listados:
    st.warning("No se encontraron alojamientos con los criterios actuales.")
    st.stop()

st.success(f"Se encontraron **{len(listados)}** alojamiento(s)")

# ─── Procesamiento de resultados ───
resultados = []
for r in listados:
    # Extraer coordenadas de GeoJSON (formato: [longitud, latitud])
    coord = r.get("address", {}).get("location", {}).get("coordinates", [])
    
    # Extraer precio y convertir de Decimal128 a float
    raw_price = r.get("price", 0)
    precio = float(str(raw_price)) if raw_price else 0.0

    resultados.append({
        "Propiedad": r.get("name", "—"),
        "Tipo": r.get("property_type", "—"),
        "Habitaciones": r.get("bedrooms", 0),
        "Precio ($)": precio,
        "Mercado": r.get("address", {}).get("market", "—"),
        "Sub-área": r.get("address", {}).get("suburb", "—"),
        "Longitud": coord[0] if len(coord) >= 2 else None,
        "Latitud": coord[1] if len(coord) >= 2 else None,
    })

df = pd.DataFrame(resultados)

# ─── Mostrar tabla ───
st.markdown("### 📋 Resultados Generales")
st.dataframe(
    df.drop(columns=["Longitud", "Latitud"]), 
    use_container_width=True, 
    hide_index=True
)

# ─── Mapa ───
# Filtrar registros que no tengan coordenadas válidas
df_map = df.dropna(subset=["Latitud", "Longitud"]).copy()
df_map = df_map.rename(columns={"Latitud": "latitude", "Longitud": "longitude"})

if not df_map.empty:
    st.markdown("### 🗺️ Distribución Geográfica")
    st.map(df_map[["latitude", "longitude"]])

# ─── Detalle expandible por propiedad ───
st.markdown("### 📝 Metadatos Detallados")
for i, r in enumerate(listados):
    nombre = r.get("name", "—")
    tipo_habitacion = r.get("room_type", "")
    precio_fmt = float(str(r.get("price", 0)))
    
    with st.expander(f"**{nombre}** — {tipo_habitacion} (${precio_fmt}/noche)"):
        c1, c2, c3 = st.columns([1, 1, 1])
        
        with c1:
            st.markdown("**Ubicación y Host**")
            st.markdown(f"**País:** {r.get('address', {}).get('country', '—')}")
            st.markdown(f"**Calle:** {r.get('address', {}).get('street', '—')}")
            host_name = r.get("host", {}).get("host_name", "—")
            is_superhost = "⭐" if r.get("host", {}).get("host_is_superhost") else ""
            st.markdown(f"**Anfitrión:** {host_name} {is_superhost}")

        with c2:
            st.markdown("**Características**")
            st.markdown(f"**Camas:** {r.get('beds', '—')} | **Baños:** {float(str(r.get('bathrooms', 0)))}")
            st.markdown(f"**Acomoda a:** {r.get('accommodates', '—')} personas")
            
            amenities = r.get("amenities", [])
            st.markdown("**Comodidades (Top 5):**")
            st.markdown(", ".join(amenities[:5]) + ("..." if len(amenities) > 5 else ""))

        with c3:
            reviews = r.get("reviews", [])
            st.markdown(f"**Reseñas ({len(reviews)})**")
            
            if reviews:
                latest_review = sorted(reviews, key=lambda x: x.get("date", ""), reverse=True)[0]
                st.info(f"*(Por {latest_review.get('reviewer_name', 'Anónimo')})*\n\n" + 
                        f"{latest_review.get('comments', '')[:100]}...")
            else:
                st.markdown("*No hay reseñas aún.*")
