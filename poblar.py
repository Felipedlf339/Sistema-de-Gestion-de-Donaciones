from gestion_donaciones.database import obtener_conexion

def insertar_datos_prueba():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    # Insertamos 5 unidades de prueba (4 disponibles, 1 usada para verificar que se oculta)
    unidades = [
        (1, 'Sangre', 'A+', '2026-11-10', '2026-12-22', 'Disponible'),
        (2, 'Plaquetas', 'O+', '2026-11-12', '2026-11-17', 'Disponible'),
        (3, 'Plasma', 'O-', '2026-11-01', '2027-11-01', 'Disponible'),
        (4, 'Sangre', 'B+', '2026-10-15', '2026-11-26', 'Disponible'),
        (5, 'Sangre', 'AB+', '2026-11-11', '2026-12-23', 'Usado')
    ]
    
    cursor.executemany("""
        INSERT INTO unidades (id_donacion, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
        VALUES (?, ?, ?, ?, ?, ?)
    """, unidades)
    
    conexion.commit()
    conexion.close()
    print("¡Datos inyectados con éxito en la base de datos!")

if __name__ == "__main__":
    insertar_datos_prueba()