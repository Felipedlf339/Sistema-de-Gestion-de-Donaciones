import sqlite3
from pathlib import Path
from contextlib import closing
from gestion_donaciones.modelos.enums import EstadoUnidad

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
                    id_despacho INTEGER REFERENCES despachos(id_despacho),
                    tipo_componente TEXT NOT NULL,
                    tipo_sangre TEXT NOT NULL,
                    fecha_extraccion TEXT NOT NULL,
                    fecha_caducidad TEXT NOT NULL,
                    estado TEXT NOT NULL
                )
            """)
            # una sola columna y sin NOT NULL: cada unidad pertenece a lo sumo a un despacho
            # (NULL mientras no se haya despachado)
            agregar_columna_si_falta(conexion, "unidades", "id_despacho",
                                     "INTEGER REFERENCES despachos(id_despacho)")
            conexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_unidades_id_despacho ON unidades(id_despacho)"
            )
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
            # id_encargado es el personal (encargado de inventario) que prepara el despacho
            # fecha_recepcion queda NULL hasta que el centro médico recibe las unidades
            # estado guarda el valor de EstadoDespacho (EN_TRANSITO o ENTREGADO)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS despachos (
                    id_despacho INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_solicitud INTEGER NOT NULL REFERENCES solicitudes(id_solicitud),
                    id_encargado INTEGER NOT NULL REFERENCES personal(id_personal),
                    fecha_despacho TEXT NOT NULL,
                    fecha_recepcion TEXT,
                    estado TEXT NOT NULL CHECK (estado IN ('EN_TRANSITO', 'ENTREGADO'))
                )
            """)
    
def reservar_unidades_despacho(
    conexion: sqlite3.Connection,
    id_despacho: int,
    ids_unidades: list[int],
) -> bool:
    """
    Si alguna unidad no existe o ya no está disponible, deshace toda la operación
    y retorna False. Si todas se reservan, confirma y retorna True.
    """
    if not ids_unidades:
        return False
    if len(set(ids_unidades)) != len(ids_unidades):
        return False

    cursor = conexion.cursor()
    try:
        if not conexion.in_transaction:
            cursor.execute("BEGIN IMMEDIATE")

        for id_unidad in ids_unidades:
            cursor.execute(
                """
                UPDATE unidades
                SET estado = ?,
                    id_despacho = ?
                WHERE id_unidad = ?
                  AND estado = ?
                """,
                (
                    EstadoUnidad.RESERVADA.value,
                    id_despacho,
                    id_unidad,
                    EstadoUnidad.DISPONIBLE.value,
                ),
            )

            if cursor.rowcount == 0:
                conexion.rollback()
                return False

        conexion.commit()
        return True

    except sqlite3.Error:
        if conexion.in_transaction:
            conexion.rollback()
        raise