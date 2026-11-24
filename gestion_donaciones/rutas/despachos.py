from contextlib import closing
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos.enums import EstadoSolicitud

router = APIRouter(prefix="/despachos", tags=["Despachos"])
templates = Jinja2Templates(directory="templates")


def formatear_fecha(texto):
    try:
        return datetime.fromisoformat(texto).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return texto or ""


def obtener_solicitudes_pendientes():
    """Solicitudes PENDIENTES de todos los centros médicos, de la más antigua a la más reciente"""
    with closing(obtener_conexion()) as conexion:
        filas = conexion.execute(
            """
            SELECT s.id_solicitud, s.id_centro_medico, c.nombre AS centro_medico,
                   s.tipo_hemoderivado, s.grupo_sanguineo, s.cantidad, s.fecha_solicitud
            FROM solicitudes s
            LEFT JOIN centros_medicos c ON c.id_centro_medico = s.id_centro_medico
            WHERE UPPER(s.estado) = ?
            ORDER BY datetime(s.fecha_solicitud) ASC, s.id_solicitud ASC
            """,
            (EstadoSolicitud.PENDIENTE.value,),
        ).fetchall()

    return [
        {
            "id_solicitud": fila["id_solicitud"],
            "centro_medico": fila["centro_medico"] or f"Centro médico #{fila['id_centro_medico']}",
            "tipo": fila["tipo_hemoderivado"],
            "grupo_sanguineo": fila["grupo_sanguineo"],
            "cantidad": fila["cantidad"],
            "fecha": formatear_fecha(fila["fecha_solicitud"]),
        }
        for fila in filas
    ]


@router.get("/pendientes", response_class=HTMLResponse)
def ver_solicitudes_pendientes(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="solicitudes_pendientes.html",
        context={"solicitudes": obtener_solicitudes_pendientes()},
    )
