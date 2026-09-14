import csv
import numpy as np
import pyqtgraph.opengl as gl

from renderers.solar_structure_renderer import (
    SolarStructureRenderBundle,
    SolarStructureRenderer,
)

from renderers.home_renderer import HomeRenderer

from world.solar_structure import SolarStructure

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from ui.editor_page import EditorPage
from world.wall import Wall
from world.world_project import WorldProject

from renderers.terrain_renderer import TerrainRenderer
from renderers.structure_points_renderer import (
    StructurePointsRenderer,
)
from services.geotiff_reader import GeoTiffReader

from services.work_route_generator import WorkRouteGenerator

class EditorController(QObject):
    """
    Controlador de las operaciones realizadas dentro del editor.

    Sus responsabilidades actuales son:

    - Añadir muros al proyecto.
    - Crear su representación en la escena 3D.
    - Seleccionar objetos.
    - Modificar sus propiedades.
    - Eliminar objetos.

    La interfaz no modifica directamente el modelo del mundo.
    """

    def __init__(self,editor_page: EditorPage,) -> None:
        super().__init__(editor_page)

        self.editor_page = editor_page
        self.project: WorldProject | None = None

        # Relaciona cada object_id con su objeto gráfico.
        self.scene_items: dict[
            str,
            tuple[object, ...],
        ] = {}

        self.terrain_scene_item = None

        self.terrain_info = None
        self.terrain_elevation_data: np.ndarray | None = None

        self.home_ray_scene_item = None
        self.home_preview_scene_item = None

        self.home_scene_items: tuple[object, ...] = ()

        self.structure_points_scene_item = None
        self.structure_points: list[tuple[float, float, float]] = []
        self.structure_point_groups: list[
            list[tuple[float, float, float]]
        ] = []

        self._configure_connections()

        self.home_position: tuple[float, float, float] | None = None

        self.perimeter_points: list[tuple[float, float, float]] = []
        self.perimeter_scene_items: list[object] = []

        self.perimeter_finalized = False

        self.dockout_points: list[tuple[float, float, float]] = []
        self.dockout_scene_items: list[object] = []
        self.dockout_preview_scene_item = None

        self.work_x_direction: np.ndarray | None = None
        self.work_y_direction: np.ndarray | None = None
        self.work_direction_preview_scene_item = None
        self.work_direction_scene_items: list[object] = []

        self.work_route_scene_items: list[object] = []

        self.work_route_points: list[tuple[float, float, float]] = []

    # =========================================================
    # CONEXIÓN CON LA INTERFAZ
    # =========================================================

    def _configure_connections(self) -> None:
        self.editor_page.add_object_requested.connect(
            self.add_object
        )

        self.editor_page.delete_object_requested.connect(
            self.delete_object
        )

        self.editor_page.import_structure_points_requested.connect(
            self.import_structure_points
        )

        self.editor_page.object_selected.connect(
            self.select_object
        )

        self.editor_page.object_properties_edited.connect(
            self.update_object
        )

        self.editor_page.home_scene_clicked.connect(self._select_home_from_scene)
        self.editor_page.home_scene_hovered.connect(self._preview_home_from_scene)

        self.editor_page.perimeter_scene_clicked.connect(self._add_perimeter_point_from_scene)
        self.editor_page.perimeter_scene_hovered.connect(self._preview_perimeter_from_scene)
        self.editor_page.finalize_perimeter_requested.connect(self._finalize_perimeter)
        self.editor_page.clear_perimeter_requested.connect(self._clear_perimeter)

        self.editor_page.start_dockout_requested.connect(self._start_dockout)
        self.editor_page.dockout_scene_clicked.connect(self._add_dockout_point_from_scene)
        self.editor_page.dockout_scene_hovered.connect(self._preview_dockout_from_scene)
        self.editor_page.finalize_dockout_requested.connect(self._finalize_dockout)

        self.editor_page.start_work_route_requested.connect(self._start_work_route)
        self.editor_page.work_direction_scene_clicked.connect(self._set_work_direction_from_scene)
        self.editor_page.work_direction_scene_hovered.connect(self._preview_work_direction)

        self.editor_page.cancel_work_route_requested.connect(self._cancel_work_route_selection)

    # =========================================================
    # CONFIGURACIÓN DEL PROYECTO
    # =========================================================

    def set_project(
        self,
        project: WorldProject,
    ) -> None:
        """
        Establece el proyecto que se editará.
        """

        self._clear_scene_objects()
        self._clear_terrain()
        self.editor_page.clear_world_objects()

        self.project = project

        if (
            project.creation_mode == "terrain"
            and project.terrain_path
        ):
            self._load_project_terrain()

        for world_object in project.get_all_objects():
            self._add_existing_object_to_scene(
                world_object
            )

        self.editor_page.set_status_message(
            f"Proyecto '{project.name}' preparado. "
            f"Objetos: {project.object_count()}."
        )

    def _load_project_terrain(self) -> None:
        """
        Lee el DEM asociado al proyecto y genera
        su representación tridimensional.
        """

        if (
            self.project is None
            or not self.project.terrain_path
        ):
            return

        try:
            terrain_info = GeoTiffReader.read_info(
                self.project.terrain_path
            )

            elevation_data, _ = (GeoTiffReader.read_local_elevation_data(self.project.terrain_path))

            self.terrain_info = terrain_info
            self.terrain_elevation_data = elevation_data

            terrain_item = TerrainRenderer.create(
                elevation_data=elevation_data,
                resolution_x=terrain_info.resolution_x,
                resolution_y=terrain_info.resolution_y,
            )

        except (
            OSError,
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self.editor_page,
                "Error al cargar terreno",
                str(error),
            )
            return

        self.terrain_scene_item = terrain_item

        self.editor_page.add_scene_item(
            terrain_item
        )

    def _terrain_height_at(self, x: float, y: float) -> float:
        if self.terrain_info is None or self.terrain_elevation_data is None:
            raise ValueError("No hay un terreno cargado.")

        data = self.terrain_elevation_data
        rows, columns = data.shape

        resolution_x = self.terrain_info.resolution_x
        resolution_y = self.terrain_info.resolution_y

        terrain_width = columns * resolution_x
        terrain_length = rows * resolution_y

        # Convertir X,Y locales a coordenadas fraccionarias
        # de columna y fila del DEM.
        column = (x + terrain_width / 2.0) / resolution_x - 0.5
        row = rows - 0.5 - (y + terrain_length / 2.0) / resolution_y

        if column < 0.0 or column > columns - 1 or row < 0.0 or row > rows - 1:
            raise ValueError("El punto se encuentra fuera del terreno.")

        column_0 = int(np.floor(column))
        row_0 = int(np.floor(row))

        column_1 = min(column_0 + 1, columns - 1)
        row_1 = min(row_0 + 1, rows - 1)

        fraction_x = column - column_0
        fraction_y = row - row_0

        z00 = float(data[row_0, column_0])
        z10 = float(data[row_0, column_1])
        z01 = float(data[row_1, column_0])
        z11 = float(data[row_1, column_1])

        if np.isnan([z00, z10, z01, z11]).any():
            raise ValueError("El punto corresponde a una zona sin datos del terreno.")

        z_top = z00 * (1.0 - fraction_x) + z10 * fraction_x
        z_bottom = z01 * (1.0 - fraction_x) + z11 * fraction_x

        return z_top * (1.0 - fraction_y) + z_bottom * fraction_y

    def _select_home_from_scene(self, screen_x: float, screen_y: float) -> None:
        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            home_position = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError) as error:
            QMessageBox.warning(self.editor_page, "Punto Home no válido", str(error))
            return

        x, y, z = home_position

        self.home_position = (x, y, z)
        self._update_navigation_availability()
        self.editor_page.set_home_coordinates(x, y, z)

        self._clear_home_scene()

        if self.home_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.home_preview_scene_item)
            self.home_preview_scene_item = None

        self.home_scene_items = HomeRenderer.create(x, y, z)

        for scene_item in self.home_scene_items:
            self.editor_page.add_scene_item(scene_item)

        if self.home_ray_scene_item is not None:
            self.editor_page.remove_scene_item(self.home_ray_scene_item)
            self.home_ray_scene_item = None

            self.editor_page.set_status_message(
                f"Home seleccionado: X={x:.3f} m | Y={y:.3f} m | Z={z:.3f} m"
            )

    def _preview_home_from_scene(self, screen_x: float, screen_y: float) -> None:
        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            home_position = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError):
            return

        hit_point = np.array(home_position, dtype=np.float32)

        ray_positions = np.array(
            [
                ray_origin,
                hit_point,
            ],
            dtype=np.float32,
        )

        if self.home_ray_scene_item is None:
            self.home_ray_scene_item = gl.GLLinePlotItem(
                pos=ray_positions,
                color=(0.9, 0.3, 0.1, 1.0),
                width=2.0,
                antialias=True,
                mode="lines",
            )

            self.editor_page.add_scene_item(self.home_ray_scene_item)

        else:
            self.home_ray_scene_item.setData(pos=ray_positions)

        preview_position = np.array(
            [
                 [
                    hit_point[0],
                    hit_point[1],
                    hit_point[2] + 0.5,
                ]
            ],
            dtype=np.float32,
        )

        if self.home_preview_scene_item is None:
            self.home_preview_scene_item = gl.GLScatterPlotItem(
                pos=preview_position,
                size=10.0,
                color=(0.9, 0.3, 0.1, 1.0),
                pxMode=True,
            )

            self.editor_page.add_scene_item(self.home_preview_scene_item)

        else:
            self.home_preview_scene_item.setData(pos=preview_position)

    def _intersect_ray_with_terrain(
        self,
        ray_origin: np.ndarray,
        ray_direction: np.ndarray,
    ) -> tuple[float, float, float]:
        if self.terrain_info is None or self.terrain_elevation_data is None:
            raise ValueError("No hay un terreno cargado.")

        terrain_width = self.project.width
        terrain_length = self.project.length

        x_min = -terrain_width / 2.0
        x_max = terrain_width / 2.0
        y_min = -terrain_length / 2.0
        y_max = terrain_length / 2.0

        step = 2.0
        maximum_distance = 10000.0

        previous_point = None
        previous_difference = None

        distance = 0.0

        while distance <= maximum_distance:
            point = ray_origin + ray_direction * distance

            x = float(point[0])
            y = float(point[1])
            z = float(point[2])

            if x_min <= x <= x_max and y_min <= y <= y_max:
                terrain_z = self._terrain_height_at(x, y)
                difference = z - terrain_z

                if previous_difference is not None and previous_difference > 0.0 and difference <= 0.0:
                    low = distance - step
                    high = distance

                    for _ in range(20):
                        middle = (low + high) / 2.0
                        middle_point = ray_origin + ray_direction * middle

                        middle_x = float(middle_point[0])
                        middle_y = float(middle_point[1])
                        middle_z = float(middle_point[2])

                        terrain_z = self._terrain_height_at(middle_x, middle_y)

                        if middle_z > terrain_z:
                            low = middle
                        else:
                            high = middle

                    final_distance = (low + high) / 2.0
                    final_point = ray_origin + ray_direction * final_distance

                    final_x = float(final_point[0])
                    final_y = float(final_point[1])
                    final_z = self._terrain_height_at(final_x, final_y)

                    return final_x, final_y, final_z

                previous_point = point
                previous_difference = difference

            distance += step

        raise ValueError("No se encontró una intersección entre el clic y el terreno.")


    def _clear_terrain(self) -> None:
        """
        Elimina el terreno actualmente mostrado
        en la escena.
        """

        if self.terrain_scene_item is None:
            return

        self.editor_page.remove_scene_item(
            self.terrain_scene_item
        )

        self.terrain_scene_item = None

        self.terrain_info = None
        self.terrain_elevation_data = None

    # =========================================================
    # IMPORTACIÓN DE PUNTOS DE ESTRUCTURAS
    # =========================================================

    def import_structure_points(self) -> None:
        """
        Importa desde CSV las coordenadas UTM de los postes
        y las representa sobre el terreno.

        Formato esperado del CSV:

            ID, Northing, Easting, ...

        Ejemplo:

            1,4507950.2629,378196.8329,-
        """

        if (self.project is None or not self.project.terrain_path):
            QMessageBox.warning(
                self.editor_page,
                "Terreno requerido",
                "Debe cargar un terreno antes de "
                "importar las coordenadas de los postes.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.editor_page,
            "Importar coordenadas de postes",
            "",
            "Archivos CSV (*.csv);;Todos los archivos (*)",
        )

        if not file_path:
            return

        utm_points: list[
            tuple[float, float]
        ] = []

        utm_groups: list[
            list[tuple[float, float]]
        ] = []

        current_group: list[
            tuple[float, float]
        ] = []

        current_easting: float | None = None

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:

                reader = csv.reader(csv_file)

                for line_number, row in enumerate(
                    reader,
                    start=1,
                ):
                    # Ignorar líneas vacías.
                    if not row:
                        continue

                    if len(row) < 3:
                        raise ValueError(
                            f"La línea {line_number} del CSV "
                            f"no contiene al menos 3 columnas."
                        )

                    try:
                        northing = float(
                            row[1].strip()
                        )

                        easting = float(
                            row[2].strip()
                        )

                    except ValueError as error:
                        raise ValueError(
                            f"Coordenadas no válidas en "
                            f"la línea {line_number}: {row}"
                        ) from error

                    # ---------------------------------------------
                    # Detectar grupos consecutivos de postes.
                    #
                    # Cada grupo mantiene aproximadamente el mismo
                    # Easting y representa una fila fotovoltaica.
                    # ---------------------------------------------
                    if current_easting is None:
                        current_easting = easting

                    elif abs(
                        easting - current_easting
                    ) > 1e-6:
                        if current_group:
                            utm_groups.append(
                                current_group
                            )

                        current_group = []
                        current_easting = easting

                    point = ( easting, northing,)

                    current_group.append(point)

                    utm_points.append(point)

                if current_group:
                    utm_groups.append(current_group)

            if not utm_points:
                raise ValueError(
                    "El archivo CSV no contiene puntos válidos."
                )

            # ---------------------------------------------
            # Convertir todos los puntos UTM a nuestro
            # sistema local X,Y,Z.
            # ---------------------------------------------
            local_points = (
                GeoTiffReader.utm_points_to_local_coordinates(
                    self.project.terrain_path,
                    utm_points,
                )
            )

            self.structure_points = list(
                local_points
            )

            self.structure_point_groups = []

            point_index = 0

            for utm_group in utm_groups:
                group_size = len(
                    utm_group
                )

                local_group = list(
                    local_points[
                        point_index:
                        point_index + group_size
                    ]
                )

                self.structure_point_groups.append(local_group)

                point_index += group_size
            # ---------------------------------------------
            # Eliminar puntos previamente importados.
            # ---------------------------------------------
            if (
                self.structure_points_scene_item
                is not None
            ):
                self.editor_page.remove_scene_item(
                    self.structure_points_scene_item
                )

                self.structure_points_scene_item = None

            # ---------------------------------------------
            # Crear los marcadores 3D.
            # ---------------------------------------------
            points_item = (
                StructurePointsRenderer.create_points(
                    local_points
                )
            )

            self.structure_points_scene_item = (
                points_item
            )

            self.editor_page.add_scene_item(
                points_item
            )

        except (
            OSError,
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self.editor_page,
                "Error al importar CSV",
                str(error),
            )
            return

        if self.editor_page.should_generate_solar_structures():
            for row_index, post_group in enumerate(self.structure_point_groups, start=1):
                self._add_imported_tracker_row(post_group, row_index)

            message = f"Postes: {len(local_points)} | Seguidores: {len(self.structure_point_groups)}"
        else:
            message = f"Postes: {len(local_points)} | Estructuras solares: desactivadas"

        self.editor_page.set_status_message(message)

        if self.editor_page.should_generate_solar_structures():
            for row_index, post_group in enumerate(self.structure_point_groups, start=1):
                self._add_imported_tracker_row(post_group, row_index)



    def _add_imported_tracker_row(
        self,
        post_points: list[tuple[float, float, float]],
        row_index: int,
    ) -> None:
        if self.project is None:
            return

        structure_name = self.project.generate_unique_name(
            f"tracker_importado_{row_index}"
        )

        structure = SolarStructure(
            name=structure_name,
            structure_type="single_row_tracker",
            post_count=len(post_points),
            post_points=list(post_points),
            tracker_angle=0.0,
        )

        self.project.add_object(structure)

        try:
            render_bundle = SolarStructureRenderer.create_from_post_points(
                structure
            )

        except Exception:
            self.project.remove_object(structure.object_id)
            raise

        self._add_scene_items(
            object_id=structure.object_id,
            scene_items=render_bundle.items,
        )

        self.editor_page.add_world_object(
            object_id=structure.object_id,
            display_name=structure.name,
        )

    def _require_project(self) -> bool:
        if self.project is not None:
            return True

        QMessageBox.warning(
            self.editor_page,
            "Proyecto no disponible",
            "No existe un proyecto activo en el editor.",
        )

        return False

    # =========================================================
    # CREACIÓN DE OBJETOS
    # =========================================================

    def add_object(
        self,
        object_type: str,
    ) -> None:
        if not self._require_project():
            return

        if object_type == "wall":
            self._add_wall()
            return

        solar_structure_types = {
            "solar_fixed": "fixed",
            "solar_single_row_tracker": (
                "single_row_tracker"
            ),
            "solar_dual_row_tracker": (
                "dual_row_tracker"
            ),
        }

        structure_type = solar_structure_types.get(
            object_type
        )

        if structure_type is not None:
            self._add_solar_structure(
                structure_type
            )
            return

        QMessageBox.information(
            self.editor_page,
            "Objeto no implementado",
            f"El tipo de objeto '{object_type}' "
            "todavía no está disponible.",
        )

    def _add_wall(self) -> None:
        assert self.project is not None

        wall_name = self.project.generate_unique_name(
            "muro"
        )

        wall = Wall(
            name=wall_name,
            x=0.0,
            y=0.0,
            z=1.0,
            length=5.0,
            thickness=0.20,
            height=2.0,
        )

        try:
            self.project.add_object(wall)

        except ValueError as error:
            QMessageBox.warning(
                self.editor_page,
                "No se pudo añadir el muro",
                str(error),
            )
            return

        scene_item = self._create_wall_scene_item(
            wall
        )
 
        self._add_scene_items(
            object_id=wall.object_id,
            scene_items=(scene_item,),
        )

        self.editor_page.add_world_object(
            object_id=wall.object_id,
            display_name=wall.name,
        )

        self.editor_page.set_property_values(
            object_id=wall.object_id,
            object_type=wall.object_type,
            properties=wall.to_dict(),
        )

        self.editor_page.set_status_message(
            f"Se añadió el muro '{wall.name}'."
        )

    def _add_solar_structure(
        self,
        structure_type: str,
    ) -> None:
        assert self.project is not None

        name_prefixes = {
            "fixed": "estructura_fija",
            "single_row_tracker": "seguidor_mono_fila",
            "dual_row_tracker": "seguidor_dual_row",
        }

        display_names = {
            "fixed": "estructura fotovoltaica fija",
            "single_row_tracker": (
                "seguidor mono-fila de un eje"
            ),
            "dual_row_tracker": (
                "seguidor dual-row de un eje"
            ),
        }

        if structure_type not in name_prefixes:
            QMessageBox.warning(
                self.editor_page,
                "Tipo de estructura no válido",
                f"El tipo '{structure_type}' no está disponible.",
            )
            return

        structure_name = (
            self.project.generate_unique_name(
                name_prefixes[structure_type]
            )
        )

        structure = SolarStructure(
            name=structure_name,
            structure_type=structure_type,
            x=0.0,
            y=0.0,
            z=0.0,
        )

        try:
            self.project.add_object(structure)

        except ValueError as error:
            QMessageBox.warning(
                self.editor_page,
                "No se pudo añadir la estructura",
                str(error),
            )
            return

        try:
            render_bundle = (
                SolarStructureRenderer.create(
                    structure
                )
            )

        except Exception as error:
            self.project.remove_object(
                structure.object_id
            )

            QMessageBox.critical(
                self.editor_page,
                "Error de representación 3D",
                "No se pudo crear la representación "
                f"gráfica de la estructura:\n{error}",
            )
            return

        self._add_scene_items(
            object_id=structure.object_id,
            scene_items=render_bundle.items,
        )

        self.editor_page.add_world_object(
            object_id=structure.object_id,
            display_name=structure.name,
        )

        self.editor_page.set_property_values(
            object_id=structure.object_id,
            object_type=structure.object_type,
            properties=structure.to_dict(),
        )

        self.editor_page.set_status_message(
            f"Se añadió la {display_names[structure_type]} "
            f"'{structure.name}'."
        )

    def _add_existing_object_to_scene(
        self,
        world_object,
    ) -> None:
        if world_object.object_type == "wall":
            wall_item = self._create_wall_scene_item(
                world_object
            )

            scene_items = (
                wall_item,
            )

        elif world_object.object_type == "solar_structure":
            render_bundle = (
                SolarStructureRenderer.create(
                    world_object
                )
            )

            scene_items = render_bundle.items

        else:
            return

        self._add_scene_items(
            object_id=world_object.object_id,
            scene_items=scene_items,
        )

        self.editor_page.add_world_object(
            object_id=world_object.object_id,
            display_name=world_object.name,
        )

    # =========================================================
    # SELECCIÓN DE OBJETOS
    # =========================================================

    def select_object(
        self,
        object_id: str,
    ) -> None:
        if not self._require_project():
            return

        assert self.project is not None

        try:
            world_object = self.project.get_object(
                object_id
            )

        except KeyError:
            self.editor_page.clear_property_values()
            return

        self.editor_page.set_property_values(
            object_id=world_object.object_id,
            object_type=world_object.object_type,
            properties=world_object.to_dict(),
        )

        self.editor_page.set_status_message(
            f"Objeto seleccionado: "
            f"'{world_object.name}'."
        )

    # =========================================================
    # MODIFICACIÓN DE OBJETOS
    # =========================================================

    def update_object(
        self,
        object_id: str,
        properties: dict,
    ) -> None:
        if not self._require_project():
            return

        assert self.project is not None

        new_x = float(properties.get("x", 0.0))
        new_y = float(properties.get("y", 0.0))

        if not self.project.is_position_inside_terrain(
            new_x,
            new_y,
        ):
            QMessageBox.warning(
                self.editor_page,
                "Posición fuera del terreno",
                "La posición X-Y del objeto debe estar "
                "dentro de los límites del terreno.",
            )

            self.select_object(object_id)
            return

        try:
            world_object = self.project.update_object(
                object_id,
                properties,
            )

        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(
                self.editor_page,
                "Propiedades no válidas",
                str(error),
            )

            self.select_object(object_id)
            return

        self._replace_scene_item(
            world_object
        )

        self.editor_page.update_world_object_name(
            object_id=world_object.object_id,
            new_name=world_object.name,
        )

        self.editor_page.set_property_values(
            object_id=world_object.object_id,
            object_type=world_object.object_type,
            properties=world_object.to_dict(),
        )

        self.editor_page.set_status_message(
            f"Se actualizó el objeto "
            f"'{world_object.name}'."
        )

    def _replace_scene_item(
        self,
        world_object,
    ) -> None:
        """
        Reconstruye la representación gráfica de un objeto
        después de modificar sus propiedades.
        """

        try:
            if world_object.object_type == "wall":
                new_scene_items = (
                    self._create_wall_scene_item(
                        world_object
                    ),
                )

            elif (
                world_object.object_type
                == "solar_structure"
            ):
                render_bundle = (
                    SolarStructureRenderer.create(
                        world_object
                    )
                )

                new_scene_items = (
                    render_bundle.items
                )

            else:
                return

        except Exception as error:
            QMessageBox.critical(
                self.editor_page,
                "Error de representación 3D",
                "No se pudo actualizar la representación "
                f"gráfica del objeto:\n{error}",
            )
            return

        self._remove_scene_items(
            world_object.object_id
        )

        self._add_scene_items(
            object_id=world_object.object_id,
            scene_items=new_scene_items,
        )
    # =========================================================
    # ELIMINACIÓN DE OBJETOS
    # =========================================================

    def delete_object(
        self,
        object_id: str,
    ) -> None:
        if not self._require_project():
            return

        assert self.project is not None

        try:
            removed_object = self.project.remove_object(
                object_id
            )

        except KeyError as error:
            QMessageBox.warning(
                self.editor_page,
                "No se pudo eliminar el objeto",
                str(error),
            )
            return

        self._remove_scene_items(
            object_id
        )


        self.editor_page.remove_world_object(
            object_id
        )

        self.editor_page.set_status_message(
            f"Se eliminó el objeto "
            f"'{removed_object.name}'."
        )

    # =========================================================
    # GESTIÓN DE ELEMENTOS GRÁFICOS
    # =========================================================

    def _add_scene_items(
        self,
        object_id: str,
        scene_items: tuple[object, ...],
    ) -> None:
        """
        Registra y añade a la escena todos los elementos gráficos
        pertenecientes a un objeto del mundo.
        """

        self.scene_items[object_id] = scene_items

        for scene_item in scene_items:
            self.editor_page.add_scene_item(
                scene_item
            )

    def _remove_scene_items(
        self,
        object_id: str,
    ) -> None:
        """
        Elimina de la escena todos los elementos gráficos
        asociados a un objeto.
        """

        scene_items = self.scene_items.pop(
            object_id,
            (),
        )

        for scene_item in scene_items:
            self.editor_page.remove_scene_item(
                scene_item
            )


    # =========================================================
    # REPRESENTACIÓN GRÁFICA DEL MURO
    # =========================================================

    def _create_wall_scene_item(
        self,
        wall: Wall,
    ) -> gl.GLMeshItem:
        length, thickness, height = (
            wall.get_scaled_dimensions()
        )

        half_length = length / 2.0
        half_thickness = thickness / 2.0
        half_height = height / 2.0

        vertices = np.array(
            [
                [
                    -half_length,
                    -half_thickness,
                    -half_height,
                ],
                [
                    half_length,
                    -half_thickness,
                    -half_height,
                ],
                [
                    half_length,
                    half_thickness,
                    -half_height,
                ],
                [
                    -half_length,
                    half_thickness,
                    -half_height,
                ],
                [
                    -half_length,
                    -half_thickness,
                    half_height,
                ],
                [
                    half_length,
                    -half_thickness,
                    half_height,
                ],
                [
                    half_length,
                    half_thickness,
                    half_height,
                ],
                [
                    -half_length,
                    half_thickness,
                    half_height,
                ],
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

        rotation_matrix = (
            self._create_rotation_matrix(
                roll_degrees=wall.roll,
                pitch_degrees=wall.pitch,
                yaw_degrees=wall.yaw,
            )
        )

        vertices = vertices @ rotation_matrix.T

        vertices += np.array(
            [
                wall.x,
                wall.y,
                wall.z,
            ],
            dtype=float,
        )

        mesh_data = gl.MeshData(
            vertexes=vertices,
            faces=faces,
        )

        wall_item = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            shader="shaded",
            color=(0.68, 0.68, 0.72, 1.0),
            drawEdges=True,
            edgeColor=(0.15, 0.15, 0.18, 1.0),
        )

        return wall_item

    @staticmethod
    def _create_rotation_matrix(
        roll_degrees: float,
        pitch_degrees: float,
        yaw_degrees: float,
    ) -> np.ndarray:
        roll = np.radians(roll_degrees)
        pitch = np.radians(pitch_degrees)
        yaw = np.radians(yaw_degrees)

        rotation_x = np.array(
            [
                [1, 0, 0],
                [
                    0,
                    np.cos(roll),
                    -np.sin(roll),
                ],
                [
                    0,
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
                    0,
                    np.sin(pitch),
                ],
                [0, 1, 0],
                [
                    -np.sin(pitch),
                    0,
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
                    0,
                ],
                [
                    np.sin(yaw),
                    np.cos(yaw),
                    0,
                ],
                [0, 0, 1],
            ],
            dtype=float,
        )

        return (
            rotation_z
            @ rotation_y
            @ rotation_x
        )

    # =========================================================
    # LIMPIEZA DEL EDITOR
    # =========================================================

    def _clear_scene_objects(self) -> None:
        """
        Elimina todos los componentes gráficos de todos
        los objetos presentes en la escena.
        """

        for scene_items in self.scene_items.values():
            for scene_item in scene_items:
                self.editor_page.remove_scene_item(
                    scene_item
                )

        self.scene_items.clear()

    def _clear_home_scene(self) -> None:
        for scene_item in self.home_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.home_scene_items = ()

    def _add_perimeter_point_from_scene(self, screen_x: float, screen_y: float) -> None:
        if len(self.perimeter_points) >= 10:
            QMessageBox.warning(
                self.editor_page,
                "Máximo de puntos alcanzado",
                "El perímetro puede contener como máximo 10 puntos.\n"
                "Pulse 'Borrar perímetro' para comenzar nuevamente.",
            )
            return

        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError) as error:
            QMessageBox.warning(self.editor_page, "Punto no válido", str(error))
            return

        self.perimeter_points.append(point)

        self.perimeter_finalized = False
        self._update_perimeter_scene()

        self.editor_page.set_status_message(
            f"Puntos de perímetro: {len(self.perimeter_points)} / 10"
        )

    def _preview_perimeter_from_scene(self, screen_x: float, screen_y: float) -> None:
        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError):
            return

        preview_position = np.array(
            [[point[0], point[1], point[2] + 0.5]],
            dtype=np.float32,
        )

        if self.home_preview_scene_item is None:
            self.home_preview_scene_item = gl.GLScatterPlotItem(
                pos=preview_position,
                size=10.0,
                color=(0.95, 0.65, 0.10, 1.0),
                pxMode=True,
            )
            self.editor_page.add_scene_item(self.home_preview_scene_item)
        else:
            self.home_preview_scene_item.setData(pos=preview_position)

    def _finalize_perimeter(self) -> None:
        if len(self.perimeter_points) < 3:
            QMessageBox.warning(
                self.editor_page,
                "Perímetro incompleto",
                "Debe seleccionar al menos 3 puntos para definir un perímetro.",
            )
            return

        self.perimeter_finalized = True

        self._update_navigation_availability()

        self._update_perimeter_scene()

        self.editor_page.set_status_message(f"Perímetro válido con {len(self.perimeter_points)} puntos.")


    def _clear_perimeter(self) -> None:
        self.perimeter_points.clear()

        self.perimeter_finalized = False

        self._update_navigation_availability()

        for scene_item in self.perimeter_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.perimeter_scene_items.clear()

        if self.home_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.home_preview_scene_item)
            self.home_preview_scene_item = None

        self.editor_page.set_status_message("Perímetro borrado.")

    def _update_perimeter_scene(self) -> None:
        for scene_item in self.perimeter_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.perimeter_scene_items.clear()

        if not self.perimeter_points:
            return

        point_positions = np.array(
            [
                (x, y, z + 0.8)
                for x, y, z in self.perimeter_points
            ],
            dtype=np.float32,
        )

        points_item = gl.GLScatterPlotItem(
            pos=point_positions,
            size=8.0,
            color=(0.95, 0.65, 0.10, 1.0),
            pxMode=True,
        )

        self.editor_page.add_scene_item(points_item)
        self.perimeter_scene_items.append(points_item)

        if len(self.perimeter_points) < 2:
            return

        line_positions = list(point_positions)

        if self.perimeter_finalized and len(self.perimeter_points) >= 3:
            line_positions.append(point_positions[0])

        line_positions = np.array(line_positions, dtype=np.float32)

        line_item = gl.GLLinePlotItem(
           pos=line_positions,
            color=(0.95, 0.65, 0.10, 1.0),
            width=3.0,
            antialias=True,
            mode="line_strip",
        )

        self.editor_page.add_scene_item(line_item)
        self.perimeter_scene_items.append(line_item)


    def _update_navigation_availability(self) -> None:
        navigation_ready = self.home_position is not None and self.perimeter_finalized
        self.editor_page.set_navigation_routes_enabled(navigation_ready)

    def _start_dockout(self) -> None:
        if self.home_position is None or not self.perimeter_finalized:
            QMessageBox.warning(
                self.editor_page,
                "Navegación no disponible",
                "Debe definir un Home y finalizar el perímetro antes de crear la ruta Dock Out.",
            )
            return

        for scene_item in self.dockout_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.dockout_scene_items.clear()

        if self.dockout_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.dockout_preview_scene_item)
            self.dockout_preview_scene_item = None

        self.dockout_points = [self.home_position]

        self._update_dockout_scene()

        self.editor_page.set_status_message(
            "Dock Out iniciado. WP0 corresponde al Home."
        )

    def _add_dockout_point_from_scene(self, screen_x: float, screen_y: float) -> None:
        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError) as error:
            QMessageBox.warning(self.editor_page, "Waypoint no válido", str(error))
            return

        self.dockout_points.append(point)
        self._update_dockout_scene()

        waypoint_index = len(self.dockout_points) - 1

        self.editor_page.set_status_message(
            f"Dock Out: WP{waypoint_index} añadido | Total: {len(self.dockout_points)} waypoints"
        )

    def _update_dockout_scene(self) -> None:
        for scene_item in self.dockout_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.dockout_scene_items.clear()

        if not self.dockout_points:
            return

        positions = np.array(
            [(x, y, z + 1.0) for x, y, z in self.dockout_points],
            dtype=np.float32,
        )

        points_item = gl.GLScatterPlotItem(
            pos=positions,
            size=7.0,
            color=(0.10, 0.35, 0.95, 1.0),
            pxMode=True,
        )

        self.editor_page.add_scene_item(points_item)
        self.dockout_scene_items.append(points_item)

        if len(self.dockout_points) < 2:
            return

        line_item = gl.GLLinePlotItem(
            pos=positions,
            color=(0.10, 0.35, 0.95, 1.0),
            width=3.0,
            antialias=True,
            mode="line_strip",
        )

        self.editor_page.add_scene_item(line_item)
        self.dockout_scene_items.append(line_item)


    def _preview_dockout_from_scene(self, screen_x: float, screen_y: float) -> None:
        if not self.dockout_points:
            return

        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError):
            return

        previous_point = self.dockout_points[-1]

        positions = np.array(
            [
                (previous_point[0], previous_point[1], previous_point[2] + 1.0),
                (point[0], point[1], point[2] + 1.0),
            ],
            dtype=np.float32,
        )

        if self.dockout_preview_scene_item is None:
            self.dockout_preview_scene_item = gl.GLLinePlotItem(
                pos=positions,
                color=(0.25, 0.55, 1.0, 0.75),
                width=2.0,
                antialias=True,
                mode="lines",
            )

            self.editor_page.add_scene_item(self.dockout_preview_scene_item)
        else:
            self.dockout_preview_scene_item.setData(pos=positions)


    def _finalize_dockout(self) -> None:
        if len(self.dockout_points) < 2:
            QMessageBox.warning(
                self.editor_page,
                "Dock Out incompleto",
                "Debe añadir al menos un waypoint después del Home.",
            )
            return

        if self.dockout_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.dockout_preview_scene_item)
            self.dockout_preview_scene_item = None

        self.editor_page.set_status_message(
            f"Ruta Dock Out finalizada con {len(self.dockout_points)} waypoints."
        )


    def _start_work_route(self) -> None:
        if self.home_position is None:
            QMessageBox.warning(self.editor_page, "Home requerido", "Debe definir el punto Home.")
            return

        if not self.perimeter_finalized:
            QMessageBox.warning(self.editor_page, "Perímetro requerido", "Debe finalizar el perímetro.")
            return

        if len(self.dockout_points) < 2:
            QMessageBox.warning(
                self.editor_page,
                "Dock Out requerido",
                "Debe generar y finalizar una ruta Dock Out antes de generar la ruta de trabajo.",
            )
            return

        self.work_x_direction = None
        self.work_y_direction = None

        for scene_item in self.work_direction_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.work_direction_scene_items.clear()

        if self.work_direction_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.work_direction_preview_scene_item)
            self.work_direction_preview_scene_item = None

        self.editor_page.show_work_route_group()

        self.editor_page.set_status_message(
            "Marque en el terreno el sentido de incremento X."
        )


    def _set_work_direction_from_scene(self, direction: str, screen_x: float, screen_y: float) -> None:
        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError) as error:
            QMessageBox.warning(self.editor_page, "Dirección no válida", str(error))
            return

        origin = np.array(self.dockout_points[-1][:2], dtype=float)
        target = np.array(point[:2], dtype=float)

        vector = target - origin
        magnitude = np.linalg.norm(vector)

        if magnitude < 1.0:
            QMessageBox.warning(
                self.editor_page,
                "Dirección no válida",
                "Marque un punto al menos a 1 metro del final del Dock Out.",
            )
            return

        vector /= magnitude

        if direction == "x":
            self.work_x_direction = vector
            self.editor_page.set_work_direction_label("x", vector[0], vector[1])
            self.editor_page.set_status_message("Sentido X definido. Ahora marque el sentido de incremento Y.")

        elif direction == "y":
            self.work_y_direction = vector
            self.editor_page.set_work_direction_label("y", vector[0], vector[1])

            try:
                self._generate_work_route_base()

            except ValueError as error:
                QMessageBox.warning(
                    self.editor_page,
                    "No se pudo generar la ruta",
                    str(error),
                )

    def _preview_work_direction(self, direction: str, screen_x: float, screen_y: float) -> None:
        if not self.dockout_points:
            return

        try:
            ray_origin, ray_direction = self.editor_page.scene_ray_from_screen(screen_x, screen_y)
            point = self._intersect_ray_with_terrain(ray_origin, ray_direction)

        except (ValueError, np.linalg.LinAlgError):
            return

        origin = self.dockout_points[-1]

        positions = np.array(
            [
                (origin[0], origin[1], origin[2] + 1.5),
                (point[0], point[1], point[2] + 1.5),
            ],
            dtype=np.float32,
        )

        if self.work_direction_preview_scene_item is None:
            self.work_direction_preview_scene_item = gl.GLLinePlotItem(
                pos=positions,
                color=(0.65, 0.10, 0.75, 1.0),
                width=3.0,
                antialias=True,
                mode="lines",
            )

            self.editor_page.add_scene_item(self.work_direction_preview_scene_item)

        else:
            self.work_direction_preview_scene_item.setData(pos=positions)


    def _cancel_work_route_selection(self) -> None:
        self.work_x_direction = None
        self.work_y_direction = None

        if self.work_direction_preview_scene_item is not None:
            self.editor_page.remove_scene_item(self.work_direction_preview_scene_item)
            self.work_direction_preview_scene_item = None

        for scene_item in self.work_direction_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.work_direction_scene_items.clear()

        self.editor_page.set_work_direction_label("x", 0.0, 0.0)
        self.editor_page.set_work_direction_label("y", 0.0, 0.0)

        self.editor_page.set_status_message("Selección de dirección de ruta cancelada.")


    def _generate_work_route_base(self) -> None:
        if self.work_x_direction is None or self.work_y_direction is None:
            raise ValueError("Debe definir los sentidos X e Y.")

        if not self.perimeter_finalized:
            raise ValueError("Debe existir un perímetro válido.")

        work_width, overlap = self.editor_page.get_work_route_parameters()
        spacing = WorkRouteGenerator.calculate_spacing(work_width, overlap)

        activation_radius = WorkRouteGenerator.calculate_post_activation_radius(
            self.structure_point_groups
        )

        segments = WorkRouteGenerator.generate_parallel_segments(
            self.perimeter_points,
            self.work_x_direction,
            self.work_y_direction,
            spacing,
        )

        segments = WorkRouteGenerator.filter_segments_by_posts(
            segments,
            self.structure_points,
            activation_radius,
        )

        route_2d = WorkRouteGenerator.build_zigzag_route(
            segments,
            self.work_x_direction,
            self.dockout_points[-1],
        )

        post_conflicts = WorkRouteGenerator.find_post_conflicts(
            route_2d,
            self.structure_points,
            safety_radius=1.0,
        )

        route_with_detours = WorkRouteGenerator.apply_post_detours(
            route_2d,
            self.structure_points,
            self.perimeter_points,
            safety_radius=1.0,
        )

        remaining_conflicts = WorkRouteGenerator.find_post_conflicts(
            route_with_detours,
            self.structure_points,
            safety_radius=1.0,
        )

        for scene_item in self.work_route_scene_items:
            self.editor_page.remove_scene_item(scene_item)

        self.work_route_scene_items.clear()
        self.work_route_points = []

        for x, y in route_with_detours:
            z = self._terrain_height_at(x, y)
            self.work_route_points.append((x, y, z))

        positions = np.array(
            [(x, y, z + 1.2) for x, y, z in self.work_route_points],
            dtype=np.float32,
        )

        route_item = gl.GLLinePlotItem(
            pos=positions,
            color=(0.10, 0.70, 0.25, 1.0),
            width=3.0,
            antialias=True,
            mode="line_strip",
        )

        self.editor_page.add_scene_item(route_item)
        self.work_route_scene_items.append(route_item)

        points_item = gl.GLScatterPlotItem(
            pos=positions,
            size=4.0,
            color=(0.10, 0.55, 0.20, 1.0),
            pxMode=True,
        )

        self.editor_page.add_scene_item(points_item)
        self.work_route_scene_items.append(points_item)

        self.editor_page.set_status_message(
            f"Ruta: {len(self.work_route_points)} waypoints | "
            f"Conflictos iniciales: {len(post_conflicts)} | "
            f"Conflictos restantes: {len(remaining_conflicts)}"
        )
