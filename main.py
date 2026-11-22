import os

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from gestion_donaciones.rutas import disponibilidad, elegibilidad, registro_donaciones, sesion
from gestion_donaciones.rutas import registro_donantes as rutas_donantes
from gestion_donaciones.database import inicializar_bd

inicializar_bd()
app = FastAPI(title="Sistema de Gestión de Donaciones")
templates = Jinja2Templates(directory="templates")

# la sesión se guarda en una cookie firmada con esta clave
# en producción se define la variable de entorno CLAVE_SESION
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("CLAVE_SESION", "clave-de-desarrollo-cambiar"),
    max_age=8 * 60 * 60,  # 8 horas, un turno
)

clientes_conectados = []

@app.websocket("/ws/stock")
async def websocket_stock(websocket: WebSocket):
    await websocket.accept()
    clientes_conectados.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clientes_conectados.remove(websocket)

async def notificar_nuevo_stock(datos_unidad: dict):
    for cliente in clientes_conectados:
        try:
            await cliente.send_json(datos_unidad)
        except Exception:
            pass

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(disponibilidad.router)
app.include_router(elegibilidad.router)
app.include_router(registro_donaciones.router)
app.include_router(rutas_donantes.router)
app.include_router(sesion.router)

@app.get("/")
def inicio(request: Request):
    usuario = sesion.usuario_en_sesion(request)
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="panel_principal.html", context={"usuario": usuario}
    )