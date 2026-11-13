from gestion_donaciones.database import obtener_conexion

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
        
    conexion.commit()
    conexion.close()
    print("¡Los 3 donantes de ejemplo y las unidades fueron inyectados con éxito!")

if __name__ == "__main__":
    insertar_datos_prueba()