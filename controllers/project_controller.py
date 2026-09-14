import re
from pathlib import Path

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox

from controllers.editor_controller import EditorController
from ui.main_window import MainWindow
from world.world_project import WorldProject

from world.sdf_generator import SdfGenerator

from services.geotiff_reader import GeoTiffReader

from services.kml_route_exporter import KmlRouteExporter

from services.simulation_route_exporter import SimulationRouteExporter

class ProjectController(QObject):
    """
    Controlador encargado de administrar el proyecto activo.

    Sus responsabilidades actuales son:

    - Validar los datos de la pantalla inicial.
    - Crear un proyecto nuevo.
    - Entregar el proyecto al editor.
    - Navegar entre configuración y editor.
    - Mantener una referencia al proyecto activo.

    La edición de objetos pertenece a EditorController.
    """

    def __init__(
        self,
        main_window: MainWindow,
        editor_controller: EditorController,
    ) -> None:
        super().__init__(main_window)

        self.main_window = main_window
        self.editor_controller = editor_controller

        self.current_project: WorldProject | None = None

        self._configure_connections()

    # =========================================================
    # CONEXIONES CON LA INTERFAZ
    # =========================================================

    def _configure_connections(self) -> None:
        start_page = self.main_window.start_page
        editor_page = self.main_window.editor_page

        start_page.create_from_scratch_requested.connect(
            self.create_project_from_scratch
        )

        start_page.terrain_import_requested.connect(
            self.import_terrain
        )

        editor_page.back_requested.connect(
            self.return_to_start_page
        )

        editor_page.save_requested.connect(
            self._show_save_pending_message
        )

        editor_page.export_sdf_requested.connect(
            self.export_sdf
        )

        editor_page.run_gazebo_requested.connect(
            self._show_gazebo_pending_message
        )

    # =========================================================
    # CREACIÓN DEL PROYECTO
    # =========================================================

    def create_project_from_scratch(
        self,
        name: str,
        width: float,
        length: float,
    ) -> None:
        """
        Valida los datos, crea el proyecto y abre el editor.
        """

        try:
            validated_name = self._validate_project_name(
                name
            )

            project = WorldProject(
                name=validated_name,
                width=float(width),
                length=float(length),
                creation_mode="scratch",
            )

        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self.main_window,
                "Datos del proyecto no válidos",
                str(error),
            )
            return

        self.current_project = project

        self.main_window.editor_page.configure_project(
            name=project.name,
            width=project.width,
            length=project.length,
        )

        self.editor_controller.set_project(
            project
        )

        self.main_window.show_editor_page(
            project_name=project.name
        )

    @staticmethod
    def _validate_project_name(
        name: str,
    ) -> str:
        """
        Valida un nombre que pueda utilizarse posteriormente
        como nombre de archivo y como nombre del mundo SDF.
        """

        clean_name = name.strip()

        if not clean_name:
            raise ValueError(
                "Debe ingresar un nombre para el proyecto."
            )

        valid_name_pattern = (
            r"^[A-Za-z_][A-Za-z0-9_-]*$"
        )

        if re.fullmatch(
            valid_name_pattern,
            clean_name,
        ) is None:
            raise ValueError(
                "El nombre debe comenzar con una letra o "
                "guion bajo y solo puede contener letras, "
                "números, guiones y guiones bajos."
            )

        return clean_name

    # =========================================================
    # IMPORTACIÓN DE TERRENO
    # =========================================================

    def import_terrain(
        self,
        terrain_path: str,
    ) -> None:
        """
        Crea un proyecto a partir de un GeoTIFF DEM.
        """

        try:
            if not terrain_path.strip():
                raise ValueError(
                    "Debe seleccionar un archivo de terreno."
                )

            terrain_info = GeoTiffReader.read_info(
                terrain_path
            )

            terrain_width = (
                terrain_info.max_x
                - terrain_info.min_x
            )

            terrain_length = (
                terrain_info.max_y
                - terrain_info.min_y
            )

            project_name = Path(
                terrain_path
            ).stem

            project_name = (
                self._validate_project_name(
                    project_name
                )
            )

            project = WorldProject(
                name=project_name,
                width=terrain_width,
                length=terrain_length,
                creation_mode="terrain",
                terrain_path=str(
                    Path(terrain_path).resolve()
                ),
            )

        except (
            OSError,
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self.main_window,
                "Terreno no válido",
                str(error),
            )
            return

        self.current_project = project

        self.main_window.editor_page.configure_project(
            name=project.name,
            width=project.width,
            length=project.length,
        )

        self.editor_controller.set_project(
            project
        )

        self.main_window.show_editor_page(
            project_name=project.name
        )

        self.main_window.editor_page.set_status_message(
            (
                f"Terreno cargado: "
                f"{project.width:.1f} × "
                f"{project.length:.1f} m"
            )
        )

    # =========================================================
    # NAVEGACIÓN
    # =========================================================

    def return_to_start_page(self) -> None:
        """
        Regresa a la configuración inicial.

        El proyecto continúa almacenado en memoria mientras
        no se cree otro proyecto o se cierre la aplicación.
        """

        self.main_window.show_start_page()

    # =========================================================
    # CONSULTAS DEL PROYECTO
    # =========================================================

    def has_active_project(self) -> bool:
        return self.current_project is not None

    def get_active_project(
        self,
    ) -> WorldProject | None:
        return self.current_project

    # =========================================================
    # FUNCIONES PENDIENTES
    # =========================================================

    def _show_save_pending_message(self) -> None:
        if not self._require_active_project():
            return

        QMessageBox.information(
            self.main_window,
            "Guardar proyecto",
            "El guardado del proyecto se implementará "
            "mediante un servicio independiente.",
        )

    def export_sdf(
        self,
        show_confirmation: bool = True,
    ) -> Path | None:
        """
        Exporta el proyecto activo como un archivo SDF.

        El archivo se guarda dentro de la carpeta
        generated_worlds del proyecto.
        """

        if not self._require_active_project():
            return None

        assert self.current_project is not None

        project_directory = (
            Path(__file__).resolve().parent.parent
        )

        output_path = (
            project_directory
            / "generated_worlds"
            / f"{self.current_project.name}.sdf"
        )

        try:
            exported_path = SdfGenerator.export(
                project=self.current_project,
                output_path=output_path,
                post_points=self.editor_controller.structure_points,
                post_groups=self.editor_controller.structure_point_groups,
                route_points=self.editor_controller.work_route_points,
                dockout_points=self.editor_controller.dockout_points,
                home_position=self.editor_controller.home_position,
            )

            route_points = self.editor_controller.work_route_points

            if len(route_points) >= 2 and self.current_project.terrain_path:
                route_directory = (
                    project_directory
                    / "generated_worlds"
                    / "routes"
                )

                route_path = (
                    route_directory
                    / f"{self.current_project.name}_route.kml"
                )

                KmlRouteExporter.export(
                    route_points=route_points,
                    terrain_path=self.current_project.terrain_path,
                    output_path=route_path,
                    route_name=f"{self.current_project.name}_route",
                )

            if (
                len(self.editor_controller.dockout_points) >= 2
                and len(self.editor_controller.work_route_points) >= 2
            ):
                simulation_route_path = (
                    project_directory
                    / "generated_worlds"
                    / "routes"
                    / "simulation_route.csv"
                )

                SimulationRouteExporter.export(
                    dockout_points=self.editor_controller.dockout_points,
                    work_route_points=self.editor_controller.work_route_points,
                    output_path=simulation_route_path,
                )

        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self.main_window,
                "Error al exportar SDF",
                "No se pudo generar el archivo SDF:\n"
                f"{error}",
            )
            return None

        self.main_window.editor_page.set_status_message(
            f"Mundo exportado en: {exported_path}"
        )

        if show_confirmation:
            QMessageBox.information(
                self.main_window,
                "Exportación completada",
                "El mundo se exportó correctamente:\n\n"
                f"{exported_path}",
            )

        return exported_path

    def _show_gazebo_pending_message(self) -> None:
        if not self._require_active_project():
            return

        QMessageBox.information(
            self.main_window,
            "Ejecutar Gazebo",
            "La ejecución de Gazebo estará disponible "
            "después de implementar la exportación SDF.",
        )

    def _require_active_project(self) -> bool:
        if self.current_project is not None:
            return True

        QMessageBox.warning(
            self.main_window,
            "Proyecto no disponible",
            "No existe un proyecto activo.",
        )

        return False
