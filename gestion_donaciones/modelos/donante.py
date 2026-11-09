"""Modelo Donante (HU-01, tarea 1.1)."""

from gestion_donaciones.modelos.enums import EstadoElegibilidad, TipoSangre
from gestion_donaciones.modelos.persona import Persona


class Donante(Persona):

    def __init__(self, run, nombre, grupo_sanguineo, factor_rh,
                 correo=None, telefono=None, fecha_nacimiento=None, peso_kg=None):
        super().__init__(run, nombre, correo, telefono)
        self.grupo_sanguineo = grupo_sanguineo
        self.factor_rh = factor_rh
        self.fecha_nacimiento = fecha_nacimiento
        self.peso_kg = peso_kg

        # Datos que se completan después del registro
        self.id_donante = None              
        self.estado_elegibilidad = None     
        self.fecha_habilitacion = None
        self.fecha_ultima_donacion = None

    def tipo_sangre(self):
        return TipoSangre(self.grupo_sanguineo.value + self.factor_rh.value)

    def es_apto(self):
        return self.estado_elegibilidad == EstadoElegibilidad.APTO
    
    def cambiar_elegibilidad(self, nuevo_estado):
        self.estado_elegibilidad = nuevo_estado
