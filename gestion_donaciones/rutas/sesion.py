"""Rutas de inicio y cierre de sesión del personal (HU-07, tarea T27)"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gestion_donaciones.registro_personal import RegistroPersonal
from gestion_donaciones.validaciones import esta_vacio

router = APIRouter(tags=["Sesión"])
templates = Jinja2Templates(directory="templates")

registro = RegistroPersonal()

MENSAJE_INCORRECTO = "RUN o contraseña incorrectos"


class InicioSesionRequest(BaseModel):
    run: str | None = None
    contrasena: str | None = None


def personal_a_diccionario(personal):
    # lo que se guarda en la sesión (debe poder pasarse a JSON)
    centro = getattr(personal, "centro_medico", None)
    return {
        "id_personal": personal.id_personal,
        "run": personal.run,
        "nombre": personal.nombre,
        "cargo": personal.cargo.name,
        "nombre_cargo": personal.cargo.value,
        "centro_medico": centro.nombre if centro else None,
    }


def usuario_en_sesion(request):
    # devuelve los datos del usuario con sesión iniciada, o None
    return request.session.get("usuario")


@router.get("/login", response_class=HTMLResponse)
def ver_inicio_sesion(request: Request):
    if usuario_en_sesion(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/login")
def iniciar_sesion(datos: InicioSesionRequest, request: Request):
    if esta_vacio(datos.run) or esta_vacio(datos.contrasena):
        raise HTTPException(status_code=400, detail="Ingrese su RUN y su contraseña.")

    personal = registro.iniciar_sesion(datos.run, datos.contrasena)
    if personal is None:
        # mismo mensaje si no existe el RUN o si la contraseña está mal,
        # así no se puede averiguar qué RUN están registrados
        raise HTTPException(status_code=401, detail=MENSAJE_INCORRECTO)

    usuario = personal_a_diccionario(personal)
    request.session.clear()
    request.session["usuario"] = usuario
    return {"mensaje": "Sesión iniciada.", "usuario": usuario}


# es POST (botón dentro de un <form>) para que un enlace externo no pueda cerrar la sesión
@router.post("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
