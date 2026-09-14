from dataclasses import dataclass

import numpy as np
import pyqtgraph.opengl as gl

from world.solar_structure import SolarStructure


@dataclass
class SolarStructureRenderBundle:
    """
    Agrupa todos los elementos gráficos que representan
    una estructura fotovoltaica.

    Una estructura solar no se representa mediante una sola malla,
    sino mediante postes, vigas, tubos y módulos independientes.
    """

    object_id: str
    items: tuple[object, ...]


class SolarStructureRenderer:
    """
    Convierte un SolarStructure en elementos visibles de PyQtGraph.

    Sistema de coordenadas local:

    - X: dirección longitudinal de la fila.
    - Y: dirección transversal entre filas.
    - Z: dirección vertical.
    """

    POST_COLOR = (
        0.30,
        0.32,
        0.35,
        1.0,
    )

    BEAM_COLOR = (
        0.45,
        0.47,
        0.50,
        1.0,
    )

    TUBE_COLOR = (
        0.25,
        0.27,
        0.30,
        1.0,
    )

    PANEL_COLOR = (
        0.05,
        0.18,
        0.32,
        1.0,
    )

    PANEL_EDGE_COLOR = (
        0.60,
        0.75,
        0.90,
        1.0,
    )

    MOTOR_COLOR = (
        0.55,
        0.18,
        0.12,
        1.0,
    )

    @classmethod
    def create(
        cls,
        structure: SolarStructure,
    ) -> SolarStructureRenderBundle:
        """
        Crea la representación gráfica completa de la estructura.
        """

        structure.validate()

        items: list[object] = []

        row_length = structure.get_row_length()
        row_offsets = structure.get_row_offsets()
        active_angle = structure.active_angle

        post_positions = cls._calculate_post_positions(
            row_length=row_length,
            post_count=structure.post_count,
            module_length=structure.module_length,
        )

        for row_offset in row_offsets:
            cls._create_row(
                structure=structure,
                row_offset=row_offset,
                row_length=row_length,
                post_positions=post_positions,
                active_angle=active_angle,
                items=items,
            )

        if structure.structure_type == "dual_row_tracker":
            cls._create_dual_row_connection(
                structure=structure,
                items=items,
            )

        return SolarStructureRenderBundle(
            object_id=structure.object_id,
            items=tuple(items),
        )

    @classmethod
    def create_from_post_points(
        cls,
        structure: SolarStructure,
    ) -> SolarStructureRenderBundle:
        """
        Crea un seguidor mono-fila utilizando las posiciones
        reales de los postes importadas desde el CSV.
        """

        if structure.structure_type != "single_row_tracker":
            raise ValueError(
                "La generación desde postes reales solo está "
                "disponible para seguidores mono-fila."
            )

        if len(structure.post_points) < 2:
            raise ValueError(
                "La estructura debe contener al menos dos postes."
            )

        points = np.asarray(
            structure.post_points,
            dtype=float,
        )

        # -------------------------------------------------
        # Determinar orientación longitudinal de la fila.
        # -------------------------------------------------
        first_point = points[0]
        last_point = points[-1]

        delta_x = last_point[0] - first_point[0]
        delta_y = last_point[1] - first_point[1]

        row_span = float(np.hypot(delta_x, delta_y))

        if row_span <= 0.0:
            raise ValueError(
                "No se puede determinar la dirección de la fila."
            )

        center_x = (first_point[0] + last_point[0]) / 2.0
        center_y = (first_point[1] + last_point[1]) / 2.0

        yaw = float(
            np.degrees(
                np.arctan2(delta_y, delta_x)
            )
        )

        structure.x = center_x
        structure.y = center_y
        structure.z = 0.0
        structure.yaw = yaw
        structure.post_count = len(points)

        # -------------------------------------------------
        # Convertir XY globales de los postes al sistema
        # local de la estructura.
        # -------------------------------------------------
        yaw_radians = np.radians(yaw)

        cos_yaw = np.cos(yaw_radians)
        sin_yaw = np.sin(yaw_radians)

        relative_x = points[:, 0] - center_x
        relative_y = points[:, 1] - center_y

        local_x = (
            cos_yaw * relative_x
            + sin_yaw * relative_y
        )

        local_y = (
            -sin_yaw * relative_x
            + cos_yaw * relative_y
        )

        local_z = points[:, 2]

        order = np.argsort(local_x)

        local_x = local_x[order]
        local_y = local_y[order]
        local_z = local_z[order]

        # -------------------------------------------------
        # Longitud del seguidor.
        # -------------------------------------------------
        row_length = (
            float(local_x[-1] - local_x[0])
            + structure.module_length * 0.50
        )

        # -------------------------------------------------
        # Número de paneles según la longitud real.
        # -------------------------------------------------
        module_pitch = (
            structure.module_length
            + structure.module_gap
        )

        structure.modules_per_row = max(
            1,
            int(
                np.floor(
                    row_length / module_pitch
                )
            ),
        )

        # -------------------------------------------------
        # Altura del eje del tracker.
        #
        # Se utiliza el punto más alto del terreno y se
        # mantiene una altura mínima de post_height.
        # Los postes situados más abajo serán más largos.
        # -------------------------------------------------
        axis_height = (
            float(np.max(local_z))
            + structure.post_height
        )

        items: list[object] = []

        # -------------------------------------------------
        # Postes reales.
        # -------------------------------------------------
        for post_x, post_y, ground_z in zip(
            local_x,
            local_y,
            local_z,
        ):
            actual_post_height = (
                axis_height - float(ground_z)
            )

            post = cls._create_box_item(
                structure=structure,
                center=(
                    float(post_x),
                    float(post_y),
                    float(ground_z)
                    + actual_post_height / 2.0,
                ),
                size=(
                    structure.post_width,
                    structure.post_depth,
                    actual_post_height,
                ),
                color=cls.POST_COLOR,
            )

            items.append(post)

        # -------------------------------------------------
        # Tubo longitudinal del tracker.
        # -------------------------------------------------
        torque_tube = cls._create_cylinder_item(
            structure=structure,
            center=(
                0.0,
                0.0,
                axis_height,
            ),
            radius=structure.torque_tube_radius,
            length=row_length,
            color=cls.TUBE_COLOR,
        )

        items.append(torque_tube)

        # -------------------------------------------------
        # Travesaños sobre cada poste.
        # -------------------------------------------------
        beam_height = (
            axis_height
            + structure.torque_tube_radius
        )

        for post_x, post_y in zip(
            local_x,
            local_y,
        ):
            cross_beam = cls._create_box_item(
                structure=structure,
                center=(
                    float(post_x),
                    float(post_y),
                    beam_height,
                ),
                size=(
                    structure.beam_thickness,
                    structure.module_width * 0.90,
                    structure.beam_thickness,
                ),
                color=cls.BEAM_COLOR,
                local_rotation=(
                    structure.tracker_angle,
                    0.0,
                    0.0,
                ),
            )

            items.append(cross_beam)

        # -------------------------------------------------
        # Paneles solares.
        # -------------------------------------------------
        first_module_x = (
            -(
                structure.modules_per_row - 1
            )
            * module_pitch
            / 2.0
        )

        panel_height = (
            axis_height
            + structure.torque_tube_radius
            + structure.beam_thickness
            + structure.module_thickness / 2.0
        )

        for module_index in range(
            structure.modules_per_row
        ):
            module_x = (
                first_module_x
                + module_index * module_pitch
            )

            panel = cls._create_box_item(
                structure=structure,
                center=(
                    module_x,
                    0.0,
                    panel_height,
                ),
                size=(
                    structure.module_length,
                    structure.module_width,
                    structure.module_thickness,
                ),
                color=cls.PANEL_COLOR,
                edge_color=cls.PANEL_EDGE_COLOR,
                local_rotation=(
                    structure.tracker_angle,
                    0.0,
                    0.0,
                ),
            )

            items.append(panel)

        return SolarStructureRenderBundle(
            object_id=structure.object_id,
            items=tuple(items),
        )

    # =========================================================
    # CREACIÓN DE UNA FILA COMPLETA
    # =========================================================

    @classmethod
    def _create_row(
        cls,
        structure: SolarStructure,
        row_offset: float,
        row_length: float,
        post_positions: np.ndarray,
        active_angle: float,
        items: list[object],
    ) -> None:
        """
        Añade postes, viga o tubo, soportes y paneles de una fila.
        """

        cls._create_posts(
            structure=structure,
            row_offset=row_offset,
            post_positions=post_positions,
            items=items,
        )

        cls._create_longitudinal_support(
            structure=structure,
            row_offset=row_offset,
            row_length=row_length,
            items=items,
        )

        cls._create_cross_beams(
            structure=structure,
            row_offset=row_offset,
            post_positions=post_positions,
            active_angle=active_angle,
            items=items,
        )

        cls._create_modules(
            structure=structure,
            row_offset=row_offset,
            active_angle=active_angle,
            items=items,
        )

    # =========================================================
    # POSTES
    # =========================================================

    @classmethod
    def _create_posts(
        cls,
        structure: SolarStructure,
        row_offset: float,
        post_positions: np.ndarray,
        items: list[object],
    ) -> None:
        for post_x in post_positions:
            post = cls._create_box_item(
                structure=structure,
                center=(
                    float(post_x),
                    row_offset,
                    structure.post_height / 2.0,
                ),
                size=(
                    structure.post_width,
                    structure.post_depth,
                    structure.post_height,
                ),
                color=cls.POST_COLOR,
            )

            items.append(post)

    # =========================================================
    # SOPORTE LONGITUDINAL
    # =========================================================

    @classmethod
    def _create_longitudinal_support(
        cls,
        structure: SolarStructure,
        row_offset: float,
        row_length: float,
        items: list[object],
    ) -> None:
        support_height = structure.post_height

        if structure.structure_type == "fixed":
            longitudinal_beam = cls._create_box_item(
                structure=structure,
                center=(
                    0.0,
                    row_offset,
                    support_height,
                ),
                size=(
                    row_length,
                    structure.beam_thickness,
                    structure.beam_thickness,
                ),
                color=cls.BEAM_COLOR,
            )

            items.append(longitudinal_beam)

        else:
            torque_tube = cls._create_cylinder_item(
                structure=structure,
                center=(
                    0.0,
                    row_offset,
                    support_height,
                ),
                radius=structure.torque_tube_radius,
                length=row_length,
                color=cls.TUBE_COLOR,
            )

            items.append(torque_tube)

    # =========================================================
    # TRAVESAÑOS
    # =========================================================

    @classmethod
    def _create_cross_beams(
        cls,
        structure: SolarStructure,
        row_offset: float,
        post_positions: np.ndarray,
        active_angle: float,
        items: list[object],
    ) -> None:
        beam_length = (
            structure.module_width * 0.90
        )

        beam_height = (
            structure.post_height
            + structure.torque_tube_radius
        )

        for post_x in post_positions:
            cross_beam = cls._create_box_item(
                structure=structure,
                center=(
                    float(post_x),
                    row_offset,
                    beam_height,
                ),
                size=(
                    structure.beam_thickness,
                    beam_length,
                    structure.beam_thickness,
                ),
                color=cls.BEAM_COLOR,
                local_rotation=(
                    active_angle,
                    0.0,
                    0.0,
                ),
            )

            items.append(cross_beam)

    # =========================================================
    # MÓDULOS FOTOVOLTAICOS
    # =========================================================

    @classmethod
    def _create_modules(
        cls,
        structure: SolarStructure,
        row_offset: float,
        active_angle: float,
        items: list[object],
    ) -> None:
        module_pitch = (
            structure.module_length
            + structure.module_gap
        )

        first_module_x = (
            -(
                structure.modules_per_row - 1
            )
            * module_pitch
            / 2.0
        )

        panel_center_height = (
            structure.post_height
            + structure.torque_tube_radius
            + structure.beam_thickness
            + structure.module_thickness / 2.0
        )

        for module_index in range(
            structure.modules_per_row
        ):
            module_x = (
                first_module_x
                + module_index * module_pitch
            )

            panel = cls._create_box_item(
                structure=structure,
                center=(
                    module_x,
                    row_offset,
                    panel_center_height,
                ),
                size=(
                    structure.module_length,
                    structure.module_width,
                    structure.module_thickness,
                ),
                color=cls.PANEL_COLOR,
                edge_color=cls.PANEL_EDGE_COLOR,
                local_rotation=(
                    active_angle,
                    0.0,
                    0.0,
                ),
            )

            items.append(panel)

    # =========================================================
    # CONEXIÓN DEL SEGUIDOR DUAL-ROW
    # =========================================================

    @classmethod
    def _create_dual_row_connection(
        cls,
        structure: SolarStructure,
        items: list[object],
    ) -> None:
        """
        Representa de forma simplificada el mecanismo que sincroniza
        ambas filas del seguidor dual-row.
        """

        connection_height = structure.post_height

        connection_beam = cls._create_box_item(
            structure=structure,
            center=(
                0.0,
                0.0,
                connection_height,
            ),
            size=(
                structure.beam_thickness * 2.0,
                structure.row_spacing,
                structure.beam_thickness * 2.0,
            ),
            color=cls.BEAM_COLOR,
        )

        motor_housing = cls._create_box_item(
            structure=structure,
            center=(
                0.0,
                0.0,
                connection_height,
            ),
            size=(
                0.50,
                0.50,
                0.50,
            ),
            color=cls.MOTOR_COLOR,
        )

        items.append(connection_beam)
        items.append(motor_housing)

    # =========================================================
    # POSICIONES DE LOS POSTES
    # =========================================================

    @staticmethod
    def _calculate_post_positions(
        row_length: float,
        post_count: int,
        module_length: float,
    ) -> np.ndarray:
        """
        Distribuye los postes uniformemente a lo largo de la fila,
        dejando un margen en ambos extremos.
        """

        usable_span = max(
            row_length - module_length * 0.50,
            row_length * 0.50,
        )

        return np.linspace(
            -usable_span / 2.0,
            usable_span / 2.0,
            post_count,
        )

    # =========================================================
    # CREACIÓN DE PRIMITIVAS
    # =========================================================

    @classmethod
    def _create_box_item(
        cls,
        structure: SolarStructure,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        color: tuple[float, float, float, float],
        edge_color: tuple[
            float,
            float,
            float,
            float,
        ] = (
            0.10,
            0.10,
            0.12,
            1.0,
        ),
        local_rotation: tuple[
            float,
            float,
            float,
        ] = (
            0.0,
            0.0,
            0.0,
        ),
    ) -> gl.GLMeshItem:
        vertices, faces = cls._create_box_geometry(
            size=size
        )

        transformed_vertices = (
            cls._transform_vertices(
                vertices=vertices,
                structure=structure,
                local_center=center,
                local_rotation=local_rotation,
            )
        )

        mesh_data = gl.MeshData(
            vertexes=transformed_vertices,
            faces=faces,
        )

        return gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            shader="shaded",
            color=color,
            drawFaces=True,
            drawEdges=True,
            edgeColor=edge_color,
        )

    @classmethod
    def _create_cylinder_item(
        cls,
        structure: SolarStructure,
        center: tuple[float, float, float],
        radius: float,
        length: float,
        color: tuple[float, float, float, float],
    ) -> gl.GLMeshItem:
        """
        Crea un cilindro y lo orienta longitudinalmente sobre X.
        """

        cylinder_mesh = gl.MeshData.cylinder(
            rows=1,
            cols=24,
            radius=[
                radius,
                radius,
            ],
            length=length,
        )

        vertices = np.array(
            cylinder_mesh.vertexes(),
            dtype=float,
            copy=True,
        )

        faces = np.array(
            cylinder_mesh.faces(),
            dtype=int,
            copy=True,
        )

        # MeshData.cylinder genera el cilindro sobre Z.
        # Primero lo centramos respecto a su longitud.
        vertices[:, 2] -= length / 2.0

        # Después lo rotamos 90° alrededor de Y para alinearlo con X.
        cylinder_rotation = cls._rotation_matrix(
            roll_degrees=0.0,
            pitch_degrees=90.0,
            yaw_degrees=0.0,
        )

        vertices = (
            vertices
            @ cylinder_rotation.T
        )

        transformed_vertices = (
            cls._transform_vertices(
                vertices=vertices,
                structure=structure,
                local_center=center,
                local_rotation=(
                    0.0,
                    0.0,
                    0.0,
                ),
            )
        )

        mesh_data = gl.MeshData(
            vertexes=transformed_vertices,
            faces=faces,
        )

        return gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            shader="shaded",
            color=color,
            drawFaces=True,
            drawEdges=False,
        )

    @staticmethod
    def _create_box_geometry(
        size: tuple[float, float, float],
    ) -> tuple[np.ndarray, np.ndarray]:
        size_x, size_y, size_z = size

        half_x = size_x / 2.0
        half_y = size_y / 2.0
        half_z = size_z / 2.0

        vertices = np.array(
            [
                [-half_x, -half_y, -half_z],
                [half_x, -half_y, -half_z],
                [half_x, half_y, -half_z],
                [-half_x, half_y, -half_z],
                [-half_x, -half_y, half_z],
                [half_x, -half_y, half_z],
                [half_x, half_y, half_z],
                [-half_x, half_y, half_z],
            ],
            dtype=float,
        )

        faces = np.array(
            [
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
            ],
            dtype=int,
        )

        return vertices, faces

    # =========================================================
    # TRANSFORMACIONES
    # =========================================================

    @classmethod
    def _transform_vertices(
        cls,
        vertices: np.ndarray,
        structure: SolarStructure,
        local_center: tuple[
            float,
            float,
            float,
        ],
        local_rotation: tuple[
            float,
            float,
            float,
        ],
    ) -> np.ndarray:
        """
        Aplica en este orden:

        1. Rotación propia del componente.
        2. Posición local dentro de la estructura.
        3. Escala global.
        4. Rotación global de la estructura.
        5. Posición global de la estructura.
        """

        local_rotation_matrix = (
            cls._rotation_matrix(
                roll_degrees=local_rotation[0],
                pitch_degrees=local_rotation[1],
                yaw_degrees=local_rotation[2],
            )
        )

        transformed = (
            vertices
            @ local_rotation_matrix.T
        )

        transformed += np.array(
            local_center,
            dtype=float,
        )

        transformed *= structure.scale

        global_rotation_matrix = (
            cls._rotation_matrix(
                roll_degrees=structure.roll,
                pitch_degrees=structure.pitch,
                yaw_degrees=structure.yaw,
            )
        )

        transformed = (
            transformed
            @ global_rotation_matrix.T
        )

        transformed += np.array(
            [
                structure.x,
                structure.y,
                structure.z,
            ],
            dtype=float,
        )

        return transformed

    @staticmethod
    def _rotation_matrix(
        roll_degrees: float,
        pitch_degrees: float,
        yaw_degrees: float,
    ) -> np.ndarray:
        roll = np.radians(roll_degrees)
        pitch = np.radians(pitch_degrees)
        yaw = np.radians(yaw_degrees)

        rotation_x = np.array(
            [
                [1.0, 0.0, 0.0],
                [
                    0.0,
                    np.cos(roll),
                    -np.sin(roll),
                ],
                [
                    0.0,
                    np.sin(roll),
                    np.cos(roll),
                ],
            ],
            dtype=float,
        )

        rotation_y = np.array(
            [
                [
                    np.cos(pitch),
                    0.0,
                    np.sin(pitch),
                ],
                [0.0, 1.0, 0.0],
                [
                    -np.sin(pitch),
                    0.0,
                    np.cos(pitch),
                ],
            ],
            dtype=float,
        )

        rotation_z = np.array(
            [
                [
                    np.cos(yaw),
                    -np.sin(yaw),
                    0.0,
                ],
                [
                    np.sin(yaw),
                    np.cos(yaw),
                    0.0,
                ],
                [0.0, 0.0, 1.0],
            ],
            dtype=float,
        )

        return (
            rotation_z
            @ rotation_y
            @ rotation_x
        )
