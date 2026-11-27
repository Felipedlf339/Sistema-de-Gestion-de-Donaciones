from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos.despacho import Despacho
from gestion_donaciones.modelos.enums import (
    EstadoDespacho,
    EstadoSolicitud,
    EstadoUnidad,
)


class ErrorDespacho(Exception):
    """Base de los errores al despachar (el mensaje se puede mostrar al usuario)"""


class SolicitudNoEncontrada(ErrorDespacho):
    pass


class SolicitudNoPendiente(ErrorDespacho):
    pass


class StockInsuficiente(ErrorDespacho):
    def __init__(self, pedidas, disponibles, tipo, grupo):
        self.pedidas = pedidas
        self.disponibles = disponibles
        super().__init__(
            f"Stock insuficiente: se pidieron {pedidas} unidades de {tipo} {grupo} "
            f"y solo hay {disponibles} disponibles."
        )


@dataclass
class ResultadoDespacho:
    despacho: Despacho
    unidades: list[dict]    # unidades que quedaron reservadas, en el orden en que se eligieron

    @property
    def ids_unidades(self):
        return [unidad["id_unidad"] for unidad in self.unidades]


def despachar_solicitud(id_solicitud, id_encargado, hoy=None):
    hoy = hoy or date.today()
    ahora = datetime.now()

    with closing(obtener_conexion()) as conexion:
        try:
            conexion.execute("BEGIN IMMEDIATE")

            solicitud = conexion.execute(
                "SELECT * FROM solicitudes WHERE id_solicitud = ?", (id_solicitud,)
            ).fetchone()
            if solicitud is None:
                raise SolicitudNoEncontrada(f"No existe la solicitud {id_solicitud}.")
            if solicitud["estado"].upper() != EstadoSolicitud.PENDIENTE.value:
                raise SolicitudNoPendiente(
                    f"La solicitud {id_solicitud} ya no está pendiente."
                )

            cantidad = solicitud["cantidad"]
            tipo = solicitud["tipo_hemoderivado"]
            grupo = solicitud["grupo_sanguineo"]
            if not isinstance(cantidad, int) or cantidad < 1:
                raise ErrorDespacho("La solicitud no tiene una cantidad válida.")
            unidades = conexion.execute(
                """
                SELECT id_unidad, tipo_componente, tipo_sangre, fecha_caducidad
                FROM unidades
                WHERE estado = ? COLLATE NOCASE
                  AND tipo_componente = ? COLLATE NOCASE
                  AND tipo_sangre = ? COLLATE NOCASE
                  AND fecha_caducidad >= ?
                ORDER BY fecha_caducidad ASC, id_unidad ASC
                LIMIT ?
                """,
                (EstadoUnidad.DISPONIBLE.value, tipo, grupo, hoy.isoformat(), cantidad),
            ).fetchall()
            if len(unidades) < cantidad:
                raise StockInsuficiente(cantidad, len(unidades), tipo, grupo)

            id_despacho = conexion.execute(
                "INSERT INTO despachos (id_solicitud, id_encargado, fecha_despacho, estado) "
                "VALUES (?, ?, ?, ?)",
                (id_solicitud, id_encargado, ahora.isoformat(timespec="seconds"),
                 EstadoDespacho.EN_TRANSITO.value),
            ).lastrowid

            for unidad in unidades:
                reservada = conexion.execute(
                    "UPDATE unidades SET estado = ?, id_despacho = ? "
                    "WHERE id_unidad = ? AND estado = ? COLLATE NOCASE",
                    (EstadoUnidad.RESERVADA.value, id_despacho, unidad["id_unidad"],
                     EstadoUnidad.DISPONIBLE.value),
                ).rowcount
                if reservada != 1:
                    # no debería pasar dentro de la transacción; si pasa, no se despacha nada
                    raise StockInsuficiente(cantidad, 0, tipo, grupo)

            conexion.execute(
                "UPDATE solicitudes SET estado = ? WHERE id_solicitud = ?",
                (EstadoSolicitud.ATENDIDA.value, id_solicitud),
            )
            conexion.commit()

        except BaseException:
            if conexion.in_transaction:
                conexion.rollback()
            raise

    despacho = Despacho(
        id_solicitud=id_solicitud,
        id_encargado=id_encargado,
        fecha_despacho=ahora,
        estado=EstadoDespacho.EN_TRANSITO,
        id_despacho=id_despacho,
    )
    return ResultadoDespacho(despacho=despacho, unidades=[dict(u) for u in unidades])
