"""Modelo de datos del dominio"""

from gestion_donaciones.modelos.enums import (
    CargoMedico,
    CargoPersonal,
    EstadoElegibilidad,
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
from gestion_donaciones.modelos.centro_medico import CentroMedico
from gestion_donaciones.modelos.personalCentroDonacion import PersonalCentroDonacion
from gestion_donaciones.modelos.personal_centro_medico import PersonalCentroMedico