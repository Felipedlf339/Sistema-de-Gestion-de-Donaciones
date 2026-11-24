import os

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from gestion_donaciones.rutas import disponibilidad, elegibilidad, permisos, registro_donaciones, sesion, entregas
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

# todas las pantallas piden sesión y un cargo autorizado (ver rutas/permisos.py)
# el inicio y cierre de sesión quedan libres
con_permiso = [Depends(permisos.verificar_acceso)]
app.include_router(disponibilidad.router, dependencies=con_permiso)
app.include_router(elegibilidad.router, dependencies=con_permiso)
app.include_router(registro_donaciones.router, dependencies=con_permiso)
app.include_router(rutas_donantes.router, dependencies=con_permiso)
app.include_router(sesion.router)
app.include_router(entregas.router)


@app.exception_handler(permisos.SinSesion)
def responder_sin_sesion(request: Request, error):
    # al abrir una pantalla se envía al inicio de sesión; a un fetch() se le responde 401
    if permisos.quiere_html(request):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detail": permisos.MENSAJE_SIN_SESION}, status_code=401)


@app.exception_handler(permisos.AccesoDenegado)
def responder_acceso_denegado(request: Request, error):
    if permisos.quiere_html(request):
        return templates.TemplateResponse(
            request=request,
            name="acceso_denegado.html",
            context={
                "usuario": sesion.usuario_en_sesion(request),
                "mensaje": permisos.MENSAJE_ACCESO_DENEGADO,
            },
            status_code=403,
        )
    return JSONResponse({"detail": permisos.MENSAJE_ACCESO_DENEGADO}, status_code=403)


@app.get("/")
def inicio(request: Request):
    usuario = sesion.usuario_en_sesion(request)
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="panel_principal.html",
        context={"usuario": usuario, "opciones": permisos.opciones_del_menu(usuario)},
    )
