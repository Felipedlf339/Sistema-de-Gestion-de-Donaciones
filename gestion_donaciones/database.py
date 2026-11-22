import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).resolve().parent / "donaciones.db"


def obtener_conexion() -> sqlite3.Connection:
    conexion = sqlite3.connect(DB_PATH, timeout=10.0)
    conexion.row_factory = sqlite3.Row
    return conexion


def agregar_columna_si_falta(conexion, tabla, columna, definicion):
    columnas = [fila["name"] for fila in conexion.execute(f"PRAGMA table_info({tabla})")]
    if columna not in columnas:
        conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def inicializar_bd() -> None:
    with closing(obtener_conexion()) as conexion:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS donantes (
                    id_donante INTEGER PRIMARY KEY AUTOINCREMENT,
                    run TEXT UNIQUE NOT NULL,
                    nombre TEXT NOT NULL,
                    correo TEXT,
                    telefono TEXT,
                    fecha_nacimiento TEXT,
                    peso_kg REAL,
                    grupo_sanguineo TEXT NOT NULL,
                    factor_rh TEXT NOT NULL,
                    fecha_habilitacion TEXT,
                    fecha_ultima_donacion TEXT,
                    estado_elegibilidad TEXT,
                    motivo TEXT
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS centros_medicos (
                    id_centro_medico INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    direccion TEXT
                )
            """)
            # cargo guarda el nombre del enum (ej. ATENCION_DONANTE): CargoPersonal si
            # id_centro_medico es NULL, CargoMedico si tiene centro médico
            # contrasena_hash guarda "sal$hash" (ver credenciales.py), nunca la contraseña
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS personal (
                    id_personal INTEGER PRIMARY KEY AUTOINCREMENT,
                    run TEXT UNIQUE NOT NULL,
                    nombre TEXT NOT NULL,
                    correo TEXT,
                    telefono TEXT,
                    cargo TEXT NOT NULL,
                    id_centro_medico INTEGER REFERENCES centros_medicos(id_centro_medico),
                    contrasena_hash TEXT NOT NULL
                )
            """)
            # las bases creadas antes de HU-07 tienen la tabla personal sin estas columnas
            agregar_columna_si_falta(conexion, "personal", "id_centro_medico",
                                     "INTEGER REFERENCES centros_medicos(id_centro_medico)")
            agregar_columna_si_falta(conexion, "personal", "contrasena_hash", "TEXT")
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS unidades (
                    id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_donacion INTEGER,
                    id_despacho INTEGER,
                    tipo_componente TEXT NOT NULL,
                    tipo_sangre TEXT NOT NULL,
                    fecha_extraccion TEXT NOT NULL,
                    fecha_caducidad TEXT NOT NULL,
                    estado TEXT NOT NULL
                )
            """)
            agregar_columna_si_falta(conexion, "unidades", "id_despacho", "INTEGER")
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS solicitudes (
                    id_solicitud INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_centro_medico INTEGER NOT NULL,
                    tipo_hemoderivado TEXT NOT NULL,
                    grupo_sanguineo TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    fecha_solicitud TEXT NOT NULL,
                    estado TEXT NOT NULL
                )
            """)
