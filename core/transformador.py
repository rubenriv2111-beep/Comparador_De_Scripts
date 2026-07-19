from pyproj import Transformer

class TransformadorUTM:
    def __init__(self, epsg_code):
        self.trans = Transformer.from_crs(f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)
        self.cache = {}

    def transformar_lote(self, puntos):
        resultado = []
        for x, y in puntos:
            key = (round(x, 6), round(y, 6))
            if key in self.cache:
                lon, lat = self.cache[key]
            else:
                lon, lat = self.trans.transform(x, y)
                self.cache[key] = (lon, lat)
            resultado.append((lon, lat))
        return resultado