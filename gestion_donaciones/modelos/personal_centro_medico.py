"""Modelo PersonalCentroMedico, funcionario del centro médico"""

from gestion_donaciones.modelos.persona import Persona


class PersonalCentroMedico(Persona):

    def __init__(self, run, nombre, cargo, centro_medico, correo=None, telefono=None):
        super().__init__(run, nombre, correo, telefono)
        self.cargo = cargo                  # CargoMedico
        self.centro_medico = centro_medico  # CentroMedico al que pertenece

        # se asigna al guardar en la base de datos
        self.id_personal = None
