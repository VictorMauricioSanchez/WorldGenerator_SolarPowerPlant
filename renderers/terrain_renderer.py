import numpy as np
import pyqtgraph.opengl as gl


class TerrainRenderer:
    """
    Convierte una matriz de elevaciones en una malla 3D.

    Convención de coordenadas locales:

    X positivo -> Este
    Y positivo -> Norte
    Z positivo -> Arriba

    El origen X-Y corresponde al centro del GeoTIFF.
    """

    TERRAIN_COLOR = (
        0.70,
        0.76,
        0.58,
        1.0,
    )

    @classmethod
    def create(
        cls,
        elevation_data: np.ndarray,
        resolution_x: float,
        resolution_y: float,
    ) -> gl.GLMeshItem:
        """
        Genera un GLMeshItem a partir de una matriz
        bidimensional de elevaciones.
        """

        if elevation_data.ndim != 2:
            raise ValueError(
                "La matriz de elevaciones debe ser bidimensional."
            )

        rows, columns = elevation_data.shape

        if rows < 2 or columns < 2:
            raise ValueError(
                "El terreno debe contener al menos "
                "2 filas y 2 columnas."
            )

        if resolution_x <= 0 or resolution_y <= 0:
            raise ValueError(
                "La resolución del terreno debe ser "
                "mayor que cero."
            )

        if np.isnan(elevation_data).any():
            raise ValueError(
                "El terreno contiene valores NoData. "
                "Será necesario tratarlos antes de renderizar."
            )

        vertices = cls._create_vertices(
            elevation_data=elevation_data,
            resolution_x=resolution_x,
            resolution_y=resolution_y,
        )

        faces = cls._create_faces(
            rows=rows,
            columns=columns,
        )

        mesh_data = gl.MeshData(
            vertexes=vertices,
            faces=faces,
        )

        terrain_item = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            shader="shaded",
            color=cls.TERRAIN_COLOR,
            drawFaces=True,
            drawEdges=False,
        )

        return terrain_item

    @staticmethod
    def _create_vertices(
        elevation_data: np.ndarray,
        resolution_x: float,
        resolution_y: float,
    ) -> np.ndarray:
        """
        Genera un vértice X,Y,Z por cada píxel del DEM.

        La fila 0 del GeoTIFF corresponde al Norte,
        mientras que Y en nuestro mundo aumenta hacia
        el Norte. Por eso se invierte el eje de filas.
        """

        rows, columns = elevation_data.shape

        column_indices = np.arange(
            columns,
            dtype=np.float32,
        )

        row_indices = np.arange(
            rows,
            dtype=np.float32,
        )

        # Coordenadas del centro de cada píxel.
        # Dimensiones físicas completas del terreno.
        terrain_width = (
            columns * resolution_x
        )

        terrain_length = (
            rows * resolution_y
        )

	# Coordenadas del centro de cada píxel.
	#
	# El origen local (0, 0) se encuentra en el centro
	# del terreno.
	#
	# X positivo -> Este
	# Y positivo -> Norte
        x_coordinates = (
            (column_indices + 0.5)
            * resolution_x
            - terrain_width / 2.0
        )

        y_coordinates = (
            (rows - row_indices - 0.5)
            * resolution_y
            - terrain_length / 2.0
        )

        x_grid, y_grid = np.meshgrid(
            x_coordinates,
            y_coordinates,
        )

        vertices = np.column_stack(
            (
                x_grid.ravel(),
                y_grid.ravel(),
                elevation_data.ravel(),
            )
        )

        return vertices.astype(
            np.float32
        )

    @staticmethod
    def _create_faces(
        rows: int,
        columns: int,
    ) -> np.ndarray:
        """
        Divide cada celda rectangular de la malla
        en dos triángulos.
        """

        row_indices = np.arange(
            rows - 1,
            dtype=np.int32,
        )

        column_indices = np.arange(
            columns - 1,
            dtype=np.int32,
        )

        column_grid, row_grid = np.meshgrid(
            column_indices,
            row_indices,
        )

        top_left = (
            row_grid * columns
            + column_grid
        ).ravel()

        top_right = top_left + 1
        bottom_left = top_left + columns
        bottom_right = bottom_left + 1

        first_triangles = np.column_stack(
            (
                top_left,
                bottom_left,
                top_right,
            )
        )

        second_triangles = np.column_stack(
            (
                top_right,
                bottom_left,
                bottom_right,
            )
        )

        faces = np.vstack(
            (
                first_triangles,
                second_triangles,
            )
        )

        return faces.astype(
            np.uint32
        )
