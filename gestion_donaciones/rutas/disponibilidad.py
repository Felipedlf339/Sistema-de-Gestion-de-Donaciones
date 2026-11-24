from datetime import datetime
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos import EstadoSolicitud, SolicitudStock

router = APIRouter()
templates = Jinja2Templates(directory="templates")

ID_CENTRO_MEDICO_POR_DEFECTO = 1


def _obtener_unidades_disponibles(
    conexion,
    tipo: str | None = None,
    grupo: str | None = None,
    rh: str | None = None,
    vence_antes_de: str | None = None,
):
    cursor = conexion.cursor()
    query = "SELECT * FROM unidades WHERE LOWER(estado) = 'disponible'"
    parametros = []

    if tipo:
        query += " AND tipo_componente = ?"
        parametros.append(tipo)

    if grupo and rh:
        query += " AND tipo_sangre = ?"
        parametros.append(f"{grupo}{rh}")
    elif grupo:
        query += " AND tipo_sangre LIKE ?"
        parametros.append(f"{grupo}%")
    elif rh:
        query += " AND tipo_sangre LIKE ?"
        parametros.append(f"%{rh}")

    if vence_antes_de:
        query += " AND fecha_caducidad <= ?"
        parametros.append(vence_antes_de)

    cursor.execute(query, parametros)
    return cursor.fetchall()


def _resolver_id_centro_medico(request: Request, conexion) -> int:
    """Obtiene el id_centro_medico del usuario en sesión o usa uno fijo por defecto."""
    usuario = None
    if "session" in request.scope:
        usuario = request.session.get("usuario")

    cursor = conexion.cursor()
    if isinstance(usuario, dict):
        if usuario.get("id_centro_medico"):
            return int(usuario["id_centro_medico"])

        if usuario.get("id_personal"):
            cursor.execute(
                "SELECT id_centro_medico FROM personal WHERE id_personal = ?",
                (usuario["id_personal"],),
            )
            fila = cursor.fetchone()
            if fila and fila["id_centro_medico"] is not None:
                return int(fila["id_centro_medico"])

        if usuario.get("centro_medico"):
            cursor.execute(
                "SELECT id_centro_medico FROM centros_medicos WHERE nombre = ?",
                (usuario["centro_medico"],),
            )
            fila = cursor.fetchone()
            if fila:
                return int(fila["id_centro_medico"])

    cursor.execute("SELECT id_centro_medico FROM centros_medicos ORDER BY id_centro_medico ASC LIMIT 1")
    fila_centro = cursor.fetchone()
    if fila_centro:
        return int(fila_centro["id_centro_medico"])

    return ID_CENTRO_MEDICO_POR_DEFECTO


def _obtener_solicitudes_centro(conexion, id_centro_medico: int):
    """Obtiene las solicitudes del centro médico ordenadas de más reciente a más antigua."""
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT id_solicitud, tipo_hemoderivado, grupo_sanguineo, cantidad, fecha_solicitud, estado
        FROM solicitudes
        WHERE id_centro_medico = ?
        ORDER BY fecha_solicitud DESC, id_solicitud DESC
        """,
        (id_centro_medico,),
    )
    return cursor.fetchall()


@router.get("/stock", response_class=HTMLResponse)
def consultar_disponibilidad(
    request: Request,
    tipo: str = Query(None),
    grupo: str = Query(None),
    rh: str = Query(None),
    vence_antes_de: str = Query(None),
):
    conexion = obtener_conexion()
    unidades_db = _obtener_unidades_disponibles(conexion, tipo, grupo, rh, vence_antes_de)
    id_centro_medico = _resolver_id_centro_medico(request, conexion)
    solicitudes_db = _obtener_solicitudes_centro(conexion, id_centro_medico)
    conexion.close()

    return templates.TemplateResponse(
        request=request,
        name="disponibilidad.html",
        context={
            "request": request,
            "unidades": unidades_db,
            "solicitudes": solicitudes_db,
        },
    )


@router.post("/stock/solicitar", response_class=HTMLResponse)
def solicitar_stock(
    request: Request,
    tipo_hemoderivado: str = Form(""),
    grupo_sanguineo: str = Form(""),
    cantidad: str = Form(""),
):
    tipo_limpio = (tipo_hemoderivado or "").strip()
    grupo_limpio = (grupo_sanguineo or "").strip()
    cantidad_texto = (cantidad or "").strip()

    conexion = obtener_conexion()
    id_centro_medico = _resolver_id_centro_medico(request, conexion)

    def _responder_error(mensaje: str):
        unidades_db = _obtener_unidades_disponibles(conexion)
        solicitudes_db = _obtener_solicitudes_centro(conexion, id_centro_medico)
        conexion.close()
        return templates.TemplateResponse(
            request=request,
            name="disponibilidad.html",
            status_code=400,
            context={
                "request": request,
                "unidades": unidades_db,
                "solicitudes": solicitudes_db,
                "mensaje_error": mensaje,
                "form_tipo": tipo_limpio,
                "form_grupo": grupo_limpio,
                "form_cantidad": cantidad_texto,
            },
        )

    if not tipo_limpio:
        return _responder_error("Debe seleccionar el tipo de hemoderivado.")

    if not grupo_limpio:
        return _responder_error("Debe seleccionar el grupo sanguíneo.")

    if not cantidad_texto:
        return _responder_error("Debe ingresar una cantidad válida mayor a 0.")

    try:
        cantidad_int = int(cantidad_texto)
    except ValueError:
        return _responder_error("La cantidad debe ser un número entero mayor a 0.")

    if cantidad_int <= 0:
        return _responder_error("La cantidad solicitada debe ser mayor a 0.")

    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM unidades
        WHERE LOWER(estado) = 'disponible'
          AND tipo_componente = ?
          AND tipo_sangre = ?
        """,
        (tipo_limpio, grupo_limpio),
    )
    disponibles = cursor.fetchone()["total"]

    if cantidad_int > disponibles:
        return _responder_error(
            f"Stock insuficiente: solo hay {disponibles} disponibles de {tipo_limpio} ({grupo_limpio})."
        )

    solicitud = SolicitudStock(
        id_centro_medico=id_centro_medico,
        tipo_hemoderivado=tipo_limpio,
        grupo_sanguineo=grupo_limpio,
        cantidad=cantidad_int,
        fecha_solicitud=datetime.now(),
        estado=EstadoSolicitud.PENDIENTE,
    )

    with conexion:
        cursor.execute(
            """
            INSERT INTO solicitudes (
                id_centro_medico,
                tipo_hemoderivado,
                grupo_sanguineo,
                cantidad,
                fecha_solicitud,
                estado
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                solicitud.id_centro_medico,
                solicitud.tipo_hemoderivado,
                solicitud.grupo_sanguineo,
                solicitud.cantidad,
                solicitud.fecha_solicitud.isoformat(timespec="seconds"),
                solicitud.estado.value,
            ),
        )

    unidades_db = _obtener_unidades_disponibles(conexion)
    solicitudes_db = _obtener_solicitudes_centro(conexion, id_centro_medico)
    conexion.close()

    return templates.TemplateResponse(
        request=request,
        name="disponibilidad.html",
        context={
            "request": request,
            "unidades": unidades_db,
            "solicitudes": solicitudes_db,
            "mensaje_exito": (
                f"Solicitud registrada en estado Pendiente: {cantidad_int} unidad(es) de "
                f"{tipo_limpio} ({grupo_limpio})."
            ),
        },
    )