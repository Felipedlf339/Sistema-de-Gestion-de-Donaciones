"""Rutas del formulario de registro de donantes (HU-01, tarea 1.2)."""

from datetime import date

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.enums import FactorRh, GrupoSanguineo
from gestion_donaciones.registro_donantes import RegistroDonantes

router = APIRouter(prefix="/donantes", tags=["Donantes"])
templates = Jinja2Templates(directory="templates")

registro = RegistroDonantes()


class DonanteRequest(BaseModel):
    # Todo llega como texto, las reglas las revisa validar_donante()
    run: str | None = None
    nombre: str | None = None
    correo: str | None = None
    telefono: str | None = None
    grupo_sanguineo: str | None = None
    factor_rh: str | None = None
    fecha_nacimiento: str | None = None
    peso_kg: str | None = None


def limpiar(texto):
    # quita espacios y deja None si el campo viene vacío
    if texto is None:
        return None
    texto = texto.strip()
    if texto == "":
        return None
    return texto


# Si un valor no se puede convertir se deja el texto original,
# así validar_donante() lo marca como inválido
def convertir_grupo(texto):
    if texto is None:
        return None
    try:
        return GrupoSanguineo(texto.upper())
    except ValueError:
        return texto


def convertir_factor(texto):
    if texto is None:
        return None
    try:
        return FactorRh(texto)
    except ValueError:
        return texto


def convertir_peso(texto):
    if texto is None:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return texto


def convertir_fecha(texto):
    if texto is None:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return texto


def crear_donante(datos):
    return Donante(
        run=limpiar(datos.run),
        nombre=limpiar(datos.nombre),
        grupo_sanguineo=convertir_grupo(limpiar(datos.grupo_sanguineo)),
        factor_rh=convertir_factor(limpiar(datos.factor_rh)),
        correo=limpiar(datos.correo),
        telefono=limpiar(datos.telefono),
        fecha_nacimiento=convertir_fecha(limpiar(datos.fecha_nacimiento)),
        peso_kg=convertir_peso(limpiar(datos.peso_kg)),
    )


def donante_a_diccionario(donante):
    estado = donante.estado_elegibilidad
    return {
        "id_donante": donante.id_donante,
        "run": donante.run,
        "nombre": donante.nombre,
        "correo": donante.correo,
        "telefono": donante.telefono,
        "tipo_sangre": donante.tipo_sangre().value,
        "estado": estado.value if estado else None,
    }


@router.get("/registrar", response_class=HTMLResponse)
def ver_formulario_donante(request: Request):
    return templates.TemplateResponse(request=request, name="registro_donantes.html")


@router.post("/registrar")
def procesar_registro_donante(datos: DonanteRequest):
    donante = crear_donante(datos)
    errores = registro.registrar(donante)

    if errores:
        # si el RUN ya estaba registrado se muestra ese donante (CU-01, paso 2)
        existente = registro.buscar_por_run(donante.run)
        if existente is not None:
            return JSONResponse(
                status_code=409,
                content={
                    "mensaje": "Ya existe un donante registrado con ese RUN.",
                    "donante": donante_a_diccionario(existente),
                },
            )
        raise HTTPException(status_code=400, detail=errores)

    return {
        "mensaje": "Donante registrado con éxito.",
        "donante": donante_a_diccionario(donante),
    }
