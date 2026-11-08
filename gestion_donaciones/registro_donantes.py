"""Registro de donantes en memoria (HU-01, tarea 1.3)."""

from gestion_donaciones.validaciones import normalizar_run, validar_donante


class RegistroDonantes:
    # guarda los donantes en memoria usando el RUN normalizado como clave.
    # mas adelante se puede cambiar por una base de datos manteniendo los mismos métodos.

    def __init__(self):
        self.donantes = {}
        self.siguiente_id = 1

    def buscar_por_run(self, run):
        # Devuelve el donante con ese RUN, o None si no está registrado
        clave = normalizar_run(run)

        if clave is None:
            return None

        return self.donantes.get(clave)

    def registrar(self, donante):
        # valida y guarda un donante nuevo.
        # devuelve una lista con los mensajes de error.
        errores = validar_donante(donante)

        if len(errores) > 0:
            return errores

        donante.run = normalizar_run(donante.run)
        donante.id_donante = self.siguiente_id
        self.siguiente_id = self.siguiente_id + 1
        self.donantes[donante.run] = donante

        return []
