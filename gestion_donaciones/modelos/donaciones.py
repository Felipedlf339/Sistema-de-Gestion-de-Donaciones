from gestion_donaciones.modelos import Donacion, TipoDonacion
from gestion_donaciones.modelos.generacion_unidades import generar_unidad

class DonanteNoApto(Exception):
    pass

class DonanteNoEncontrado(Exception):
    pass


def registrar_donacion(donante, tipo_donacion):

    if donante is None:
        raise ValueError("Debe proporcionar un donante válido.")

    if not isinstance(tipo_donacion, TipoDonacion):
        raise ValueError("La donación debe ser de sangre o plaquetas.")

    if not donante.es_apto():
        raise DonanteNoApto("El donante no es Apto, la donación no pudo ser registrada.")

    id_donante = getattr(donante, 'id_donante', getattr(donante, 'run', None))

    donacion = Donacion(id_donante=id_donante, tipo_donacion=tipo_donacion)
    unidad = generar_unidad(donacion, donante)

    return donacion, unidad