# Bloqueo de Unidades en SQLite HU-10

## Objetivo
Evitar reservas duplicadas sobre una misma unidad de sangre mediante control de concurrencia atómico en SQLite, definiendo el contrato de integración para el módulo de despacho.

## Estrategia de Concurrencia

1. **Bloqueo inmediato de escritura:**
   * Al iniciar la reserva, SQLite adquiere un bloqueo reservado.
   * Si dos solicitudes llegan al mismo tiempo, SQLite serializa el acceso: la primera ejecuta la transacción y la segunda espera hasta que la primera haga `COMMIT` o `ROLLBACK`.
2. **Actualización condicional atómica:**
   * No se consulta la disponibilidad antes de modificar para evitar condiciones de carrera entre la lectura y la escritura.
   * Se ejecuta directamente un `UPDATE` exigiendo que el estado siga siendo `'Disponible'`.
3. **Validación por filas afectadas:**
   * **`rowcount == 1`:** Reserva confirmada de forma exclusiva.
   * **`rowcount == 0`:** La unidad no existe o ya fue tomada milisegundos antes. Se ejecuta `ROLLBACK` y se retorna `False`.

## Contrato para Despacho

### Apertura de conexión recomendada
```python
conexion = sqlite3.connect("donaciones.db", timeout=10.0, isolation_level=None)
```

### Función de referencia
```python
import sqlite3

def reservar_unidad(conexion: sqlite3.Connection, id_unidad: int, id_centro_destino: int) -> bool:
    """
    Reserva una unidad de forma atómica.
    Retorna True si estaba 'Disponible' y quedó reservada, False si ya fue tomada.
    """
    cursor = conexion.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            UPDATE unidades_sangre
            SET estado = 'Reservada',
                centro_destino_id = ?
            WHERE id_unidad = ?
              AND estado = 'Disponible'
            """,
            (id_centro_destino, id_unidad),
        )

        if cursor.rowcount == 0:
            conexion.rollback()
            return False

        conexion.commit()
        return True

    except sqlite3.Error:
        conexion.rollback()
        raise
```

### Manejo de respuesta en FastAPI
* Si `reservar_unidad(...)` devuelve `False`, el endpoint de despacho debe responder con estado HTTP **`409 Conflict`** indicando que la unidad ya fue reservada por otro centro.