"""Consulta de despachos para el personal de centro médico (HU-11, T44)."""

from contextlib import closing
from datetime import datetime

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos.enums import EstadoDespacho, EstadoUnidad


def _formatear_fecha(texto, con_hora=False):
    if not texto:
        return ""
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return texto
    return fecha.strftime("%d-%m-%Y %H:%M" if con_hora else "%d-%m-%Y")


def obtener_personal(id_personal):
    with closing(obtener_conexion()) as conexion:
        return conexion.execute(
            "SELECT id_personal, nombre, id_centro_medico FROM personal WHERE id_personal = ?",
            (id_personal,),
        ).fetchone()


def listar_despachos_en_transito(id_centro_medico):
    with closing(obtener_conexion()) as conexion:
        despachos = conexion.execute(
            """
            SELECT id_despacho, fecha_despacho
            FROM despachos
            WHERE id_centro_medico = ? AND estado = ?
            ORDER BY fecha_despacho ASC
            """,
            (id_centro_medico, EstadoDespacho.EN_TRANSITO.value),
        ).fetchall()

        resultado = []
        for despacho in despachos:
            unidades = conexion.execute(
                """
                SELECT id_unidad, tipo_componente, tipo_sangre, fecha_caducidad
                FROM unidades
                WHERE id_despacho = ?
                ORDER BY fecha_caducidad ASC, id_unidad ASC
                """,
                (despacho["id_despacho"],),
            ).fetchall()
            resultado.append({
                "id_despacho": despacho["id_despacho"],
                "fecha_despacho": _formatear_fecha(despacho["fecha_despacho"], con_hora=True),
                "unidades": [
                    {
                        "id_unidad": u["id_unidad"],
                        "tipo": u["tipo_componente"].capitalize(),
                        "grupo_sanguineo": u["tipo_sangre"],
                        "fecha_caducidad": _formatear_fecha(u["fecha_caducidad"]),
                    }
                    for u in unidades
                ],
            })
    return resultado


class DespachoNoEncontrado(Exception):
    pass


class DespachoDeOtroCentro(Exception):
    pass


class DespachoYaEntregado(Exception):
    pass


def confirmar_recepcion(id_despacho, id_personal, id_centro_medico):
    """Confirma la recepción de un despacho (HU-11, T45).

    Deja el despacho ENTREGADO con su fecha de recepción y sus unidades
    ENTREGADAS, todo en una sola transacción: si algo falla, no cambia nada.
    Devuelve la fecha de recepción guardada (ISO).
    """
    fecha = datetime.now().isoformat(timespec="seconds")

    with closing(obtener_conexion()) as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        try:
            despacho = conexion.execute(
                "SELECT id_centro_medico FROM despachos WHERE id_despacho = ?",
                (id_despacho,),
            ).fetchone()
            if despacho is None:
                raise DespachoNoEncontrado()

            if despacho["id_centro_medico"] != id_centro_medico:
                raise DespachoDeOtroCentro()

            cursor = conexion.execute(
                """
                UPDATE despachos
                SET estado = ?, fecha_recepcion = ?, id_personal_receptor = ?
                WHERE id_despacho = ? AND estado = ?
                """,
                (EstadoDespacho.ENTREGADO.value, fecha, id_personal,
                 id_despacho, EstadoDespacho.EN_TRANSITO.value),
            )
            if cursor.rowcount == 0:
                raise DespachoYaEntregado()

            conexion.execute(
                "UPDATE unidades SET estado = ? WHERE id_despacho = ? AND estado = ?",
                (EstadoUnidad.ENTREGADA.value, id_despacho, EstadoUnidad.RESERVADA.value),
            )
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise

    return fecha