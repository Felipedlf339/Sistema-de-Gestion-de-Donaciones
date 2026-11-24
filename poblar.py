from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import (
    CargoMedico,
    CargoPersonal,
    CentroMedico,
    PersonalCentroDonacion,
    PersonalCentroMedico,
)
from gestion_donaciones.registro_personal import RegistroPersonal

def insertar_personal_prueba():
    # usuarios para probar el inicio de sesión (HU-07); si ya existen no se duplican
    registro = RegistroPersonal()

    if registro.buscar_por_run("18.888.888-7") is None:
        centro = CentroMedico("Hospital Regional de Concepción", "San Martín 1436, Concepción")
        registro.registrar_centro_medico(centro)
        registro.registrar(
            PersonalCentroMedico("18.888.888-7", "Camila Rojas", CargoMedico.RESPONSABLE_RECEPCION, centro),
            "hospital123",
        )

    registro.registrar(
        PersonalCentroDonacion("15.555.555-6", "Isaac Castro", None, CargoPersonal.ATENCION_DONANTE),
        "donacion123",
    )
    registro.registrar(
        PersonalCentroDonacion("16.666.666-K", "Cristobal Araya", None, CargoPersonal.ENCARGADO_INVENTARIO),
        "inventario123",
    )
    print("Usuarios de prueba (RUN / contraseña):")
    print("  15.555.555-6 / donacion123   -> Personal de atención al donante")
    print("  16.666.666-K / inventario123 -> Encargado de inventario")
    print("  18.888.888-7 / hospital123   -> Responsable de recepción (centro médico)")


def insertar_datos_prueba():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    donantes = [
        ("12345678-5", "Javiera Aravena Gutierrez", "A", "+", "APTO"),
        ("11111111-1", "Francisca Hidalgo", "O", "-", "DIFERIDO_TEMPORAL"),
        ("7654321-6", "Felipe de la Fuente", "AB", "+", "RECHAZADO_PERMANENTE")
    ]

    for run, nombre, grupo, rh, estado in donantes:
        cursor.execute("""
            INSERT OR REPLACE INTO donantes (run, nombre, grupo_sanguineo, factor_rh, estado_elegibilidad)
            VALUES (?, ?, ?, ?, ?)
        """, (run, nombre, grupo, rh, estado))
    
    # Insertamos 5 unidades de prueba (4 disponibles, 1 usada para verificar que se oculta)
    unidades = [
        (1, 'Sangre', 'A+', '2026-11-10', '2026-12-22', 'Disponible'),
        (2, 'Plaquetas', 'O+', '2026-11-12', '2026-11-17', 'Disponible'),
        (3, 'Plasma', 'O-', '2026-11-01', '2027-11-01', 'Disponible'),
        (4, 'Sangre', 'B+', '2026-10-15', '2026-11-26', 'Disponible'),
        (5, 'Sangre', 'AB+', '2026-11-11', '2026-12-23', 'Usado')
    ]

    cursor.executemany("""
            INSERT OR IGNORE INTO unidades (id_donacion, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        """, unidades)

    if cursor.execute("SELECT COUNT(*) FROM centros_medicos").fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO centros_medicos (nombre, direccion) VALUES (?, ?)",
            [
                ("Hospital Regional de Concepción", "San Martín 1436"),
                ("Clínica Biobío", "Av. Jorge Alessandri 3515"),
            ],
        )
    if cursor.execute("SELECT COUNT(*) FROM solicitudes").fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO solicitudes
                (id_centro_medico, tipo_hemoderivado, grupo_sanguineo, cantidad, fecha_solicitud, estado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (2, 'Plaquetas', 'O+', 2, '2026-11-20T14:30:00', 'PENDIENTE'),
                (1, 'Sangre', 'A+', 3, '2026-11-18T09:15:00', 'PENDIENTE'),
                (1, 'Plasma', 'O-', 1, '2026-11-15T16:00:00', 'ATENDIDA'),
                (2, 'Sangre', 'B+', 4, '2026-11-19T11:45:00', 'PENDIENTE'),
            ],
        )
        
    conexion.commit()
    conexion.close()
    print("¡Los 3 donantes de ejemplo y las unidades fueron inyectados con éxito!")

if __name__ == "__main__":
    inicializar_bd()
    insertar_datos_prueba()
    insertar_personal_prueba()
