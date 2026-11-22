# Sistema-de-Gestion-de-Donaciones

## Configuraciones del entorno

Pasos para ejecutar el servidor del proyecto.

**1. Crear el entorno virtual:**
```bash
python -m venv venv
```

**2. Activar el entorno virtual:**
- En Windows (Git Bash):
  ```bash
  source venv/Scripts/activate
  ```
- En Linux / Mac:
  ```bash
  source venv/bin/activate
  ```

**3. Instalar las dependencias:**
```bash
pip install -r requirements.txt
```

**4. Levantar el servidor:**
```bash
uvicorn main:app --reload
```
El servidor quedará corriendo en [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Datos y usuarios de prueba

Para cargar donantes, unidades y usuarios de ejemplo:

```bash
python poblar.py
```

Al abrir [http://127.0.0.1:8000](http://127.0.0.1:8000) se pide iniciar sesión. Usuarios de prueba (RUN / contraseña):

| RUN | Contraseña | Cargo |
|-----|------------|-------|
| 15.555.555-6 | donacion123 | Personal de atención al donante |
| 16.666.666-K | inventario123 | Encargado de inventario |
| 18.888.888-7 | hospital123 | Responsable de recepción (Hospital Regional de Concepción) |

La sesión se guarda en una cookie firmada. Fuera de desarrollo, definir la variable de entorno
`CLAVE_SESION` con una clave secreta propia.

## Pruebas

Las pruebas usan `unittest`. Desde la raíz del proyecto:

```bash
python -m unittest -v
```
