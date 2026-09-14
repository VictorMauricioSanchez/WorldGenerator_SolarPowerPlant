from __future__ import annotations

import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from services.geotiff_reader import GeoTiffReader
from services.simple_robot_exporter import SimpleRobotExporter
from world.solar_structure import SolarStructure
from world.wall import Wall
from world.world_project import WorldProject


class SdfGenerator:
    """
    Genera una primera versión funcional de un mundo SDF.

    En esta etapa:

    - El terreno es un modelo estático.
    - Los muros son modelos estáticos.
    - Las estructuras fotovoltaicas son modelos estáticos.
    - Los seguidores representan el ángulo configurado,
      pero todavía no incorporan joints ni controladores.
    """

    SDF_VERSION = "1.10"

    GROUND_COLOR = (
        0.28,
        0.42,
        0.22,
        1.0,
    )

    WALL_COLOR = (
        0.68,
        0.68,
        0.72,
        1.0,
    )

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

    MOTOR_COLOR = (
        0.55,
        0.18,
        0.12,
        1.0,
    )

    IMPORTED_POST_RADIUS = 0.10
    IMPORTED_POST_HEIGHT = 2.00

    IMPORTED_POST_COLOR = (
        1.0,
        0.75,
        0.0,
        1.0,
    )

    GAZEBO_ROUTE_WIDTH = 0.60
    GAZEBO_ROUTE_Z_OFFSET = 1.00

    GAZEBO_DOCKOUT_WIDTH = 0.60
    GAZEBO_DOCKOUT_DASH_LENGTH = 2.00
    GAZEBO_DOCKOUT_GAP = 1.00

    @classmethod
    def generate(
        cls,
        project: WorldProject,
        post_points: list[tuple[float, float, float]] | None = None,
        post_groups: list[list[tuple[float, float, float]]] | None = None,
        route_points: list[tuple[float, float, float]] | None = None,
        dockout_points: list[tuple[float, float, float]] | None = None,
        home_position: tuple[float, float, float] | None = None,
    ) -> str:
        """
        Genera el documento SDF completo como texto.
        """

        if project.width <= 0 or project.length <= 0:
            raise ValueError(
                "Las dimensiones del terreno deben ser "
                "mayores que cero."
            )

        root = ET.Element(
            "sdf",
            {
                "version": cls.SDF_VERSION,
            },
        )

        world = ET.SubElement(
            root,
            "world",
            {
                "name": cls._sanitize_name(
                    project.name,
                    fallback="generated_world",
                ),
            },
        )

        cls._add_world_plugins(world)
        cls._add_scene(world)
        cls._add_sun(world)

        #cls._add_gui(world)

        if project.creation_mode == "terrain":
            cls._add_terrain_mesh(world)
        else:
            cls._add_ground(
                world=world,
                width=project.width,
                length=project.length,
            )

        if post_groups:
            cls._add_solar_field_mesh(
                world=world,
            )
        elif post_points:
            cls._add_imported_posts_mesh(
                world=world,
            )

        if route_points:
            cls._add_route_mesh(
                world=world,
            )

        if home_position is not None:
            cls._add_simple_route_robot(
                world=world,
                home_position=home_position,
                dockout_points=dockout_points,
            )

        if dockout_points:
            cls._add_dockout_route_mesh(
                world=world,
            )

        for world_object in project.get_all_objects():
            if world_object.object_type == "wall":
                cls._add_wall(
                    world=world,
                    wall=world_object,
                )

            elif (
                world_object.object_type
                == "solar_structure"
            ):
                cls._add_solar_structure(
                    world=world,
                    structure=world_object,
                )

        tree = ET.ElementTree(root)

        ET.indent(
            tree,
            space="  ",
        )

        xml_bytes = ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )

        return xml_bytes.decode("utf-8")

    @classmethod
    def export(
        cls,
        project: WorldProject,
        output_path: str | Path,
        post_points: list[tuple[float, float, float]] | None = None,
        post_groups: list[list[tuple[float, float, float]]] | None = None,
        route_points: list[tuple[float, float, float]] | None = None,
        dockout_points: list[tuple[float, float, float]] | None = None,
        home_position: tuple[float, float, float] | None = None,
    ) -> Path:
        """
        Genera el SDF y lo escribe en el archivo indicado.
        """

        destination = Path(output_path)

        if destination.suffix.lower() != ".sdf":
            destination = destination.with_suffix(
                ".sdf"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if home_position is not None:
            SimpleRobotExporter.export(
                output_directory=destination.parent.parent / "models",
            )

        cls._export_gui_config(
            project=project,
            output_directory=destination.parent,
        )

        if project.creation_mode == "terrain":
            cls._export_terrain_obj(project=project, output_directory=destination.parent,)

        if post_points:
            cls._export_posts_obj(
                post_points=post_points,
                output_directory=destination.parent,
            )

        if post_groups:
            cls._export_solar_field_obj(
                post_groups=post_groups,
                output_directory=destination.parent,
            )

        if route_points:
            cls._export_route_obj(
                route_points=route_points,
                output_directory=destination.parent,
            )

        if dockout_points:
            cls._export_dockout_route_obj(
                dockout_points=dockout_points,
                output_directory=destination.parent,
            )

        sdf_content = cls.generate(
            project,
            post_points=post_points,
            post_groups=post_groups,
            route_points=route_points,
            dockout_points=dockout_points,
            home_position=home_position,
        )

        destination.write_text(
            sdf_content,
            encoding="utf-8",
        )

        return destination.resolve()

    @classmethod
    def _export_gui_config(
        cls,
        project: WorldProject,
        output_directory: Path,
    ) -> Path:
        template_path = Path.home() / ".gz" / "sim" / "8" / "gui.config"

        if not template_path.exists():
            raise FileNotFoundError(
                f"No se encontró la configuración de Gazebo: {template_path}"
            )

        config_text = template_path.read_text(
            encoding="utf-8"
        )

        terrain_size = max(
            project.width,
            project.length,
        )

        terrain_relief = 0.0

        if project.terrain_path:
            terrain_info = GeoTiffReader.read_info(
                project.terrain_path
            )

            terrain_relief = (
                terrain_info.max_elevation
                - terrain_info.min_elevation
            )

        camera_x = -0.65 * project.width
        camera_y = -0.65 * project.length

        camera_z = max(
            100.0,
            terrain_relief + 0.45 * terrain_size,
        )

        camera_yaw = math.atan2(
            -camera_y,
            -camera_x,
        )

        camera_pitch = 0.5

        far_clip = max(
            1000.0,
            4.0 * terrain_size,
        )

        camera_pose_text = cls._pose_text(
            camera_x,
            camera_y,
            camera_z,
            0.0,
            camera_pitch,
            camera_yaw,
        )

        plugin_match = re.search(
            r'(<plugin\s+filename="MinimalScene"\s+name="3D View">)(.*?)(</plugin>)',
            config_text,
            flags=re.DOTALL,
        )

        if plugin_match is None:
            raise ValueError(
                "No se encontró el plugin MinimalScene en gui.config."
            )

        plugin_content = plugin_match.group(2)

        plugin_content = re.sub(
            r"<engine>.*?</engine>",
            "<engine>ogre</engine>",
            plugin_content,
            count=1,
            flags=re.DOTALL,
        )

        plugin_content = re.sub(
            r"<camera_pose>.*?</camera_pose>",
            f"<camera_pose>{camera_pose_text}</camera_pose>",
            plugin_content,
            count=1,
            flags=re.DOTALL,
        )

        camera_clip_text = (
            "\n    <camera_clip>\n"
            "        <near>0.1</near>\n"
            f"        <far>{cls._number_text(far_clip)}</far>\n"
            "    </camera_clip>\n"
        )

        if "<camera_clip>" in plugin_content:
            plugin_content = re.sub(
                r"<camera_clip>.*?</camera_clip>",
                camera_clip_text.strip(),
                plugin_content,
                count=1,
                flags=re.DOTALL,
            )
        else:
            plugin_content = (
                plugin_content.rstrip()
                + camera_clip_text
            )

        updated_plugin = (
            plugin_match.group(1)
            + plugin_content
            + plugin_match.group(3)
        )

        config_text = (
            config_text[:plugin_match.start()]
            + updated_plugin
            + config_text[plugin_match.end():]
        )

        output_path = (
            output_directory
            / f"{project.name}_gui.config"
        )

        output_path.write_text(
            config_text,
            encoding="utf-8",
        )

        return output_path.resolve()

    # =========================================================
    # CONFIGURACIÓN GENERAL DEL MUNDO
    # =========================================================

    @staticmethod
    def _add_world_plugins(
        world: ET.Element,
    ) -> None:
        ET.SubElement(
            world,
            "plugin",
            {
                "filename": "gz-sim-physics-system",
                "name": "gz::sim::systems::Physics",
            },
        )

        ET.SubElement(
            world,
            "plugin",
            {
                "filename": "gz-sim-user-commands-system",
                "name": "gz::sim::systems::UserCommands",
            },
        )

        ET.SubElement(
            world,
            "plugin",
            {
                "filename": "gz-sim-scene-broadcaster-system",
                "name": "gz::sim::systems::SceneBroadcaster",
            },
        )

    @staticmethod
    def _add_scene(
        world: ET.Element,
    ) -> None:
        scene = ET.SubElement(
            world,
            "scene",
        )

        ET.SubElement(
            scene,
            "ambient",
        ).text = "0.45 0.45 0.45 1"

        ET.SubElement(
            scene,
            "background",
        ).text = "0.70 0.80 0.92 1"

        ET.SubElement(
            scene,
            "shadows",
        ).text = "true"

    @staticmethod
    def _add_gui(
        world: ET.Element,
    ) -> None:
        policies = ET.SubElement(
            world,
            "gz:policies",
        )

        ET.SubElement(
            policies,
            "include_gui_default_plugins",
        ).text = "true"

        gui = ET.SubElement(
            world,
            "gui",
            {
                "fullscreen": "0",
            },
        )

        plugin = ET.SubElement(
            gui,
            "plugin",
            {
                "filename": "MinimalScene",
                "name": "3D View",
            },
        )

        gz_gui = ET.SubElement(
            plugin,
            "gz-gui",
        )

        ET.SubElement(
            gz_gui,
            "title",
        ).text = "3D View"

        ET.SubElement(
            gz_gui,
            "property",
            {
                "type": "bool",
                "key": "showTitleBar",
            },
        ).text = "false"

        ET.SubElement(
            gz_gui,
            "property",
            {
                "type": "string",
                "key": "state",
            },
        ).text = "docked"

        ET.SubElement(
            plugin,
            "engine",
        ).text = "ogre"

        ET.SubElement(
            plugin,
            "scene",
        ).text = "scene"

        ET.SubElement(
            plugin,
            "ambient_light",
        ).text = "0.4 0.4 0.4"

        ET.SubElement(
            plugin,
            "background_color",
        ).text = "0.8 0.8 0.8"

        ET.SubElement(
            plugin,
            "camera_pose",
        ).text = "-900 -900 800 0 0.5 0.785398"

        camera_clip = ET.SubElement(
            plugin,
            "camera_clip",
        )

        ET.SubElement(
            camera_clip,
            "near",
        ).text = "0.1"

        ET.SubElement(
            camera_clip,
            "far",
        ).text = "5000"

    @staticmethod
    def _add_sun(
        world: ET.Element,
    ) -> None:
        light = ET.SubElement(
            world,
            "light",
            {
                "name": "sun",
                "type": "directional",
            },
        )

        ET.SubElement(
            light,
            "cast_shadows",
        ).text = "true"

        ET.SubElement(
            light,
            "pose",
        ).text = "0 0 10 0 0 0"

        ET.SubElement(
            light,
            "diffuse",
        ).text = "0.9 0.9 0.9 1"

        ET.SubElement(
            light,
            "specular",
        ).text = "0.2 0.2 0.2 1"

        ET.SubElement(
            light,
            "direction",
        ).text = "-0.5 0.3 -1.0"

    @classmethod
    def _export_posts_obj(
        cls,
        post_points: list[tuple[float, float, float]],
        output_directory: Path,
    ) -> Path:
        if not post_points:
            raise ValueError(
                "No existen postes para exportar."
            )

        posts_directory = output_directory / "posts"
        posts_directory.mkdir(parents=True, exist_ok=True)

        obj_path = posts_directory / "postes.obj"
        mtl_path = posts_directory / "postes.mtl"

        radius = cls.IMPORTED_POST_RADIUS
        height = cls.IMPORTED_POST_HEIGHT
        sides = 8

        with mtl_path.open("w", encoding="utf-8") as mtl_file:
            mtl_file.write("newmtl post_material\n")
            mtl_file.write("Ka 0.90 0.75 0.10\n")
            mtl_file.write("Kd 0.90 0.75 0.10\n")
            mtl_file.write("Ks 0.05 0.05 0.05\n")
            mtl_file.write("Ns 10.0\n")
            mtl_file.write("d 1.0\n")

        with obj_path.open("w", encoding="utf-8") as obj_file:
            obj_file.write("mtllib postes.mtl\n")
            obj_file.write("usemtl post_material\n")
            obj_file.write("# Postes importados\n\n")

            vertex_offset = 1

            for post_index, (x, y, terrain_z) in enumerate(post_points, start=1):
                obj_file.write(f"o post_{post_index}\n")

                for side in range(sides):
                    angle = 2.0 * math.pi * side / sides
                    vertex_x = x + radius * math.cos(angle)
                    vertex_y = y + radius * math.sin(angle)

                    obj_file.write(
                        f"v {vertex_x:.6f} {vertex_y:.6f} {terrain_z:.6f}\n"
                    )

                for side in range(sides):
                    angle = 2.0 * math.pi * side / sides
                    vertex_x = x + radius * math.cos(angle)
                    vertex_y = y + radius * math.sin(angle)
                    vertex_z = terrain_z + height

                    obj_file.write(
                        f"v {vertex_x:.6f} {vertex_y:.6f} {vertex_z:.6f}\n"
                    )

                bottom_center = vertex_offset + 2 * sides
                top_center = bottom_center + 1

                obj_file.write(
                    f"v {x:.6f} {y:.6f} {terrain_z:.6f}\n"
                )

                obj_file.write(
                    f"v {x:.6f} {y:.6f} {terrain_z + height:.6f}\n"
                )

                for side in range(sides):
                    next_side = (side + 1) % sides

                    bottom_current = vertex_offset + side
                    bottom_next = vertex_offset + next_side

                    top_current = vertex_offset + sides + side
                    top_next = vertex_offset + sides + next_side

                    obj_file.write(
                        f"f {bottom_current} {bottom_next} {top_next}\n"
                    )

                    obj_file.write(
                        f"f {bottom_current} {top_next} {top_current}\n"
                    )

                    obj_file.write(
                        f"f {bottom_center} {bottom_next} {bottom_current}\n"
                    )

                    obj_file.write(
                        f"f {top_center} {top_current} {top_next}\n"
                    )

                vertex_offset += 2 * sides + 2

                obj_file.write("\n")

        return obj_path.resolve()

    @classmethod
    def _export_terrain_obj(
        cls,
        project: WorldProject,
        output_directory: Path,
    ) -> Path:
        if not project.terrain_path:
            raise ValueError(
                "El proyecto no contiene un terreno GeoTIFF."
            )

        terrain_info = GeoTiffReader.read_info(project.terrain_path)

        elevation_data, _ = GeoTiffReader.read_local_elevation_data(
            project.terrain_path
        )

        if elevation_data.ndim != 2:
            raise ValueError(
                "La matriz de elevaciones debe ser bidimensional."
            )

        if np.isnan(elevation_data).any():
            raise ValueError(
                "El terreno contiene valores NoData."
            )

        rows, columns = elevation_data.shape

        dz_drow, dz_dcolumn = np.gradient(
            elevation_data,
            terrain_info.resolution_y,
            terrain_info.resolution_x,
        )

        normal_x = -dz_dcolumn
        normal_y = dz_drow
        normal_z = np.ones_like(elevation_data)

        normal_length = np.sqrt(
            normal_x**2
            + normal_y**2
            + normal_z**2
        )

        normal_x /= normal_length
        normal_y /= normal_length
        normal_z /= normal_length

        if rows < 2 or columns < 2:
            raise ValueError(
                "El terreno debe contener al menos 2 filas y 2 columnas."
            )

        terrain_directory = output_directory / "terrain"
        terrain_directory.mkdir(parents=True, exist_ok=True)

        obj_path = terrain_directory / "terreno.obj"
        mtl_path = terrain_directory / "terreno.mtl"

        terrain_width = columns * terrain_info.resolution_x
        terrain_length = rows * terrain_info.resolution_y

        with obj_path.open("w", encoding="utf-8") as obj_file:
            obj_file.write("mtllib terreno.mtl\n")
            obj_file.write("usemtl terrain_material\n")
            with mtl_path.open("w", encoding="utf-8") as mtl_file:
                mtl_file.write("newmtl terrain_material\n")
                mtl_file.write("Ka 0.28 0.42 0.22\n")
                mtl_file.write("Kd 0.28 0.42 0.22\n")
                mtl_file.write("Ks 0.05 0.05 0.05\n")
                mtl_file.write("Ns 10.0\n")
                mtl_file.write("d 1.0\n")
            obj_file.write("# Terreno generado desde GeoTIFF\n")
            obj_file.write("# X = Este, Y = Norte, Z = elevación local\n\n")

            for row in range(rows):
                y = (rows - row - 0.5) * terrain_info.resolution_y - terrain_length / 2.0

                for column in range(columns):
                    x = (column + 0.5) * terrain_info.resolution_x - terrain_width / 2.0
                    z = float(elevation_data[row, column])

                    obj_file.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")

            obj_file.write("\n")

            for row in range(rows):
                for column in range(columns):
                    nx = float(normal_x[row, column])
                    ny = float(normal_y[row, column])
                    nz = float(normal_z[row, column])

                    obj_file.write(f"vn {nx:.8f} {ny:.8f} {nz:.8f}\n")

            obj_file.write("\n")

            obj_file.write("\n")

            for row in range(rows - 1):
                for column in range(columns - 1):
                    top_left = row * columns + column + 1
                    top_right = top_left + 1
                    bottom_left = top_left + columns
                    bottom_right = bottom_left + 1

                    obj_file.write(
                        f"f {top_left}//{top_left} {bottom_left}//{bottom_left} {top_right}//{top_right}\n"
                    )

                    obj_file.write(
                        f"f {top_right}//{top_right} {bottom_left}//{bottom_left} {bottom_right}//{bottom_right}\n"
                    )
        return obj_path.resolve()

    # =========================================================
    # TERRENO
    # =========================================================
    @classmethod
    def _add_terrain_mesh(
        cls,
        world: ET.Element,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "generated_terrain",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        link = ET.SubElement(
            model,
            "link",
            {
                "name": "terrain_link",
            },
        )

        collision = ET.SubElement(
            link,
            "collision",
            {
                "name": "terrain_collision",
            },
        )

        collision_geometry = ET.SubElement(
            collision,
            "geometry",
        )

        collision_mesh = ET.SubElement(
            collision_geometry,
            "mesh",
        )

        ET.SubElement(
            collision_mesh,
            "uri",
        ).text = "terrain/terreno.obj"

        ET.SubElement(
            collision_mesh,
            "scale",
        ).text = "1 1 1"

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "terrain_visual",
            },
        )

        visual_geometry = ET.SubElement(
            visual,
            "geometry",
        )

        visual_mesh = ET.SubElement(
            visual_geometry,
            "mesh",
        )

        ET.SubElement(
            visual_mesh,
            "uri",
        ).text = "terrain/terreno.obj"

        ET.SubElement(
            visual_mesh,
            "scale",
        ).text = "1 1 1"

        cls._add_material(
            visual=visual,
            color=cls.GROUND_COLOR,
        )

    @classmethod
    def _add_ground(
        cls,
        world: ET.Element,
        width: float,
        length: float,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "generated_ground",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 -0.05 0 0 0"

        cls._add_box_link(
            model=model,
            name="ground_link",
            center=(
                0.0,
                0.0,
                0.0,
            ),
            size=(
                width,
                length,
                0.10,
            ),
            rotation=(
                0.0,
                0.0,
                0.0,
            ),
            color=cls.GROUND_COLOR,
        )

    @classmethod
    def _add_solar_field_mesh(
        cls,
        world: ET.Element,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "imported_solar_field",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        link = ET.SubElement(
            model,
            "link",
            {
                "name": "solar_field_link",
            },
        )

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "solar_field_visual",
            },
        )

        geometry = ET.SubElement(
            visual,
            "geometry",
        )

        mesh = ET.SubElement(
            geometry,
            "mesh",
        )

        ET.SubElement(
            mesh,
            "uri",
        ).text = "solar_field/solar_field.obj"

        ET.SubElement(
            mesh,
            "scale",
        ).text = "1 1 1"

    @classmethod
    def _add_route_mesh(
        cls,
        world: ET.Element,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "generated_work_route",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        link = ET.SubElement(
            model,
            "link",
            {
                "name": "work_route_link",
            },
        )

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "work_route_visual",
            },
        )

        geometry = ET.SubElement(
            visual,
            "geometry",
        )

        mesh = ET.SubElement(
            geometry,
            "mesh",
        )

        ET.SubElement(
            mesh,
            "uri",
        ).text = "gazebo_route/work_route.obj"

        ET.SubElement(
            mesh,
            "scale",
        ).text = "1 1 1"

    @classmethod
    def _add_imported_posts_mesh(
        cls,
        world: ET.Element,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "imported_posts",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        link = ET.SubElement(
            model,
            "link",
            {
                "name": "posts_link",
            },
        )

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "posts_visual",
            },
        )

        geometry = ET.SubElement(
            visual,
            "geometry",
        )

        mesh = ET.SubElement(
            geometry,
            "mesh",
        )

        ET.SubElement(
            mesh,
            "uri",
        ).text = "posts/postes.obj"

        ET.SubElement(
            mesh,
            "scale",
        ).text = "1 1 1"

        cls._add_material(
            visual=visual,
            color=cls.IMPORTED_POST_COLOR,
        )

    @classmethod
    def _add_imported_posts(
        cls,
        world: ET.Element,
        post_points: list[tuple[float, float, float]],
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "imported_posts",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        for post_index, (x, y, terrain_z) in enumerate(post_points, start=1):
            center_z = terrain_z + cls.IMPORTED_POST_HEIGHT / 2.0

            cls._add_cylinder_link(
                model=model,
                name=f"post_{post_index}",
                center=(
                    x,
                    y,
                    center_z,
                ),
                radius=cls.IMPORTED_POST_RADIUS,
                length=cls.IMPORTED_POST_HEIGHT,
                rotation=(
                    0.0,
                    0.0,
                    0.0,
                ),
                color=cls.POST_COLOR,
            )

    # =========================================================
    # MUROS
    # =========================================================

    @classmethod
    def _add_wall(
        cls,
        world: ET.Element,
        wall: Wall,
    ) -> None:
        model_name = cls._unique_model_name(
            prefix="wall",
            object_name=wall.name,
            object_id=wall.object_id,
        )

        model = ET.SubElement(
            world,
            "model",
            {
                "name": model_name,
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = cls._pose_text(
            wall.x,
            wall.y,
            wall.z,
            math.radians(wall.roll),
            math.radians(wall.pitch),
            math.radians(wall.yaw),
        )

        length, thickness, height = (
            wall.get_scaled_dimensions()
        )

        cls._add_box_link(
            model=model,
            name="wall_link",
            center=(
                0.0,
                0.0,
                0.0,
            ),
            size=(
                length,
                thickness,
                height,
            ),
            rotation=(
                0.0,
                0.0,
                0.0,
            ),
            color=cls.WALL_COLOR,
        )

    # =========================================================
    # ESTRUCTURAS FOTOVOLTAICAS
    # =========================================================

    @classmethod
    def _add_solar_structure(
        cls,
        world: ET.Element,
        structure: SolarStructure,
    ) -> None:
        structure.validate()

        model_name = cls._unique_model_name(
            prefix="solar",
            object_name=structure.name,
            object_id=structure.object_id,
        )

        model = ET.SubElement(
            world,
            "model",
            {
                "name": model_name,
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = cls._pose_text(
            structure.x,
            structure.y,
            structure.z,
            math.radians(structure.roll),
            math.radians(structure.pitch),
            math.radians(structure.yaw),
        )

        row_length = structure.get_row_length()
        row_offsets = structure.get_row_offsets()

        post_positions = cls._calculate_post_positions(
            row_length=row_length,
            post_count=structure.post_count,
            module_length=structure.module_length,
        )

        component_index = 0

        for row_index, row_offset in enumerate(
            row_offsets
        ):
            component_index = cls._add_solar_row(
                model=model,
                structure=structure,
                row_index=row_index,
                row_offset=row_offset,
                row_length=row_length,
                post_positions=post_positions,
                initial_index=component_index,
            )

        if structure.structure_type == "dual_row_tracker":
            cls._add_dual_row_connection(
                model=model,
                structure=structure,
                initial_index=component_index,
            )

    @classmethod
    def _add_solar_row(
        cls,
        model: ET.Element,
        structure: SolarStructure,
        row_index: int,
        row_offset: float,
        row_length: float,
        post_positions: tuple[float, ...],
        initial_index: int,
    ) -> int:
        scale = structure.scale
        active_angle = math.radians(
            structure.active_angle
        )

        component_index = initial_index

        for post_index, post_x in enumerate(
            post_positions
        ):
            cls._add_box_link(
                model=model,
                name=(
                    f"row_{row_index}_post_{post_index}_"
                    f"{component_index}"
                ),
                center=(
                    post_x * scale,
                    row_offset * scale,
                    (
                        structure.post_height
                        / 2.0
                    )
                    * scale,
                ),
                size=(
                    structure.post_width * scale,
                    structure.post_depth * scale,
                    structure.post_height * scale,
                ),
                rotation=(
                    0.0,
                    0.0,
                    0.0,
                ),
                color=cls.POST_COLOR,
            )

            component_index += 1

        support_height = (
            structure.post_height * scale
        )

        if structure.structure_type == "fixed":
            cls._add_box_link(
                model=model,
                name=(
                    f"row_{row_index}_longitudinal_beam_"
                    f"{component_index}"
                ),
                center=(
                    0.0,
                    row_offset * scale,
                    support_height,
                ),
                size=(
                    row_length * scale,
                    structure.beam_thickness * scale,
                    structure.beam_thickness * scale,
                ),
                rotation=(
                    0.0,
                    0.0,
                    0.0,
                ),
                color=cls.BEAM_COLOR,
            )

        else:
            cls._add_cylinder_link(
                model=model,
                name=(
                    f"row_{row_index}_torque_tube_"
                    f"{component_index}"
                ),
                center=(
                    0.0,
                    row_offset * scale,
                    support_height,
                ),
                radius=(
                    structure.torque_tube_radius
                    * scale
                ),
                length=row_length * scale,
                rotation=(
                    0.0,
                    math.pi / 2.0,
                    0.0,
                ),
                color=cls.TUBE_COLOR,
            )

        component_index += 1

        cross_beam_length = (
            structure.module_width
            * 0.90
            * scale
        )

        cross_beam_height = (
            structure.post_height
            + structure.torque_tube_radius
        ) * scale

        for beam_index, post_x in enumerate(
            post_positions
        ):
            cls._add_box_link(
                model=model,
                name=(
                    f"row_{row_index}_cross_beam_"
                    f"{beam_index}_{component_index}"
                ),
                center=(
                    post_x * scale,
                    row_offset * scale,
                    cross_beam_height,
                ),
                size=(
                    structure.beam_thickness * scale,
                    cross_beam_length,
                    structure.beam_thickness * scale,
                ),
                rotation=(
                    active_angle,
                    0.0,
                    0.0,
                ),
                color=cls.BEAM_COLOR,
            )

            component_index += 1

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
        ) * scale

        for module_index in range(
            structure.modules_per_row
        ):
            module_x = (
                first_module_x
                + module_index * module_pitch
            )

            cls._add_box_link(
                model=model,
                name=(
                    f"row_{row_index}_module_"
                    f"{module_index}_{component_index}"
                ),
                center=(
                    module_x * scale,
                    row_offset * scale,
                    panel_center_height,
                ),
                size=(
                    structure.module_length * scale,
                    structure.module_width * scale,
                    structure.module_thickness * scale,
                ),
                rotation=(
                    active_angle,
                    0.0,
                    0.0,
                ),
                color=cls.PANEL_COLOR,
            )

            component_index += 1

        return component_index

    @classmethod
    def _add_dual_row_connection(
        cls,
        model: ET.Element,
        structure: SolarStructure,
        initial_index: int,
    ) -> None:
        scale = structure.scale
        connection_height = (
            structure.post_height * scale
        )

        cls._add_box_link(
            model=model,
            name=(
                f"dual_connection_{initial_index}"
            ),
            center=(
                0.0,
                0.0,
                connection_height,
            ),
            size=(
                structure.beam_thickness
                * 2.0
                * scale,
                structure.row_spacing * scale,
                structure.beam_thickness
                * 2.0
                * scale,
            ),
            rotation=(
                0.0,
                0.0,
                0.0,
            ),
            color=cls.BEAM_COLOR,
        )

        cls._add_box_link(
            model=model,
            name=(
                f"dual_motor_{initial_index + 1}"
            ),
            center=(
                0.0,
                0.0,
                connection_height,
            ),
            size=(
                0.50 * scale,
                0.50 * scale,
                0.50 * scale,
            ),
            rotation=(
                0.0,
                0.0,
                0.0,
            ),
            color=cls.MOTOR_COLOR,
        )

    # =========================================================
    # PRIMITIVAS SDF
    # =========================================================

    @classmethod
    def _add_box_link(
        cls,
        model: ET.Element,
        name: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        rotation: tuple[float, float, float],
        color: tuple[float, float, float, float],
    ) -> None:
        link = ET.SubElement(
            model,
            "link",
            {
                "name": cls._sanitize_name(
                    name,
                    fallback="box_link",
                ),
            },
        )

        ET.SubElement(
            link,
            "pose",
        ).text = cls._pose_text(
            center[0],
            center[1],
            center[2],
            rotation[0],
            rotation[1],
            rotation[2],
        )

        collision = ET.SubElement(
            link,
            "collision",
            {
                "name": "collision",
            },
        )

        collision_geometry = ET.SubElement(
            collision,
            "geometry",
        )

        collision_box = ET.SubElement(
            collision_geometry,
            "box",
        )

        ET.SubElement(
            collision_box,
            "size",
        ).text = cls._vector_text(size)

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "visual",
            },
        )

        visual_geometry = ET.SubElement(
            visual,
            "geometry",
        )

        visual_box = ET.SubElement(
            visual_geometry,
            "box",
        )

        ET.SubElement(
            visual_box,
            "size",
        ).text = cls._vector_text(size)

        cls._add_material(
            visual=visual,
            color=color,
        )

    @classmethod
    def _add_cylinder_link(
        cls,
        model: ET.Element,
        name: str,
        center: tuple[float, float, float],
        radius: float,
        length: float,
        rotation: tuple[float, float, float],
        color: tuple[float, float, float, float],
    ) -> None:
        link = ET.SubElement(
            model,
            "link",
            {
                "name": cls._sanitize_name(
                    name,
                    fallback="cylinder_link",
                ),
            },
        )

        ET.SubElement(
            link,
            "pose",
        ).text = cls._pose_text(
            center[0],
            center[1],
            center[2],
            rotation[0],
            rotation[1],
            rotation[2],
        )

        collision = ET.SubElement(
            link,
            "collision",
            {
                "name": "collision",
            },
        )

        collision_geometry = ET.SubElement(
            collision,
            "geometry",
        )

        collision_cylinder = ET.SubElement(
            collision_geometry,
            "cylinder",
        )

        ET.SubElement(
            collision_cylinder,
            "radius",
        ).text = cls._number_text(radius)

        ET.SubElement(
            collision_cylinder,
            "length",
        ).text = cls._number_text(length)

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "visual",
            },
        )

        visual_geometry = ET.SubElement(
            visual,
            "geometry",
        )

        visual_cylinder = ET.SubElement(
            visual_geometry,
            "cylinder",
        )

        ET.SubElement(
            visual_cylinder,
            "radius",
        ).text = cls._number_text(radius)

        ET.SubElement(
            visual_cylinder,
            "length",
        ).text = cls._number_text(length)

        cls._add_material(
            visual=visual,
            color=color,
        )

    @classmethod
    def _add_material(
        cls,
        visual: ET.Element,
        color: tuple[float, float, float, float],
    ) -> None:
        material = ET.SubElement(
            visual,
            "material",
        )

        color_text = cls._color_text(color)

        ET.SubElement(
            material,
            "ambient",
        ).text = color_text

        ET.SubElement(
            material,
            "diffuse",
        ).text = color_text

    # =========================================================
    # CÁLCULOS Y FORMATO
    # =========================================================

    @staticmethod
    def _calculate_post_positions(
        row_length: float,
        post_count: int,
        module_length: float,
    ) -> tuple[float, ...]:
        usable_span = max(
            row_length - module_length * 0.50,
            row_length * 0.50,
        )

        if post_count <= 1:
            return (0.0,)

        start = -usable_span / 2.0
        step = usable_span / (post_count - 1)

        return tuple(
            start + index * step
            for index in range(post_count)
        )

    @classmethod
    def _unique_model_name(
        cls,
        prefix: str,
        object_name: str,
        object_id: str,
    ) -> str:
        short_id = object_id.replace(
            "-",
            "",
        )[:8]

        return cls._sanitize_name(
            f"{prefix}_{object_name}_{short_id}",
            fallback=f"{prefix}_{short_id}",
        )

    @staticmethod
    def _sanitize_name(
        value: str,
        fallback: str,
    ) -> str:
        sanitized = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            value.strip(),
        )

        sanitized = sanitized.strip("_")

        if not sanitized:
            sanitized = fallback

        if sanitized[0].isdigit():
            sanitized = f"object_{sanitized}"

        return sanitized

    @classmethod
    def _pose_text(
        cls,
        x: float,
        y: float,
        z: float,
        roll: float,
        pitch: float,
        yaw: float,
    ) -> str:
        return " ".join(
            cls._number_text(value)
            for value in (
                x,
                y,
                z,
                roll,
                pitch,
                yaw,
            )
        )

    @classmethod
    def _vector_text(
        cls,
        values: tuple[float, float, float],
    ) -> str:
        return " ".join(
            cls._number_text(value)
            for value in values
        )

    @classmethod
    def _color_text(
        cls,
        color: tuple[float, float, float, float],
    ) -> str:
        return " ".join(
            cls._number_text(value)
            for value in color
        )

    @staticmethod
    def _number_text(
        value: float,
    ) -> str:
        return f"{float(value):.8g}"

    @staticmethod
    def _write_obj_box(
        obj_file,
        center: tuple[float, float, float],
        length: float,
        width: float,
        height: float,
        yaw: float,
        vertex_offset: int,
    ) -> int:
        cx, cy, cz = center

        half_length = length / 2.0
        half_width = width / 2.0
        half_height = height / 2.0

        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)

        local_vertices = (
            (-half_length, -half_width, -half_height),
            ( half_length, -half_width, -half_height),
            ( half_length,  half_width, -half_height),
            (-half_length,  half_width, -half_height),
            (-half_length, -half_width,  half_height),
            ( half_length, -half_width,  half_height),
            ( half_length,  half_width,  half_height),
            (-half_length,  half_width,  half_height),
        )

        for local_x, local_y, local_z in local_vertices:
            x = cx + local_x * cos_yaw - local_y * sin_yaw
            y = cy + local_x * sin_yaw + local_y * cos_yaw
            z = cz + local_z

            obj_file.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")

        faces = (
            (1, 2, 3), (1, 3, 4),
            (5, 7, 6), (5, 8, 7),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 8), (3, 8, 4),
            (4, 8, 5), (4, 5, 1),
        )

        for a, b, c in faces:
            obj_file.write(
                f"f {vertex_offset + a - 1} "
                f"{vertex_offset + b - 1} "
                f"{vertex_offset + c - 1}\n"
            )

        return vertex_offset + 8

    @classmethod
    def _export_solar_field_obj(
        cls,
        post_groups: list[list[tuple[float, float, float]]],
        output_directory: Path,
    ) -> Path:
        if not post_groups:
            raise ValueError(
                "No existen grupos de postes para generar el campo solar."
            )

        solar_directory = output_directory / "solar_field"
        solar_directory.mkdir(parents=True, exist_ok=True)

        obj_path = solar_directory / "solar_field.obj"
        mtl_path = solar_directory / "solar_field.mtl"

        module_length = 2.20
        module_width = 1.10
        module_thickness = 0.04
        module_gap = 0.05
        post_height = 1.80

        with mtl_path.open("w", encoding="utf-8") as mtl_file:
            mtl_file.write("newmtl post_material\n")
            mtl_file.write("Ka 0.90 0.75 0.10\n")
            mtl_file.write("Kd 0.90 0.75 0.10\n")
            mtl_file.write("Ks 0.05 0.05 0.05\n\n")

            mtl_file.write("newmtl panel_material\n")
            mtl_file.write("Ka 0.03 0.10 0.25\n")
            mtl_file.write("Kd 0.03 0.10 0.25\n")
            mtl_file.write("Ks 0.30 0.30 0.30\n")
            mtl_file.write("Ns 50.0\n")

        with obj_path.open("w", encoding="utf-8") as obj_file:
            obj_file.write("mtllib solar_field.mtl\n")
            obj_file.write("# Campo solar completo\n\n")

            vertex_offset = 1

            # -------------------------------------------------
            # POSTES
            # -------------------------------------------------

            obj_file.write("usemtl post_material\n")

            radius = cls.IMPORTED_POST_RADIUS
            sides = 8

            for group in post_groups:
                if len(group) < 2:
                    continue

                axis_z = max(point[2] for point in group) + post_height

                for x, y, terrain_z in group:
                    height = axis_z - terrain_z

                    for side in range(sides):
                        angle = 2.0 * math.pi * side / sides
                        vx = x + radius * math.cos(angle)
                        vy = y + radius * math.sin(angle)

                        obj_file.write(
                            f"v {vx:.6f} {vy:.6f} {terrain_z:.6f}\n"
                        )

                    for side in range(sides):
                        angle = 2.0 * math.pi * side / sides
                        vx = x + radius * math.cos(angle)
                        vy = y + radius * math.sin(angle)

                        obj_file.write(
                            f"v {vx:.6f} {vy:.6f} {terrain_z + height:.6f}\n"
                        )

                    bottom_center = vertex_offset + 2 * sides
                    top_center = bottom_center + 1

                    obj_file.write(
                        f"v {x:.6f} {y:.6f} {terrain_z:.6f}\n"
                    )

                    obj_file.write(
                        f"v {x:.6f} {y:.6f} {terrain_z + height:.6f}\n"
                    )

                    for side in range(sides):
                        next_side = (side + 1) % sides

                        bottom_current = vertex_offset + side
                        bottom_next = vertex_offset + next_side
                        top_current = vertex_offset + sides + side
                        top_next = vertex_offset + sides + next_side

                        obj_file.write(
                            f"f {bottom_current} {bottom_next} {top_next}\n"
                        )

                        obj_file.write(
                            f"f {bottom_current} {top_next} {top_current}\n"
                        )

                        obj_file.write(
                            f"f {bottom_center} {bottom_next} {bottom_current}\n"
                        )

                        obj_file.write(
                            f"f {top_center} {top_current} {top_next}\n"
                        )

                    vertex_offset += 2 * sides + 2

            # -------------------------------------------------
            # PANELES
            # -------------------------------------------------

            obj_file.write("\nusemtl panel_material\n")

            for group in post_groups:
                if len(group) < 2:
                    continue

                first = np.array(group[0][:2], dtype=float)
                last = np.array(group[-1][:2], dtype=float)

                row_vector = last - first
                row_length = float(np.linalg.norm(row_vector))

                if row_length <= 0.0:
                    continue

                row_unit = row_vector / row_length
                yaw = math.atan2(row_unit[1], row_unit[0])

                row_center = (first + last) / 2.0
                axis_z = max(point[2] for point in group) + post_height

                module_pitch = module_length + module_gap
                module_count = max(1, int(row_length / module_pitch))

                first_offset = -(module_count - 1) * module_pitch / 2.0

                for module_index in range(module_count):
                    offset = first_offset + module_index * module_pitch

                    module_x = row_center[0] + offset * row_unit[0]
                    module_y = row_center[1] + offset * row_unit[1]
                    module_z = axis_z + module_thickness / 2.0

                    vertex_offset = cls._write_obj_box(
                        obj_file=obj_file,
                        center=(module_x, module_y, module_z),
                        length=module_length,
                        width=module_width,
                        height=module_thickness,
                        yaw=yaw,
                        vertex_offset=vertex_offset,
                    )

        return obj_path.resolve()


    @classmethod
    def _export_route_obj(
        cls,
        route_points: list[tuple[float, float, float]],
        output_directory: Path,
    ) -> Path:
        if len(route_points) < 2:
            raise ValueError(
                "La ruta debe contener al menos dos puntos."
            )

        route_directory = output_directory / "gazebo_route"
        route_directory.mkdir(parents=True, exist_ok=True)

        obj_path = route_directory / "work_route.obj"
        mtl_path = route_directory / "work_route.mtl"

        filtered_points: list[tuple[float, float, float]] = []

        for point in route_points:
            if not filtered_points:
                filtered_points.append(point)
                continue

            previous = np.array(filtered_points[-1][:2], dtype=float)
            current = np.array(point[:2], dtype=float)

            if np.linalg.norm(current - previous) > 1e-6:
                filtered_points.append(point)

        if len(filtered_points) < 2:
            raise ValueError(
                "La ruta no contiene suficientes puntos diferentes."
            )

        half_width = cls.GAZEBO_ROUTE_WIDTH / 2.0

        with mtl_path.open("w", encoding="utf-8") as mtl_file:
            mtl_file.write("newmtl route_material\n")
            mtl_file.write("Ka 1.00 0.85 0.05\n")
            mtl_file.write("Kd 1.00 0.85 0.05\n")
            mtl_file.write("Ks 0.05 0.05 0.05\n")
            mtl_file.write("Ns 5.0\n")
            mtl_file.write("d 1.0\n")

        with obj_path.open("w", encoding="utf-8") as obj_file:
            obj_file.write("mtllib work_route.mtl\n")
            obj_file.write("usemtl route_material\n")
            obj_file.write("o work_route\n\n")

            for index, (x, y, z) in enumerate(filtered_points):
                current = np.array((x, y), dtype=float)

                if index == 0:
                    next_point = np.array(filtered_points[index + 1][:2], dtype=float)
                    tangent = next_point - current

                elif index == len(filtered_points) - 1:
                    previous_point = np.array(filtered_points[index - 1][:2], dtype=float)
                    tangent = current - previous_point

                else:
                    previous_point = np.array(filtered_points[index - 1][:2], dtype=float)
                    next_point = np.array(filtered_points[index + 1][:2], dtype=float)
                    tangent = next_point - previous_point

                tangent_length = np.linalg.norm(tangent)

                if tangent_length <= 1e-9:
                    raise ValueError(
                        "No se pudo calcular la dirección de un tramo de ruta."
                    )

                tangent /= tangent_length

                lateral = np.array(
                    (-tangent[1], tangent[0]),
                    dtype=float,
                )

                left = current + lateral * half_width
                right = current - lateral * half_width
                route_z = z + cls.GAZEBO_ROUTE_Z_OFFSET

                obj_file.write(
                    f"v {left[0]:.6f} {left[1]:.6f} {route_z:.6f}\n"
                )

                obj_file.write(
                    f"v {right[0]:.6f} {right[1]:.6f} {route_z:.6f}\n"
                )

            obj_file.write("\n")

            for index in range(len(filtered_points) - 1):
                left_current = 2 * index + 1
                right_current = left_current + 1
                left_next = left_current + 2
                right_next = left_current + 3

                obj_file.write(
                    f"f {left_current} {right_current} {left_next}\n"
                )

                obj_file.write(
                    f"f {right_current} {right_next} {left_next}\n"
                )

        return obj_path.resolve()


    @classmethod
    def _export_dockout_route_obj(
        cls,
        dockout_points: list[tuple[float, float, float]],
        output_directory: Path,
    ) -> Path:
        if len(dockout_points) < 2:
            raise ValueError(
                "La ruta Dock Out debe contener al menos dos puntos."
            )

        route_directory = output_directory / "gazebo_route"
        route_directory.mkdir(parents=True, exist_ok=True)

        obj_path = route_directory / "dockout_route.obj"
        mtl_path = route_directory / "dockout_route.mtl"

        half_width = cls.GAZEBO_DOCKOUT_WIDTH / 2.0
        dash_length = cls.GAZEBO_DOCKOUT_DASH_LENGTH
        gap_length = cls.GAZEBO_DOCKOUT_GAP
        pattern_length = dash_length + gap_length

        with mtl_path.open("w", encoding="utf-8") as mtl_file:
            mtl_file.write("newmtl dockout_material\n")
            mtl_file.write("Ka 0.05 0.25 1.00\n")
            mtl_file.write("Kd 0.05 0.25 1.00\n")
            mtl_file.write("Ks 0.05 0.05 0.05\n")
            mtl_file.write("Ns 5.0\n")
            mtl_file.write("d 1.0\n")

        with obj_path.open("w", encoding="utf-8") as obj_file:
            obj_file.write("mtllib dockout_route.mtl\n")
            obj_file.write("usemtl dockout_material\n")
            obj_file.write("o dockout_route\n\n")

            vertex_offset = 1

            for segment_index in range(len(dockout_points) - 1):
                x0, y0, z0 = dockout_points[segment_index]
                x1, y1, z1 = dockout_points[segment_index + 1]

                start_xy = np.array((x0, y0), dtype=float)
                end_xy = np.array((x1, y1), dtype=float)

                segment = end_xy - start_xy
                segment_length = float(np.linalg.norm(segment))

                if segment_length <= 1e-9:
                    continue

                direction = segment / segment_length

                lateral = np.array(
                    (-direction[1], direction[0]),
                    dtype=float,
                )

                distance = 0.0

                while distance < segment_length:
                    dash_start_distance = distance
                    dash_end_distance = min(
                        distance + dash_length,
                        segment_length,
                    )

                    start_factor = dash_start_distance / segment_length
                    end_factor = dash_end_distance / segment_length

                    dash_start = start_xy + direction * dash_start_distance
                    dash_end = start_xy + direction * dash_end_distance

                    dash_start_z = z0 + (z1 - z0) * start_factor + cls.GAZEBO_ROUTE_Z_OFFSET
                    dash_end_z = z0 + (z1 - z0) * end_factor + cls.GAZEBO_ROUTE_Z_OFFSET

                    start_left = dash_start + lateral * half_width
                    start_right = dash_start - lateral * half_width
                    end_left = dash_end + lateral * half_width
                    end_right = dash_end - lateral * half_width

                    obj_file.write(
                        f"v {start_left[0]:.6f} {start_left[1]:.6f} {dash_start_z:.6f}\n"
                    )

                    obj_file.write(
                        f"v {start_right[0]:.6f} {start_right[1]:.6f} {dash_start_z:.6f}\n"
                    )

                    obj_file.write(
                        f"v {end_left[0]:.6f} {end_left[1]:.6f} {dash_end_z:.6f}\n"
                    )

                    obj_file.write(
                        f"v {end_right[0]:.6f} {end_right[1]:.6f} {dash_end_z:.6f}\n"
                    )

                    obj_file.write(
                        f"f {vertex_offset} {vertex_offset + 1} {vertex_offset + 2}\n"
                    )

                    obj_file.write(
                        f"f {vertex_offset + 1} {vertex_offset + 3} {vertex_offset + 2}\n"
                    )

                    vertex_offset += 4
                    distance += pattern_length

        return obj_path.resolve()


    @classmethod
    def _add_dockout_route_mesh(
        cls,
        world: ET.Element,
    ) -> None:
        model = ET.SubElement(
            world,
            "model",
            {
                "name": "generated_dockout_route",
            },
        )

        ET.SubElement(
            model,
            "static",
        ).text = "true"

        ET.SubElement(
            model,
            "pose",
        ).text = "0 0 0 0 0 0"

        link = ET.SubElement(
            model,
            "link",
            {
                "name": "dockout_route_link",
            },
        )

        visual = ET.SubElement(
            link,
            "visual",
            {
                "name": "dockout_route_visual",
            },
        )

        geometry = ET.SubElement(
            visual,
            "geometry",
        )

        mesh = ET.SubElement(
            geometry,
            "mesh",
        )

        ET.SubElement(
            mesh,
            "uri",
        ).text = "gazebo_route/dockout_route.obj"

        ET.SubElement(
            mesh,
            "scale",
        ).text = "1 1 1"

    @classmethod
    def _add_simple_route_robot(
        cls,
        world: ET.Element,
        home_position: tuple[float, float, float],
        dockout_points: list[tuple[float, float, float]] | None = None,
    ) -> None:
        x, y, terrain_z = home_position

        yaw = 0.0

        if dockout_points and len(dockout_points) >= 2:
            target_x, target_y, _ = dockout_points[1]

            delta_x = target_x - x
            delta_y = target_y - y

            if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6:
                yaw = math.atan2(
                    delta_y,
                    delta_x,
                )

        include = ET.SubElement(
            world,
            "include",
        )

        ET.SubElement(
            include,
            "uri",
        ).text = "model://simple_route_robot"

        ET.SubElement(
            include,
            "name",
        ).text = "simple_route_robot"

        ET.SubElement(
            include,
            "pose",
        ).text = cls._pose_text(
            x,
            y,
            terrain_z + 0.05,
            0.0,
            0.0,
            yaw,
        )
