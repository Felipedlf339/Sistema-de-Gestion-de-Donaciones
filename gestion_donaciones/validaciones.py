"""Reglas de validación del registro de donantes (HU-01, tarea 1.1)."""

from datetime import date, datetime

from gestion_donaciones.modelos.enums import FactorRh, GrupoSanguineo


def normalizar_run(texto):
    # Deja el RUT en la forma "12345678-5" sin puntos, ni espaciosm ni ceros a la izquierda y con K mayúscula
    if texto is None:
        return None
    
    limpio = texto.replace(".", "").replace("-", "").replace(" ", "").upper()
    cuerpo = limpio[:-1].lstrip("0")

    if cuerpo == "":
        return None
    
    return cuerpo + "-" + limpio[-1]


def calcular_digito_verificador(cuerpo):
    # Algoritmo de modulo 11, se multiplica cada dígito  por 2, 3, 4, 5, 6, 7 y se vuelve a empezar en 2
    suma = 0
    multiplicador = 2

    for digito in reversed(cuerpo):
        suma = suma + int(digito) * multiplicador
        multiplicador = multiplicador + 1

        if multiplicador > 7:
            multiplicador = 2

    resultado = 11 - (suma % 11)

    if resultado == 11:
        return "0"
    if resultado == 10:
        return "K"
    
    return str(resultado)


def validar_run(texto):
    run = normalizar_run(texto)
    
    if run is None:
        return False

    cuerpo, digito = run.split("-")
    
    if not cuerpo.isdigit() or len(cuerpo) < 7 or len(cuerpo) > 8:
        return False
    if digito != "K" and not digito.isdigit():
        return False
    
    return calcular_digito_verificador(cuerpo) == digito


def esta_vacio(valor):
    return valor is None or str(valor).strip() == ""


def validar_correo(correo):
    correo = correo.strip()

    if " " in correo or correo.count("@") != 1:
        return False
    
    usuario, dominio = correo.split("@")
    
    if usuario == "" or "." not in dominio:
        return False
    if dominio.startswith(".") or dominio.endswith("."):
        return False
    
    return True


def validar_telefono(telefono):
    numero = telefono.replace(" ", "").replace("-", "").replace("+", "")
    
    if not numero.isdigit():
        return False
    if len(numero) == 9:
        return True
    
    return len(numero) == 11 and numero.startswith("56")


def validar_donante(donante):
    # Revisa los datos del donante antes de guardarlo.
    # Devuelve una lista con los mensajes de error; si está vacía, los datos son válidos.
    errores = []

    if esta_vacio(donante.run):
        errores.append("El RUN es obligatorio.")
    elif not validar_run(donante.run):
        errores.append("El RUN no es válido.")

    if esta_vacio(donante.nombre):
        errores.append("El nombre es obligatorio.")

    if donante.grupo_sanguineo is None:
        errores.append("El grupo sanguíneo es obligatorio.")
    elif not isinstance(donante.grupo_sanguineo, GrupoSanguineo):
        errores.append("El grupo sanguíneo no es válido.")

    if donante.factor_rh is None:
        errores.append("El factor Rh es obligatorio.")
    elif not isinstance(donante.factor_rh, FactorRh):
        errores.append("El factor Rh no es válido.")

    sin_correo = esta_vacio(donante.correo)
    sin_telefono = esta_vacio(donante.telefono)
    
    if sin_correo and sin_telefono:
        errores.append("Debe ingresar al menos un contacto (correo o teléfono).")
    if not sin_correo and not validar_correo(donante.correo):
        errores.append("El correo no tiene un formato válido.")
    if not sin_telefono and not validar_telefono(donante.telefono):
        errores.append("El teléfono no tiene un formato válido.")

    
    if donante.peso_kg is not None:
        if not isinstance(donante.peso_kg, (int, float)) or donante.peso_kg <= 0:
            errores.append("El peso debe ser un número mayor que 0.")

    if donante.fecha_nacimiento is not None:
        if not isinstance(donante.fecha_nacimiento, date) or isinstance(donante.fecha_nacimiento, datetime):
            errores.append("La fecha de nacimiento no es válida.")
        elif donante.fecha_nacimiento > date.today():
            errores.append("La fecha de nacimiento no puede ser futura.")

    return errores
