"""Modelo CentroMedico, institución que solicita y recibe unidades"""


class CentroMedico:

    def __init__(self, nombre, direccion=None):
        self.nombre = nombre
        self.direccion = direccion

        # se asigna al guardar en la base de datos
        self.id_centro_medico = None
