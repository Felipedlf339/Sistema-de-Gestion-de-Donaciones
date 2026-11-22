import sqlite3
from gestion_donaciones.modelos.enums import EstadoSolicitud, EstadoUnidad


class ReservaFallidaError(Exception):
    """Se lanza cuando otra operación reservó antes alguna de las unidades."""


def reservar_unidades_despacho(
    conexion: sqlite3.Connection,
    id_despacho: int,
    ids_unidades: list[int],
) -> bool:
    """
    Si alguna unidad no existe o ya no está disponible, deshace toda la operación
    y retorna False. Si todas se reservan, confirma y retorna True.
    """
    if not ids_unidades:
        return False
    if len(set(ids_unidades)) != len(ids_unidades):
        return False

    cursor = conexion.cursor()
    try:
        if not conexion.in_transaction:
            cursor.execute("BEGIN IMMEDIATE")

        for id_unidad in ids_unidades:
            cursor.execute(
                """
                UPDATE unidades
                SET estado = ?,
                    id_despacho = ?
                WHERE id_unidad = ?
                  AND estado = ?
                """,
                (
                    EstadoUnidad.RESERVADA.value,
                    id_despacho,
                    id_unidad,
                    EstadoUnidad.DISPONIBLE.value,
                ),
            )

            if cursor.rowcount == 0:
                conexion.rollback()
                return False

        conexion.commit()
        return True

    except sqlite3.Error:
        if conexion.in_transaction:
            conexion.rollback()
        raise


def procesar_reserva_solicitud(
    conexion: sqlite3.Connection,
    id_solicitud: int,
    id_despacho: int,
    ids_unidades: list[int],
) -> None:
    """
    Intenta reservar las unidades para la solicitud.
    Si falla porque otra operación las tomó antes, lanza ReservaFallidaError
    con el aviso para el usuario y deja la solicitud en estado PENDIENTE.
    """
    exito = reservar_unidades_despacho(conexion, id_despacho, ids_unidades)
    if not exito:
        raise ReservaFallidaError(
            "Las unidades ya fueron reservadas, intente nuevamente"
        )

    with conexion:
        conexion.execute(
            "UPDATE solicitudes SET estado = ? WHERE id_solicitud = ?",
            (EstadoSolicitud.ATENDIDA.value, id_solicitud),
        )