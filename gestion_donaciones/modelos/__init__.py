"""Modelo de datos del dominio"""

from gestion_donaciones.modelos.enums import (
    EstadoElegibilidad,
    EstadoSolicitud,
    EstadoUnidad,
    FactorRh,
    GrupoSanguineo,
    TipoSangre,
    TipoDonacion,
)
from gestion_donaciones.modelos.persona import Persona
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.donacion import Donacion
from gestion_donaciones.modelos.unidad import Unidad
from gestion_donaciones.modelos.solicitud_stock import SolicitudStock