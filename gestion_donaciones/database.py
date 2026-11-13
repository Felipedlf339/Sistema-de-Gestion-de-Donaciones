import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).resolve().parent / "donaciones.db"

def obtener_conexion() -> sqlite3.Connection:
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row 
    return conexion

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
                CREATE TABLE IF NOT EXISTS personal (
                    id_personal TEXT PRIMARY KEY,
                    run TEXT UNIQUE NOT NULL,
                    nombre TEXT NOT NULL,
                    correo TEXT,
                    telefono TEXT,
                    cargo TEXT NOT NULL
                )
            """)