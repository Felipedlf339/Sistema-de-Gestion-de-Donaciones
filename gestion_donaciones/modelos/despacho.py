from datetime import datetime
from gestion_donaciones.modelos.enums import EstadoDespacho


class Despacho:

    def __init__(
        self,
        id_solicitud: int,
        id_encargado: int,
        fecha_despacho=None,
        fecha_recepcion=None,
        estado: EstadoDespacho = EstadoDespacho.EN_TRANSITO,
        id_despacho: int | None = None,
    ):
        self.id_despacho = id_despacho              # se asigna al guardar en la base de datos
        self.id_solicitud = id_solicitud            # solicitud que se está atendiendo
        self.id_encargado = id_encargado            # personal que prepara el despacho
        self.fecha_despacho = fecha_despacho or datetime.now()
        self.fecha_recepcion = fecha_recepcion      # None hasta que el centro medico recibe las unidades
        self.estado = estado

    @property
    def id(self):
        return self.id_despacho

    @id.setter
    def id(self, valor):
        self.id_despacho = valor
