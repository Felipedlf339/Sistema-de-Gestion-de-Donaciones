from gestion_donaciones.modelos.enums import EstadoUnidad


class Unidad:

    def __init__(self, id_donacion, tipo_componente, tipo_sangre,
                 fecha_extraccion, fecha_caducidad):
        self.id_unidad = None                           
        self.id_donacion = id_donacion                  
        self.tipo_componente = tipo_componente         
        self.tipo_sangre = tipo_sangre                 
        self.fecha_extraccion = fecha_extraccion        
        self.fecha_caducidad = fecha_caducidad        
        self.estado = EstadoUnidad.DISPONIBLE