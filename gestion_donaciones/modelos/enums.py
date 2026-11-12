"""Enumeraciones del dominio que usa el registro de donantes"""

from enum import Enum


class GrupoSanguineo(Enum):
    A = "A"
    B = "B"
    AB = "AB"
    O = "O"


class FactorRh(Enum):
    POSITIVO = "+"
    NEGATIVO = "-"


class TipoSangre(Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class EstadoElegibilidad(Enum):
    APTO = "APTO"
    DIFERIDO_TEMPORAL = "DIFERIDO_TEMPORAL"
    RECHAZADO_PERMANENTE = "RECHAZADO_PERMANENTE"

class TipoDonacion(Enum):
    SANGRE = "SANGRE"
    PLAQUETAS = "PLAQUETAS"
 
 
class EstadoUnidad(Enum):
    DISPONIBLE = "DISPONIBLE"
    RESERVADA = "RESERVADA"
    UTILIZADA = "UTILIZADA"
    CADUCADA = "CADUCADA"

class TipoDonacion(Enum):
    SANGRE = "SANGRE"
    PLAQUETAS = "PLAQUETAS"
 
 
class EstadoUnidad(Enum):
    DISPONIBLE = "DISPONIBLE"
    RESERVADA = "RESERVADA"
    UTILIZADA = "UTILIZADA"
    CADUCADA = "CADUCADA"

class CargoPersonal(Enum):
    ATENCION_DONANTE = "Personal de atención al donante"
    ENCARGADO_INVENTARIO = "Encargado de inventario"