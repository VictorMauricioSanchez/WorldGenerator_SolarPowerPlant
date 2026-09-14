import numpy as np
import pyqtgraph.opengl as gl


class HomeRenderer:
    """
    Representación gráfica simple del punto Home.
    """

    @classmethod
    def create(cls, x: float, y: float, z: float) -> tuple[object, ...]:
        items = []

        body = cls._create_body(x, y, z)
        roof = cls._create_roof(x, y, z)

        items.append(body)
        items.append(roof)

        return tuple(items)

    @staticmethod
    def _create_body(x: float, y: float, z: float) -> gl.GLMeshItem:
        width = 2.0
        depth = 2.0
        height = 1.6

        half_x = width / 2.0
        half_y = depth / 2.0

        vertices = np.array([
            [x - half_x, y - half_y, z],
            [x + half_x, y - half_y, z],
            [x + half_x, y + half_y, z],
            [x - half_x, y + half_y, z],
            [x - half_x, y - half_y, z + height],
            [x + half_x, y - half_y, z + height],
            [x + half_x, y + half_y, z + height],
            [x - half_x, y + half_y, z + height],
        ], dtype=float)

        faces = np.array([
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ], dtype=int)

        mesh_data = gl.MeshData(vertexes=vertices, faces=faces)

        return gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            shader="shaded",
            color=(0.88, 0.80, 0.62, 1.0),
            drawFaces=True,
            drawEdges=True,
        )

    @staticmethod
    def _create_roof(x: float, y: float, z: float) -> gl.GLMeshItem:
        width = 2.4
        depth = 2.4
        body_height = 1.6
        roof_height = 0.9

        half_x = width / 2.0
        half_y = depth / 2.0
        base_z = z + body_height
        apex_z = base_z + roof_height

        vertices = np.array([
            [x - half_x, y - half_y, base_z],
            [x + half_x, y - half_y, base_z],
            [x + half_x, y + half_y, base_z],
            [x - half_x, y + half_y, base_z],
            [x, y, apex_z],
        ], dtype=float)

        faces = np.array([
            [0, 1, 4],
            [1, 2, 4],
            [2, 3, 4],
            [3, 0, 4],
            [0, 3, 2],
            [0, 2, 1],
        ], dtype=int)

        mesh_data = gl.MeshData(vertexes=vertices, faces=faces)

        return gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            shader="shaded",
            color=(0.55, 0.16, 0.10, 1.0),
            drawFaces=True,
            drawEdges=True,
        )
