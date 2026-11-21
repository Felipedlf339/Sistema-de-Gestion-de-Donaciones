from datetime import datetime
from gestion_donaciones.modelos.enums import EstadoSolicitud


class SolicitudStock:
    def __init__(
        self,
        id_centro_medico: int,
        tipo_hemoderivado: str,
        grupo_sanguineo: str,
        cantidad: int,
        fecha_solicitud=None,
        estado: EstadoSolicitud = EstadoSolicitud.PENDIENTE,
        id_solicitud: int | None = None,
    ):
        self.id_solicitud = id_solicitud
        self.id_centro_medico = id_centro_medico
        self.tipo_hemoderivado = tipo_hemoderivado
        self.grupo_sanguineo = grupo_sanguineo
        self.cantidad = cantidad
        self.fecha_solicitud = fecha_solicitud or datetime.now()
        self.estado = estado

    @property
    def id(self):
        return self.id_solicitud

    @id.setter
    def id(self, valor):
        self.id_solicitud = valor