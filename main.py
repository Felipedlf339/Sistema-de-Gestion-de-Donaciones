from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gestion_donaciones.rutas import disponibilidad, elegibilidad, registro_donaciones
from gestion_donaciones.rutas import registro_donantes as rutas_donantes
from gestion_donaciones.database import inicializar_bd
from gestion_donaciones.rutas import disponibilidad, elegibilidad, registro_donaciones, despachos

inicializar_bd()
app = FastAPI(title="Sistema de Gestión de Donaciones")
templates = Jinja2Templates(directory="templates")

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
app.include_router(despachos.router)

@app.get("/")
def inicio(request: Request):
    return templates.TemplateResponse(request=request, name="panel_principal.html")