"""Contraseñas del personal: se guardan como hash, nunca en texto plano"""

import hashlib
import hmac
import secrets

ITERACIONES = 200000


def calcular_hash(contrasena, sal):
    resultado = hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), bytes.fromhex(sal), ITERACIONES
    )
    return resultado.hex()


def generar_hash(contrasena):
    # devuelve "sal$hash"; la sal es aleatoria, así dos contraseñas iguales dan hashes distintos
    sal = secrets.token_hex(16)
    return sal + "$" + calcular_hash(contrasena, sal)


def verificar_contrasena(contrasena, hash_guardado):
    # True si la contraseña corresponde al hash guardado
    if not contrasena or not hash_guardado or "$" not in hash_guardado:
        return False

    sal, hash_esperado = hash_guardado.split("$", 1)
    try:
        hash_ingresado = calcular_hash(contrasena, sal)
    except ValueError:
        return False  # sal mal formada

    # compare_digest compara en tiempo constante
    return hmac.compare_digest(hash_ingresado, hash_esperado)
