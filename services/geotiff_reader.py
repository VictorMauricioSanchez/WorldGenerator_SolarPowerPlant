from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio


@dataclass
class GeoTiffInfo:
    path: Path
    crs: str
    epsg: int | None

    width: int
    height: int

    resolution_x: float
    resolution_y: float

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    nodata: float | None

    min_elevation: float
    max_elevation: float


class GeoTiffReader:
    """
    Lee y valida archivos GeoTIFF utilizados como
    modelos digitales del terreno.
    """

    @staticmethod
    def read_info(
        file_path: str | Path,
    ) -> GeoTiffInfo:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        if path.suffix.lower() not in {
            ".tif",
            ".tiff",
        }:
            raise ValueError(
                "El archivo debe ser un GeoTIFF "
                "con extensión .tif o .tiff."
            )

        with rasterio.open(path) as dataset:
            if dataset.count != 1:
                raise ValueError(
                    "El GeoTIFF debe contener una sola "
                    "banda de elevación."
                )

            elevation_data = dataset.read(
                1,
                masked=True,
            )

            if elevation_data.count() == 0:
                raise ValueError(
                    "El GeoTIFF no contiene valores "
                    "de elevación válidos."
                )

            min_elevation = float(
                elevation_data.min()
            )

            max_elevation = float(
                elevation_data.max()
            )

            bounds = dataset.bounds
            resolution_x, resolution_y = (
                dataset.res
            )

            epsg = None

            if dataset.crs is not None:
                epsg = dataset.crs.to_epsg()

            crs_text = (
                dataset.crs.to_string()
                if dataset.crs is not None
                else "Desconocido"
            )

            return GeoTiffInfo(
                path=path.resolve(),
                crs=crs_text,
                epsg=epsg,
                width=dataset.width,
                height=dataset.height,
                resolution_x=float(
                    resolution_x
                ),
                resolution_y=float(
                    resolution_y
                ),
                min_x=float(bounds.left),
                min_y=float(bounds.bottom),
                max_x=float(bounds.right),
                max_y=float(bounds.top),
                nodata=dataset.nodata,
                min_elevation=min_elevation,
                max_elevation=max_elevation,
            )
    @staticmethod
    def read_elevation_data(
        file_path: str | Path,
    ) -> np.ndarray:
        """
        Lee la banda de elevación del GeoTIFF.

        Los valores NoData se convierten en NaN.

        La matriz mantiene el orden original del ráster:
        la primera fila corresponde al norte del terreno
        y la última fila al sur.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        with rasterio.open(path) as dataset:
            if dataset.count != 1:
                raise ValueError(
                    "El GeoTIFF debe contener una sola "
                    "banda de elevación."
                )

            elevation_data = dataset.read(
                1,
                masked=True,
            )

            elevation_data = elevation_data.filled(
                np.nan
            )

            return elevation_data.astype(
                np.float32
            )
    @staticmethod
    def read_local_elevation_data(
        file_path: str | Path,
    ) -> tuple[np.ndarray, float]:
        """
        Convierte las elevaciones absolutas del MDT
        en alturas locales para Gazebo.

        La elevación mínima válida se toma como Z = 0.

        Retorna:
            local_data:
                Matriz de alturas relativas en metros.

            elevation_origin:
                Elevación absoluta utilizada como origen Z.
        """

        elevation_data = (
            GeoTiffReader.read_elevation_data(
                file_path
            )
        )

        if np.all(np.isnan(elevation_data)):
            raise ValueError(
                "El GeoTIFF no contiene elevaciones válidas."
            )

        elevation_origin = float(
            np.nanmin(elevation_data)
        )

        local_data = (
            elevation_data - elevation_origin
        )

        return (
            local_data.astype(np.float32),
            elevation_origin,
        )

    @staticmethod
    def utm_to_local_coordinates(
        file_path: str | Path,
        easting: float,
        northing: float,
    ) -> tuple[float, float, float]:
        """
        Convierte una coordenada UTM del terreno
        a coordenadas locales X, Y, Z.

        Convención local:

        X positivo -> Este
        Y positivo -> Norte
        Z positivo -> Arriba

        El origen X-Y está en el centro del GeoTIFF.
        El origen Z corresponde a la elevación mínima
        válida del DEM.

        Retorna:
            (x, y, z) en metros.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        with rasterio.open(path) as dataset:
            bounds = dataset.bounds

            # ---------------------------------------------
            # Comprobar que la coordenada pertenece
            # al área cubierta por el GeoTIFF.
            # ---------------------------------------------
            if not (
                bounds.left <= easting <= bounds.right
                and bounds.bottom <= northing <= bounds.top
            ):
                raise ValueError(
                    "La coordenada UTM se encuentra "
                    "fuera de los límites del terreno."
                )

            # ---------------------------------------------
            # Centro UTM del terreno.
            # Este será nuestro origen local X-Y.
            # ---------------------------------------------
            center_easting = (
                bounds.left + bounds.right
            ) / 2.0

            center_northing = (
                bounds.bottom + bounds.top
            ) / 2.0

            local_x = (
                float(easting)
                - center_easting
            )

            local_y = (
                float(northing)
                - center_northing
            )

            # ---------------------------------------------
            # Convertir coordenada geográfica a
            # fila/columna del ráster.
            # ---------------------------------------------
            row, column = dataset.index(
                easting,
                northing,
            )

            if not (
                0 <= row < dataset.height
                and 0 <= column < dataset.width
            ):
                raise ValueError(
                    "La coordenada corresponde al borde "
                    "exterior del GeoTIFF y no a un píxel "
                    "válido del terreno."
                )

            elevation_data = dataset.read(
                1,
                masked=True,
            )

            if elevation_data.count() == 0:
                raise ValueError(
                    "El GeoTIFF no contiene "
                    "elevaciones válidas."
                )

            elevation = elevation_data[
                row,
                column,
            ]

            if np.ma.is_masked(elevation):
                raise ValueError(
                    "La coordenada UTM corresponde "
                    "a una zona NoData del terreno."
                )

            # ---------------------------------------------
            # El mismo origen Z utilizado actualmente
            # por read_local_elevation_data().
            # ---------------------------------------------
            elevation_origin = float(
                elevation_data.min()
            )

            local_z = (
                float(elevation)
                - elevation_origin
            )

            return (
                float(local_x),
                float(local_y),
                float(local_z),
            )
    @staticmethod
    def utm_points_to_local_coordinates(
        file_path: str | Path,
        points: list[tuple[float, float]],
    ) -> list[tuple[float, float, float]]:
        """
        Convierte múltiples coordenadas UTM a coordenadas
        locales X, Y, Z del terreno.

        Cada elemento de points debe tener el formato:

            (easting, northing)

        El GeoTIFF se abre una sola vez para procesar
        todos los puntos eficientemente.

        Retorna una lista:

            [(x, y, z), ...]
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        if not points:
            return []

        local_points = []

        with rasterio.open(path) as dataset:
            bounds = dataset.bounds

            center_easting = (
                bounds.left + bounds.right
            ) / 2.0

            center_northing = (
                bounds.bottom + bounds.top
            ) / 2.0

            elevation_data = dataset.read(
                1,
                masked=True,
            )

            if elevation_data.count() == 0:
                raise ValueError(
                    "El GeoTIFF no contiene "
                    "elevaciones válidas."
                )

            elevation_origin = float(
                elevation_data.min()
            )

            for index, (
                easting,
                northing,
            ) in enumerate(
                points,
                start=1,
            ):
                easting = float(easting)
                northing = float(northing)

                # -----------------------------------------
                # Comprobar límites del terreno.
                # -----------------------------------------
                if not (
                    bounds.left
                    <= easting
                    <= bounds.right
                    and bounds.bottom
                    <= northing
                    <= bounds.top
                ):
                    raise ValueError(
                        f"El punto {index} está fuera "
                        f"de los límites del terreno: "
                        f"E={easting}, N={northing}."
                    )

                # -----------------------------------------
                # Coordenadas locales X-Y.
                # -----------------------------------------
                local_x = (
                    easting - center_easting
                )

                local_y = (
                    northing - center_northing
                )

                # -----------------------------------------
                # Localizar píxel correspondiente.
                # -----------------------------------------
                row, column = dataset.index(
                    easting,
                    northing,
                )

                if not (
                    0 <= row < dataset.height
                    and 0 <= column < dataset.width
                ):
                    raise ValueError(
                        f"El punto {index} no corresponde "
                        f"a un píxel válido del DEM."
                    )

                elevation = elevation_data[
                    row,
                    column,
                ]

                if np.ma.is_masked(elevation):
                    raise ValueError(
                        f"El punto {index} corresponde "
                        f"a una zona NoData del DEM."
                    )

                # -----------------------------------------
                # Misma referencia Z que el terreno.
                # -----------------------------------------
                local_z = (
                    float(elevation)
                    - elevation_origin
                )

                local_points.append(
                    (
                        float(local_x),
                        float(local_y),
                        float(local_z),
                    )
                )

        return local_points
