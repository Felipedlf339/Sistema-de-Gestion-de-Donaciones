from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from gestion_donaciones.modelos.despachos import (
    DespachoDeOtroCentro,
    DespachoNoEncontrado,
    DespachoYaEntregado,
    confirmar_recepcion,
    listar_despachos_en_transito,
    obtener_personal,
)
from gestion_donaciones.rutas.sesion import usuario_en_sesion

router = APIRouter(prefix="/entregas", tags=["entregas"])
templates = Jinja2Templates(directory="templates")


def obtener_personal_actual(request: Request):
    usuario = usuario_en_sesion(request)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    personal = obtener_personal(usuario["id_personal"])
    if personal is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    return personal


@router.get("")
def vista_entregas(request: Request):
    personal = obtener_personal_actual(request)

    if personal["id_centro_medico"] is None:
        raise HTTPException(status_code=403, detail="Solo el personal de un centro médico puede ver las entregas.")

    despachos = listar_despachos_en_transito(personal["id_centro_medico"])
    return templates.TemplateResponse(
        request=request,
        name="entregas.html",
        context={"despachos": despachos, "nombre": personal["nombre"]},
    )


@router.post("/{id_despacho}/confirmar")
def confirmar_entrega(id_despacho: int, request: Request):
    personal = obtener_personal_actual(request)

    if personal["id_centro_medico"] is None:
        raise HTTPException(status_code=403, detail="Solo el personal de un centro médico puede confirmar entregas.")

    try:
        fecha = confirmar_recepcion(id_despacho, personal["id_personal"], personal["id_centro_medico"])
    except DespachoNoEncontrado:
        raise HTTPException(status_code=404, detail="El despacho no existe.")
    except DespachoDeOtroCentro:
        raise HTTPException(status_code=403, detail="El despacho no es de su centro médico.")
    except DespachoYaEntregado:
        raise HTTPException(status_code=409, detail="El despacho ya fue entregado.")

    return {"mensaje": "Recepción confirmada.", "fecha_recepcion": fecha}