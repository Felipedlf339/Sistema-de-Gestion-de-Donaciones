from gestion_donaciones.modelos.persona import Persona

class PersonalCentroDonacion (Persona):
    def __init__(self, run, nombre, id_personal, cargo, correo=None, telefono=None):
        super().__init__(run, nombre, correo, telefono)
        self.id_personal = id_personal
        self.cargo = cargo