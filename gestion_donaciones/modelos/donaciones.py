from gestion_donaciones.modelos import Donacion, TipoDonacion


class DonanteNoApto(Exception):
    pass


def registrar_donacion(donante, tipo_donacion):

    if donante is None:
        raise ValueError("Debe proporcionar un donante válido.")

    if not isinstance(tipo_donacion, TipoDonacion):
        raise ValueError("El tipo de donación debe ser SANGRE o PLAQUETAS.")

    if not donante.es_apto():
        raise DonanteNoApto("El donante no está Apto, no se puede registrar la donación.")

    id_donante = getattr(donante, 'id_donante', getattr(donante, 'run', None))

    donacion = Donacion(id_donante=id_donante, tipo_donacion=tipo_donacion)

    return donacion