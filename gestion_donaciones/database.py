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

def migrar_personal_a_id_entero(conexion):
    """
    Las bases antiguas tenían id_personal TEXT PRIMARY KEY, que en SQLite deja el id
    en NULL. Reconstruye la tabla con id entero autoincremental y conserva los datos.
    """
    columnas = {fila["name"]: fila["type"] for fila in conexion.execute("PRAGMA table_info(personal)")}
    if not columnas or columnas.get("id_personal", "").upper() == "INTEGER":
        return  # tabla nueva o ya migrada

    conexion.execute("DROP TABLE IF EXISTS personal_nueva")
    conexion.execute("""
        CREATE TABLE personal_nueva (
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
    conexion.execute("""
        INSERT INTO personal_nueva (run, nombre, correo, telefono, cargo,
                                    id_centro_medico, contrasena_hash)
        SELECT run, nombre, correo, telefono, cargo, id_centro_medico, contrasena_hash
        FROM personal
        WHERE contrasena_hash IS NOT NULL
        ORDER BY rowid
    """)
    conexion.execute("DROP TABLE personal")
    conexion.execute("ALTER TABLE personal_nueva RENAME TO personal")

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
            migrar_personal_a_id_entero(conexion)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS donaciones (
                    id_donacion INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_donante INTEGER NOT NULL REFERENCES donantes(id_donante),
                    tipo_donacion TEXT NOT NULL,
                    fecha_hora TEXT NOT NULL
                )
            """)
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
                    id_personal_receptor INTEGER REFERENCES personal(id_personal),
                    estado TEXT NOT NULL CHECK (estado IN ('EN_TRANSITO', 'ENTREGADO'))
                )
            """)
            # persona del centro médico que confirmó la recepción (HU-11)
            agregar_columna_si_falta(conexion, "despachos", "id_personal_receptor",
                                     "INTEGER REFERENCES personal(id_personal)")


# Re-exportar para retrocompatibilidad
from gestion_donaciones.reservas import reservar_unidades_despacho
