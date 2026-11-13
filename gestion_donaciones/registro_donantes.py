"""Registro de donantes en SQLite."""

import sqlite3
from contextlib import closing

from gestion_donaciones.validaciones import normalizar_run, validar_donante
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.enums import EstadoElegibilidad, GrupoSanguineo, FactorRh
from gestion_donaciones.database import obtener_conexion


class RegistroDonantes:
    """Gestiona la persistencia de donantes en SQLite."""

    def buscar_por_run(self, run: str) -> Donante | None:
        # Devuelve el donante con ese RUN, o None si no está registrado
        clave = normalizar_run(run)

        if clave is None:
            return None

        with closing(obtener_conexion()) as conexion:
            fila = conexion.execute(
                "SELECT * FROM donantes WHERE run = ?", (clave,)
            ).fetchone()

        if fila is None:
            return None

        # Se reconstruye el objeto Donante desde la fila de SQLite
        donante = Donante(
            run=fila["run"],
            nombre=fila["nombre"],
            grupo_sanguineo=GrupoSanguineo(fila["grupo_sanguineo"]),
            factor_rh=FactorRh(fila["factor_rh"]),
            correo=fila["correo"],
            telefono=fila["telefono"],
        )
        donante.id_donante = fila["id_donante"]
        donante.estado_elegibilidad = EstadoElegibilidad(fila["estado_elegibilidad"])
        donante.motivo = fila["motivo"]
        return donante

    def registrar(self, donante: Donante) -> list[str]:
        # valida y guarda un donante nuevo
        # devuelve una lista con los mensajes de error

        # si el RUN ya existe no se guarda de nuevo
        # quien llama puede usar buscar_por_run() para mostrar el donante registrado.
        if self.buscar_por_run(donante.run) is not None:
            return ["Ya existe un donante registrado con ese RUN."]

        errores = validar_donante(donante)
        if errores:
            return errores

        run_normalizado = normalizar_run(donante.run)
        if run_normalizado is None:
            return ["El RUN no es válido."]
        
        if donante.estado_elegibilidad is None:
            donante.estado_elegibilidad = EstadoElegibilidad.APTO

        try:
            with closing(obtener_conexion()) as conexion:
                with conexion:
                    cursor = conexion.execute(
                        """
                        INSERT INTO donantes (
                            run, nombre, correo, telefono, grupo_sanguineo,
                            factor_rh, estado_elegibilidad, motivo
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_normalizado,
                            donante.nombre,
                            donante.correo,
                            donante.telefono,
                            donante.grupo_sanguineo.value,
                            donante.factor_rh.value,
                            donante.estado_elegibilidad.value,
                            getattr(donante, "motivo", None),
                        ),
                    )
                    id_nuevo = cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e).upper(): # proteccion contra duplicados
                return ["Ya existe un donante registrado con ese RUN."]
            raise

        donante.id_donante = id_nuevo
        donante.run = run_normalizado

        return []
    
    def actualizar_elegibilidad(
        self, run: str, nuevo_estado: EstadoElegibilidad, motivo: str | None = None
    ) -> bool:
        clave = normalizar_run(run)
        if clave is None:
            return False

        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    UPDATE donantes
                    SET estado_elegibilidad = ?, motivo = ?
                    WHERE run = ?
                    """,
                    (nuevo_estado.value, motivo, clave),
                )
                return cursor.rowcount > 0
