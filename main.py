from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from gestion_donaciones.rutas.elegibilidad import router as elegibilidad_router
from gestion_donaciones.rutas.registro_donaciones import router as donaciones_router

from gestion_donaciones.database import inicializar_bd

inicializar_bd()

app = FastAPI()
# Configuración de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(elegibilidad_router)
app.include_router(donaciones_router)
