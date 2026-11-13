from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gestion_donaciones.rutas import disponibilidad, elegibilidad, registro_donaciones
from gestion_donaciones.rutas import registro_donantes as rutas_donantes
from gestion_donaciones.database import inicializar_bd

inicializar_bd()
app = FastAPI(title="Sistema de Gestión de Donaciones")
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(disponibilidad.router)
app.include_router(elegibilidad.router)
app.include_router(registro_donaciones.router)
app.include_router(rutas_donantes.router)

@app.get("/")
def inicio(request: Request):
    return templates.TemplateResponse(request=request, name="panel_principal.html")