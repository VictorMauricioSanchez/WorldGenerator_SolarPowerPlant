import numpy as np
import pyqtgraph.opengl as gl


class StructurePointsRenderer:
    """
    Renderiza puntos de implantación sobre el terreno 3D.
    """

    @staticmethod
    def create_point(
        x: float,
        y: float,
        z: float,
    ) -> gl.GLScatterPlotItem:
        """
        Crea un marcador 3D para una posición local X,Y,Z.
        """

        position = np.array(
            [
                [
                    float(x),
                    float(y),
                    float(z) + 1.0,
                ]
            ],
            dtype=np.float32,
        )

        point_item = gl.GLScatterPlotItem(
            pos=position,
            size=1.0,
            color=(1.0, 0.0, 0.0, 1.0),
            pxMode=False,
        )

        return point_item
    @staticmethod
    def create_points(
        points: list[tuple[float, float, float]],
    ) -> gl.GLScatterPlotItem:
        """
        Crea un único objeto gráfico que contiene
        todos los puntos de implantación.

        Cada punto debe tener el formato:

            (x, y, z)
        """

        if not points:
            raise ValueError(
                "No se proporcionaron puntos para renderizar."
            )

        positions = np.array(
            [
                (
                    float(x),
                    float(y),
                    float(z) + 1.0,
                )
                for x, y, z in points
            ],
            dtype=np.float32,
        )

        point_item = gl.GLScatterPlotItem(
            pos=positions,
            size=1.0,
            color=(1.0, 0.0, 0.0, 1.0),
            pxMode=True,
        )

        return point_item
