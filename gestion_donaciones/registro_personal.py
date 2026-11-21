"""Registro del personal en SQLite: alta, búsqueda por RUN e inicio de sesión (HU-07)"""

import sqlite3
from contextlib import closing

from gestion_donaciones.credenciales import generar_hash, verificar_contrasena
from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos.centro_medico import CentroMedico
from gestion_donaciones.modelos.enums import CargoMedico, CargoPersonal
from gestion_donaciones.modelos.personalCentroDonacion import PersonalCentroDonacion
from gestion_donaciones.modelos.personal_centro_medico import PersonalCentroMedico
from gestion_donaciones.validaciones import esta_vacio, normalizar_run, validar_run

# trae al funcionario junto con su centro médico (si tiene)
CONSULTA_PERSONAL = """
    SELECT p.*, c.nombre AS nombre_centro, c.direccion AS direccion_centro
    FROM personal p
    LEFT JOIN centros_medicos c ON c.id_centro_medico = p.id_centro_medico
    WHERE p.run = ?
"""


def fila_a_personal(fila):
    # id_centro_medico vacío = personal del centro de donación
    if fila["id_centro_medico"] is None:
        return PersonalCentroDonacion(
            run=fila["run"],
            nombre=fila["nombre"],
            id_personal=fila["id_personal"],
            cargo=CargoPersonal[fila["cargo"]],
            correo=fila["correo"],
            telefono=fila["telefono"],
        )

    centro = CentroMedico(fila["nombre_centro"], fila["direccion_centro"])
    centro.id_centro_medico = fila["id_centro_medico"]
    personal = PersonalCentroMedico(
        run=fila["run"],
        nombre=fila["nombre"],
        cargo=CargoMedico[fila["cargo"]],
        centro_medico=centro,
        correo=fila["correo"],
        telefono=fila["telefono"],
    )
    personal.id_personal = fila["id_personal"]
    return personal


class RegistroPersonal:

    def buscar_fila(self, run):
        clave = normalizar_run(run)
        if clave is None:
            return None
        with closing(obtener_conexion()) as conexion:
            return conexion.execute(CONSULTA_PERSONAL, (clave,)).fetchone()

    def buscar_por_run(self, run):
        # devuelve el funcionario con ese RUN, o None si no existe
        fila = self.buscar_fila(run)
        if fila is None:
            return None
        return fila_a_personal(fila)

    def iniciar_sesion(self, run, contrasena):
        # devuelve el funcionario si el RUN y la contraseña son correctos, si no None
        fila = self.buscar_fila(run)
        if fila is None:
            return None
        if not verificar_contrasena(contrasena, fila["contrasena_hash"]):
            return None
        return fila_a_personal(fila)

    def registrar_centro_medico(self, centro):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    "INSERT INTO centros_medicos (nombre, direccion) VALUES (?, ?)",
                    (centro.nombre, centro.direccion),
                )
        centro.id_centro_medico = cursor.lastrowid

    def registrar(self, personal, contrasena):
        # guarda un funcionario nuevo con su contraseña como hash
        # devuelve una lista con los mensajes de error (vacía = guardado)
        errores = []
        if not validar_run(personal.run):
            errores.append("El RUN no es válido.")
        if esta_vacio(personal.nombre):
            errores.append("El nombre es obligatorio.")
        if esta_vacio(contrasena):
            errores.append("La contraseña es obligatoria.")
        if errores:
            return errores

        if self.buscar_fila(personal.run) is not None:
            return ["Ya existe un funcionario registrado con ese RUN."]

        id_centro = None
        if isinstance(personal, PersonalCentroMedico):
            id_centro = personal.centro_medico.id_centro_medico
            if id_centro is None:
                return ["El centro médico debe estar guardado antes que su personal."]

        run_normalizado = normalizar_run(personal.run)
        try:
            with closing(obtener_conexion()) as conexion:
                with conexion:
                    cursor = conexion.execute(
                        """
                        INSERT INTO personal (
                            run, nombre, correo, telefono, cargo,
                            id_centro_medico, contrasena_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_normalizado,
                            personal.nombre,
                            personal.correo,
                            personal.telefono,
                            personal.cargo.name,  # se guarda el nombre del enum
                            id_centro,
                            generar_hash(contrasena),
                        ),
                    )
        except sqlite3.IntegrityError:
            return ["Ya existe un funcionario registrado con ese RUN."]

        personal.id_personal = cursor.lastrowid
        personal.run = run_normalizado
        return []
