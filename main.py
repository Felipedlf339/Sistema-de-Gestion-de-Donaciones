from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from gestion_donaciones.rutas.elegibilidad import router as elegibilidad_router

app = FastAPI()
# Configuración de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(elegibilidad_router)