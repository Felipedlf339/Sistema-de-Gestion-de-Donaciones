from contextlib import closing
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.despacho_solicitudes import (
    ErrorDespacho,
    SolicitudNoEncontrada,
    despachar_solicitud,
)
from gestion_donaciones.modelos.enums import EstadoSolicitud
from pydantic import BaseModel

from gestion_donaciones.database import obtener_conexion, reservar_unidades_despacho
from gestion_donaciones.modelos.enums import EstadoDespacho, EstadoSolicitud, EstadoUnidad
from gestion_donaciones.rutas.permisos import obtener_usuario

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


@router.post("/solicitudes/{id_solicitud}/despachar")
def despachar(id_solicitud: int, usuario=Depends(obtener_usuario)):
    """Despacha la solicitud con las unidades que vencen antes (asignación automática)"""
    try:
        resultado = despachar_solicitud(id_solicitud, usuario["id_personal"])
    except SolicitudNoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ErrorDespacho as error:  
        raise HTTPException(status_code=409, detail=str(error))

    return {
        "id_despacho": resultado.despacho.id_despacho,
        "id_solicitud": id_solicitud,
        "estado": resultado.despacho.estado.value,
        "unidades": resultado.ids_unidades,
    }
def obtener_solicitud(id_solicitud):
    with closing(obtener_conexion()) as c:
        return c.execute(
            """SELECT s.id_solicitud, s.id_centro_medico, c.nombre AS centro_medico,
                      s.tipo_hemoderivado, s.grupo_sanguineo, s.cantidad,
                      s.fecha_solicitud, s.estado
               FROM solicitudes s
               LEFT JOIN centros_medicos c ON c.id_centro_medico = s.id_centro_medico
               WHERE s.id_solicitud = ?""", (id_solicitud,)).fetchone()


def obtener_unidades_disponibles(tipo, grupo):
    """Unidades DISPONIBLES, no vencidas, del mismo componente y grupo; las que vencen antes primero"""
    with closing(obtener_conexion()) as c:
        filas = c.execute(
            """SELECT id_unidad, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad
               FROM unidades
               WHERE estado = ? AND UPPER(tipo_componente) = UPPER(?)
                 AND tipo_sangre = ? AND date(fecha_caducidad) >= date('now')
               ORDER BY fecha_caducidad ASC, id_unidad ASC""",
            (EstadoUnidad.DISPONIBLE.value, tipo, grupo)).fetchall()
    return [
        {
            "id_unidad": f["id_unidad"],
            "tipo": f["tipo_componente"].capitalize(),
            "grupo_sanguineo": f["tipo_sangre"],
            "fecha_extraccion": datetime.fromisoformat(f["fecha_extraccion"]).strftime("%d/%m/%Y"),
            "fecha_caducidad": datetime.fromisoformat(f["fecha_caducidad"]).strftime("%d/%m/%Y"),
        }
        for f in filas
    ]


@router.get("/nuevo", response_class=HTMLResponse)
def ver_formulario_despacho(request: Request, solicitud: int):
    s = obtener_solicitud(solicitud)
    if s is None or s["estado"].upper() != EstadoSolicitud.PENDIENTE.value:
        raise HTTPException(status_code=404, detail="La solicitud no existe o ya fue atendida.")
    datos = {
        "id_solicitud": s["id_solicitud"],
        "centro_medico": s["centro_medico"] or f"Centro médico #{s['id_centro_medico']}",
        "tipo": s["tipo_hemoderivado"],
        "grupo_sanguineo": s["grupo_sanguineo"],
        "cantidad": s["cantidad"],
        "fecha": formatear_fecha(s["fecha_solicitud"]),
    }
    return templates.TemplateResponse(
        request=request,
        name="despacho_nuevo.html",
        context={
            "solicitud": datos,
            "unidades": obtener_unidades_disponibles(s["tipo_hemoderivado"], s["grupo_sanguineo"]),
        },
    )


class DespachoCreate(BaseModel):
    id_solicitud: int
    ids_unidades: list[int]


@router.post("/nuevo")
def crear_despacho(datos: DespachoCreate, usuario=Depends(obtener_usuario)):
    s = obtener_solicitud(datos.id_solicitud)
    if s is None or s["estado"].upper() != EstadoSolicitud.PENDIENTE.value:
        raise HTTPException(status_code=404, detail="La solicitud no existe o ya fue atendida.")
    if len(set(datos.ids_unidades)) != s["cantidad"]:
        raise HTTPException(status_code=400, detail=f"Debe seleccionar exactamente {s['cantidad']} unidad(es).")

    validas = {u["id_unidad"] for u in obtener_unidades_disponibles(s["tipo_hemoderivado"], s["grupo_sanguineo"])}
    if not set(datos.ids_unidades) <= validas:
        raise HTTPException(status_code=400, detail="Alguna unidad ya no está disponible. Actualice la pantalla.")

    with closing(obtener_conexion()) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute("UPDATE solicitudes SET estado = 'ATENDIDA' WHERE id_solicitud = ?", (datos.id_solicitud,))
            cursor = c.execute(
                """INSERT INTO despachos (id_solicitud, id_encargado, fecha_despacho, estado)
                   VALUES (?, ?, ?, ?)""",
                (datos.id_solicitud, usuario["id_personal"],
                 datetime.now().isoformat(timespec="seconds"), EstadoDespacho.EN_TRANSITO.value),
            )
            id_despacho = cursor.lastrowid
            # reserva las unidades y confirma; si falla alguna, deshace todo
            if not reservar_unidades_despacho(c, id_despacho, datos.ids_unidades):
                raise HTTPException(status_code=409, detail="Alguna unidad ya no está disponible.")
        except Exception:
            c.rollback()
            raise

    return {"mensaje": f"Despacho #{id_despacho} creado. Las unidades quedaron en tránsito."}
