"""Clase abstracta Persona, datos comunes de donantes y personal"""


class Persona:
    # Clase base, no se usa directamente, sino a través de Donante y del personal de los centros

    def __init__(self, run, nombre, correo=None, telefono=None):
        self.run = run
        self.nombre = nombre
        self.correo = correo
        self.telefono = telefono
