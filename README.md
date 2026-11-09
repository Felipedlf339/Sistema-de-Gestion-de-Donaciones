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
El servidor quedará corriendo en `[http://127.0.0.1:8000](http://127.0.0.1:8000)`.