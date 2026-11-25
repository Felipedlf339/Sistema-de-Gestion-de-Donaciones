from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from gestion_donaciones.modelos.recepcion_despachos import (
    DespachoDeOtroCentro,
    DespachoNoEncontrado,
    DespachoYaEntregado,
    confirmar_recepcion,
    listar_despachos_en_transito,
    obtener_personal,
)
from gestion_donaciones.rutas.permisos import obtener_usuario

router = APIRouter(prefix="/despachos/recepcion", tags=["Recepción de despachos"])
templates = Jinja2Templates(directory="templates")

SIN_CENTRO = "Su usuario no está asociado a un centro médico."


@router.get("", response_class=HTMLResponse)
def ver_recepcion(request: Request, usuario=Depends(obtener_usuario)):
    personal = obtener_personal(usuario)
    if personal is None or personal["id_centro_medico"] is None:
        despachos, error = [], SIN_CENTRO
    else:
        despachos, error = listar_despachos_en_transito(personal["id_centro_medico"]), None
    return templates.TemplateResponse(
        request=request,
        name="recepcion_despachos.html",
        context={"despachos": despachos, "error": error},
    )


@router.post("/{id_despacho}/confirmar")
def confirmar(id_despacho: int, usuario=Depends(obtener_usuario)):
    personal = obtener_personal(usuario)
    if personal is None or personal["id_centro_medico"] is None:
        raise HTTPException(status_code=403, detail=SIN_CENTRO)
    try:
        confirmar_recepcion(id_despacho, personal["id_personal"], personal["id_centro_medico"])
    except DespachoNoEncontrado:
        raise HTTPException(status_code=404, detail="El despacho no existe.")
    except DespachoDeOtroCentro:
        raise HTTPException(status_code=403, detail="Ese despacho es de otro centro médico.")
    except DespachoYaEntregado:
        raise HTTPException(status_code=409, detail="La recepción de este despacho ya fue confirmada.")
    return {"mensaje": f"Recepción del despacho #{id_despacho} confirmada."}