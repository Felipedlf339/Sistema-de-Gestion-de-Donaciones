from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from gestion_donaciones.rutas import disponibilidad, elegibilidad, registro_donaciones, registro_donantes
import json
from fastapi.staticfiles import StaticFiles
from gestion_donaciones.rutas.elegibilidad import router as elegibilidad_router
from gestion_donaciones.rutas.registro_donaciones import router as donaciones_router

from gestion_donaciones.database import inicializar_bd

inicializar_bd()

app = FastAPI(title="Sistema de Gestión de Donaciones")
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
        await cliente.send_json(datos_unidad)

# Configuración de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(disponibilidad.router)
app.include_router(elegibilidad.router)
app.include_router(registro_donaciones.router)
app.include_router(registro_donantes.router)
