import numpy as np
import pyqtgraph.opengl as gl

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EditorPage(QWidget):
    """
    Interfaz gráfica del editor de mundos.

    Esta clase muestra:

    - Biblioteca de objetos.
    - Escena tridimensional.
    - Propiedades del objeto seleccionado.
    - Lista de objetos añadidos al mundo.
    - Controles para guardar, exportar y ejecutar Gazebo.

    No crea objetos del mundo directamente. Las acciones se comunican
    al controlador mediante señales.
    """

    back_requested = pyqtSignal()
    save_requested = pyqtSignal()
    export_sdf_requested = pyqtSignal()
    run_gazebo_requested = pyqtSignal()

    add_object_requested = pyqtSignal(str)
    delete_object_requested = pyqtSignal(object)
    object_selected = pyqtSignal(object)

    import_structure_points_requested = pyqtSignal()

    mark_home_requested = pyqtSignal()
    home_coordinates_edited = pyqtSignal(float, float)
    home_scene_clicked = pyqtSignal(float, float)
    home_scene_hovered = pyqtSignal(float, float)
    object_properties_edited = pyqtSignal(object,dict,)

    perimeter_scene_clicked = pyqtSignal(float, float)
    perimeter_scene_hovered = pyqtSignal(float, float)
    finalize_perimeter_requested = pyqtSignal()
    clear_perimeter_requested = pyqtSignal()

    dockout_scene_clicked = pyqtSignal(float, float)
    dockout_scene_hovered = pyqtSignal(float, float)
    finalize_dockout_requested = pyqtSignal()

    start_dockout_requested = pyqtSignal()

    work_direction_scene_clicked = pyqtSignal(str, float, float)
    work_direction_scene_hovered = pyqtSignal(str, float, float)
    start_work_route_requested = pyqtSignal()

    cancel_work_route_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._selected_object_id = None
        self._updating_properties = False
        self._home_selection_mode = False
        self._perimeter_selection_mode = False

        self._dockout_selection_mode = False

        self._work_direction_selection: str | None = None

        self.terrain_item = None
        self.terrain_outline_item = None

        self._create_interface()
        self._configure_connections()

    # =========================================================
    # CREACIÓN DE LA INTERFAZ
    # =========================================================

    def _create_interface(self) -> None:
        top_bar = self._create_top_bar()
        content_splitter = self._create_content_splitter()

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        main_layout.addLayout(top_bar)
        main_layout.addWidget(content_splitter, 1)

        self.setLayout(main_layout)

    # =========================================================
    # BARRA SUPERIOR
    # =========================================================

    def _create_top_bar(self) -> QHBoxLayout:
        self.back_button = QPushButton(
            "← Volver a configuración"
        )

        self.project_label = QLabel(
            "Editor del mundo"
        )
        self.project_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
        """)

        self.save_button = QPushButton(
            "Guardar proyecto"
        )

        self.export_button = QPushButton(
            "Exportar SDF"
        )

        self.run_gazebo_button = QPushButton(
            "Ejecutar en Gazebo"
        )

        layout = QHBoxLayout()
        layout.addWidget(self.back_button)
        layout.addSpacing(20)
        layout.addWidget(self.project_label)
        layout.addStretch()
        layout.addWidget(self.save_button)
        layout.addWidget(self.export_button)
        layout.addWidget(self.run_gazebo_button)

        return layout

    # =========================================================
    # DIVISIÓN PRINCIPAL
    # =========================================================

    def _create_content_splitter(self) -> QSplitter:
        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.addWidget(
            self._create_library_panel()
        )

        splitter.addWidget(
            self._create_scene_panel()
        )

        splitter.addWidget(
            self._create_properties_panel()
        )

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        splitter.setSizes(
            [220, 760, 400]
        )
        splitter.setCollapsible(
            2,
            False,
        )

        return splitter

    # =========================================================
    # PANEL IZQUIERDO: BIBLIOTECA
    # =========================================================

    def _create_library_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(210)

        title = QLabel(
            "Biblioteca de objetos"
        )
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
        """)

        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderHidden(True)

        self._populate_object_library()

        self.add_object_button = QPushButton(
            "Añadir objeto seleccionado"
        )

        self.import_structure_points_button = QPushButton("Importar CSV de postes")

        self.generate_solar_structures_checkbox = QCheckBox("Generar estructuras solares")
        self.generate_solar_structures_checkbox.setChecked(False)

        self.add_object_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.object_tree, 1)
        layout.addWidget(self.add_object_button)

        layout.addSpacing(12)
        layout.addWidget(self.import_structure_points_button)

        layout.addWidget(self.generate_solar_structures_checkbox)

        panel.setLayout(layout)

        return panel

    def _populate_object_library(self) -> None:
        structures = QTreeWidgetItem(
            ["Estructuras"]
        )

        self._add_library_item(
            parent=structures,
            text="Muros",
            object_type="wall",
            enabled=True,
        )

        self._add_library_item(
            parent=structures,
            text="Estructura fotovoltaica fija",
            object_type="solar_fixed",
            enabled=True,
        )

        self._add_library_item(
            parent=structures,
            text="Seguidor mono-fila de un eje",
            object_type="solar_single_row_tracker",
            enabled=True,
        )

        self._add_library_item(
            parent=structures,
            text="Seguidor dual-row de un eje",
            object_type="solar_dual_row_tracker",
            enabled=True,
        )

        self._add_library_item(
            parent=structures,
            text="Columnas",
            object_type="column",
            enabled=False,
        )

        self._add_library_item(
            parent=structures,
            text="Soportes genéricos",
            object_type="support",
            enabled=False,
        )
        surfaces = QTreeWidgetItem(
            ["Vías y superficies"]
        )

        self._add_library_item(
            parent=surfaces,
            text="Calles",
            object_type="road",
            enabled=False,
        )

        self._add_library_item(
            parent=surfaces,
            text="Aceras",
            object_type="sidewalk",
            enabled=False,
        )

        self._add_library_item(
            parent=surfaces,
            text="Plataformas",
            object_type="platform",
            enabled=False,
        )

        industrial = QTreeWidgetItem(
            ["Elementos industriales"]
        )

        self._add_library_item(
            parent=industrial,
            text="Paneles",
            object_type="panel",
            enabled=False,
        )

        self._add_library_item(
            parent=industrial,
            text="Tuberías",
            object_type="pipe",
            enabled=False,
        )

        self._add_library_item(
            parent=industrial,
            text="Maquinaria",
            object_type="machine",
            enabled=False,
        )

        environment = QTreeWidgetItem(
            ["Entorno"]
        )

        self._add_library_item(
            parent=environment,
            text="Edificios",
            object_type="building",
            enabled=False,
        )

        self._add_library_item(
            parent=environment,
            text="Vegetación",
            object_type="vegetation",
            enabled=False,
        )

        self._add_library_item(
            parent=environment,
            text="Señalización",
            object_type="sign",
            enabled=False,
        )

        self.object_tree.addTopLevelItems(
            [
                structures,
                surfaces,
                industrial,
                environment,
            ]
        )

        self.object_tree.expandAll()

    @staticmethod
    def _add_library_item(
        parent: QTreeWidgetItem,
        text: str,
        object_type: str,
        enabled: bool,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])

        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            object_type,
        )

        item.setDisabled(not enabled)
        parent.addChild(item)

        return item

    # =========================================================
    # PANEL CENTRAL: ESCENA 3D
    # =========================================================

    def _create_scene_panel(self) -> QWidget:
        panel = QWidget()

        title = QLabel("Escena 3D")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
        """)

        self.north_view_button = QPushButton("Norte ↑")
        self.north_view_button.setFixedWidth(90)
        self.north_view_button.clicked.connect(self._orient_view_north)

        self.mark_home_button = QPushButton("Marcar Home")
        self.mark_home_button.setFixedWidth(120)
        self.mark_home_button.clicked.connect(self._activate_home_selection)

        self.mark_perimeter_button = QPushButton("Marcar perímetro")
        self.mark_perimeter_button.setFixedWidth(140)

        self.finalize_perimeter_button = QPushButton("Finalizar perímetro")
        self.finalize_perimeter_button.setFixedWidth(150)

        self.clear_perimeter_button = QPushButton("Borrar perímetro")
        self.clear_perimeter_button.setFixedWidth(130)

        self.mark_dockout_button = QPushButton("Marcar Dock Out")
        self.mark_dockout_button.setFixedWidth(130)
        self.mark_dockout_button.setEnabled(False)

        self.mark_dockout_button.clicked.connect(self._toggle_dockout_selection)

        self.generate_work_route_button = QPushButton("Generar ruta de trabajo")
        self.generate_work_route_button.clicked.connect(self._start_work_route_selection)
        self.generate_work_route_button.setFixedWidth(170)
        self.generate_work_route_button.setEnabled(False)

        self.cancel_work_route_button = QPushButton("Cancelar selección")
        self.cancel_work_route_button.setFixedWidth(140)
        self.cancel_work_route_button.setVisible(False)
        self.cancel_work_route_button.clicked.connect(self._cancel_work_route_selection)

        self.mark_perimeter_button.clicked.connect(self._activate_perimeter_selection)
        self.finalize_perimeter_button.clicked.connect(self._finalize_perimeter)
        self.clear_perimeter_button.clicked.connect(self._clear_perimeter)

        self.scene_3d = gl.GLViewWidget()
        self.scene_3d.setMouseTracking(True)
        self.scene_3d.installEventFilter(self)
        self.scene_3d.setBackgroundColor("#F5F1E8")

        self.scene_3d.setMinimumHeight(650)

        self.scene_3d.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.grid_item = gl.GLGridItem()
        self.grid_item.setSpacing(1, 1)
        self.scene_3d.addItem(
            self.grid_item
        )

        self.axes_item = gl.GLAxisItem()
        self.axes_item.setSize(5, 5, 5)
        self.scene_3d.addItem(
            self.axes_item
        )

        self.status_label = QLabel(
            "Proyecto vacío. Seleccione un objeto "
            "de la biblioteca para comenzar."
        )

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        view_controls_layout = QHBoxLayout()
        view_controls_layout.addStretch()
        view_controls_layout.addWidget(self.mark_home_button)
        view_controls_layout.addWidget(self.mark_perimeter_button)
        view_controls_layout.addWidget(self.finalize_perimeter_button)
        view_controls_layout.addWidget(self.clear_perimeter_button)
        view_controls_layout.addWidget(self.mark_dockout_button)
        view_controls_layout.addWidget(self.generate_work_route_button)
        view_controls_layout.addWidget(self.north_view_button)

        view_controls_layout.addWidget(self.generate_work_route_button)
        view_controls_layout.addWidget(self.cancel_work_route_button)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(view_controls_layout)
        layout.addWidget(self.scene_3d, 1)
        layout.addWidget(self.status_label)

        panel.setLayout(layout)

        return panel

    def _orient_view_north(self) -> None:
        self.scene_3d.setCameraPosition(azimuth=-90)

    def _activate_home_selection(self) -> None:
        self._dockout_selection_mode = False
        self.mark_dockout_button.setText("Marcar Dock Out")

        self._perimeter_selection_mode = False
        self.mark_perimeter_button.setText("Marcar perímetro")

        self._home_selection_mode = True
        self.mark_home_button.setText("Seleccione un punto...")

    def _activate_perimeter_selection(self) -> None:

        self._dockout_selection_mode = False
        self.mark_dockout_button.setText("Marcar Dock Out")

        self._home_selection_mode = False
        self.mark_home_button.setText("Marcar Home")

        self._perimeter_selection_mode = True
        self.mark_perimeter_button.setText("Marcando perímetro...")


    def _finalize_perimeter(self) -> None:
        self._perimeter_selection_mode = False
        self.mark_perimeter_button.setText("Marcar perímetro")
        self.finalize_perimeter_requested.emit()


    def _clear_perimeter(self) -> None:
        self._perimeter_selection_mode = False
        self.mark_perimeter_button.setText("Marcar perímetro")
        self.clear_perimeter_requested.emit()

    def _toggle_dockout_selection(self) -> None:
        if self._dockout_selection_mode:
            self._dockout_selection_mode = False
            self.mark_dockout_button.setText("Marcar Dock Out")
            self.finalize_dockout_requested.emit()
            return

        self._home_selection_mode = False
        self._perimeter_selection_mode = False

        self.mark_home_button.setText("Marcar Home")
        self.mark_perimeter_button.setText("Marcar perímetro")

        self.start_dockout_requested.emit()

        self._dockout_selection_mode = True
        self.mark_dockout_button.setText("Finalizar Dock Out")

    def eventFilter(self, watched, event) -> bool:
        if watched is not self.scene_3d:
           return super().eventFilter(watched, event)

        if self._home_selection_mode:
            if event.type() == QEvent.Type.MouseMove:
                position = event.position()
                self.home_scene_hovered.emit(position.x(), position.y())

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    position = event.position()
                    self.home_scene_clicked.emit(position.x(), position.y())

                    self._home_selection_mode = False
                    self.mark_home_button.setText("Marcar Home")

                    return True

        elif self._perimeter_selection_mode:
            if event.type() == QEvent.Type.MouseMove:
                position = event.position()
                self.perimeter_scene_hovered.emit(position.x(), position.y())

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    position = event.position()
                    self.perimeter_scene_clicked.emit(position.x(), position.y())

                    return True

        elif self._dockout_selection_mode:
            if event.type() == QEvent.Type.MouseMove:
                position = event.position()
                self.dockout_scene_hovered.emit(position.x(), position.y())

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    position = event.position()
                    self.dockout_scene_clicked.emit(position.x(), position.y())

                    return True

        elif self._work_direction_selection is not None:
            if event.type() == QEvent.Type.MouseMove:
                position = event.position()

                self.work_direction_scene_hovered.emit(
                    self._work_direction_selection,
                    position.x(),
                    position.y(),
                )

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    position = event.position()

                    current_direction = self._work_direction_selection

                    self.work_direction_scene_clicked.emit(
                        current_direction,
                        position.x(),
                        position.y(),
                    )

                    if current_direction == "x":
                        self._work_direction_selection = "y"
                        self.generate_work_route_button.setText("Marque sentido Y...")

                    else:
                        self._work_direction_selection = None
                        self.generate_work_route_button.setText("Generar ruta de trabajo")
                        self.cancel_work_route_button.setVisible(False)

                    return True

        return super().eventFilter(watched, event)


    def scene_ray_from_screen(
        self,
        screen_x: float,
        screen_y: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        width = self.scene_3d.width()
        height = self.scene_3d.height()

        if width <= 0 or height <= 0:
            raise ValueError("El visor 3D no tiene dimensiones válidas.")

        # Coordenadas de pantalla -> coordenadas normalizadas OpenGL.
        ndc_x = 2.0 * screen_x / width - 1.0
        ndc_y = 1.0 - 2.0 * screen_y / height

        viewport = self.scene_3d.getViewport()
        projection = self.scene_3d.projectionMatrix(viewport, viewport)
        view = self.scene_3d.viewMatrix()

        view_projection = projection * view

        matrix_rows = []

        for row_index in range(4):
            row = view_projection.row(row_index)
            matrix_rows.append([
                row.x(),
                row.y(),
                row.z(),
                row.w(),
            ])

        view_projection_matrix = np.array(matrix_rows, dtype=float)
        inverse_matrix = np.linalg.inv(view_projection_matrix)

        near_clip = np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=float)
        far_clip = np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=float)

        near_world = inverse_matrix @ near_clip
        far_world = inverse_matrix @ far_clip

        near_world /= near_world[3]
        far_world /= far_world[3]

        ray_origin = near_world[:3]

        ray_direction = far_world[:3] - near_world[:3]
        ray_direction /= np.linalg.norm(ray_direction)

        return ray_origin, ray_direction

    # =========================================================
    # PANEL DERECHO: PROPIEDADES
    # =========================================================

    def _create_properties_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(390)

        self.home_group = self._create_home_group()

        self.work_route_group = self._create_work_route_group()

        self.object_properties_group = QGroupBox(
            "Propiedades del objeto"
        )
        self.object_properties_group.setEnabled(False)

        properties_layout = QVBoxLayout()
        properties_layout.addWidget(
            self._create_general_properties_group()
        )
        properties_layout.addWidget(
            self._create_transform_group()
        )

        self.wall_dimensions_group = (
            self._create_wall_dimensions_group()
        )
        self.wall_dimensions_group.setVisible(False)

        properties_layout.addWidget(
            self.wall_dimensions_group
        )

        self.solar_structure_group = (
            self._create_solar_structure_group()
        )
        self.solar_structure_group.setVisible(False)

        properties_layout.addWidget(
            self.solar_structure_group
        )

        self.object_properties_group.setLayout(
            properties_layout
        )

        self.properties_scroll_area = QScrollArea()
        self.properties_scroll_area.setWidgetResizable(
            True
        )

        self.properties_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.properties_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.properties_scroll_area.setWidget(
            self.object_properties_group
        )

        world_objects_label = QLabel(
            "Objetos del mundo"
        )

        world_objects_label.setStyleSheet("""
            font-weight: bold;
        """)

        self.world_objects_list = QListWidget()

        self.delete_object_button = QPushButton(
            "Eliminar objeto"
        )
        self.delete_object_button.setEnabled(False)

        layout = QVBoxLayout()

        layout.addWidget(self.home_group)
        layout.addWidget(self.work_route_group)

        layout.addWidget(
            self.properties_scroll_area,
            3
        )

        layout.addWidget(world_objects_label)

        layout.addWidget(
            self.world_objects_list,
            1,
        )

        layout.addWidget(
            self.delete_object_button
        )

        panel.setLayout(layout)

        return panel

    def _create_home_group(self) -> QGroupBox:
        group = QGroupBox("Punto Home")

        self.home_x_input = QDoubleSpinBox()
        self.home_x_input.setRange(-1000000.0, 1000000.0)
        self.home_x_input.setDecimals(3)
        self.home_x_input.setSuffix(" m")

        self.home_y_input = QDoubleSpinBox()
        self.home_y_input.setRange(-1000000.0, 1000000.0)
        self.home_y_input.setDecimals(3)
        self.home_y_input.setSuffix(" m")

        self.home_z_input = QDoubleSpinBox()
        self.home_z_input.setRange(-1000000.0, 1000000.0)
        self.home_z_input.setDecimals(3)
        self.home_z_input.setSuffix(" m")
        self.home_z_input.setReadOnly(True)
        self.home_z_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)

        form = QFormLayout()
        form.addRow("X:", self.home_x_input)
        form.addRow("Y:", self.home_y_input)
        form.addRow("Z:", self.home_z_input)

        group.setLayout(form)
        group.setVisible(False)

        return group

    def _create_work_route_group(self) -> QGroupBox:
        group = QGroupBox("Ruta de trabajo")

        self.work_width_input = QDoubleSpinBox()
        self.work_width_input.setRange(1.0, 20.0)
        self.work_width_input.setDecimals(2)
        self.work_width_input.setSingleStep(0.10)
        self.work_width_input.setValue(1.20)
        self.work_width_input.setSuffix(" m")

        self.work_overlap_input = QDoubleSpinBox()
        self.work_overlap_input.setRange(0.0, 0.20)
        self.work_overlap_input.setDecimals(2)
        self.work_overlap_input.setSingleStep(0.01)
        self.work_overlap_input.setValue(0.20)
        self.work_overlap_input.setSuffix(" m")

        self.work_x_direction_label = QLabel("No definido")
        self.work_y_direction_label = QLabel("No definido")

        form = QFormLayout()
        form.addRow("Ancho de desbroce:", self.work_width_input)
        form.addRow("Solapamiento:", self.work_overlap_input)
        form.addRow("Sentido X:", self.work_x_direction_label)
        form.addRow("Sentido Y:", self.work_y_direction_label)

        group.setLayout(form)
        group.setVisible(False)

        return group

    def _create_general_properties_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox("General")

        self.object_name_input = QLineEdit()

        form = QFormLayout()
        form.addRow(
            "Nombre:",
            self.object_name_input,
        )

        group.setLayout(form)

        return group

    def _create_transform_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox("Transformación")

        self.position_x_input = (
            self._create_numeric_control(
                minimum=-10000.0,
                maximum=10000.0,
                value=0.0,
                decimals=3,
                suffix=" m",
            )
        )

        self.position_y_input = (
            self._create_numeric_control(
                minimum=-10000.0,
                maximum=10000.0,
                value=0.0,
                decimals=3,
                suffix=" m",
            )
        )

        self.position_z_input = (
            self._create_numeric_control(
                minimum=-10000.0,
                maximum=10000.0,
                value=0.0,
                decimals=3,
                suffix=" m",
            )
        )

        self.rotation_x_input = (
            self._create_numeric_control(
                minimum=-360.0,
                maximum=360.0,
                value=0.0,
                decimals=2,
                suffix="°",
            )
        )

        self.rotation_y_input = (
            self._create_numeric_control(
                minimum=-360.0,
                maximum=360.0,
                value=0.0,
                decimals=2,
                suffix="°",
            )
        )

        self.rotation_z_input = (
            self._create_numeric_control(
                minimum=-360.0,
                maximum=360.0,
                value=0.0,
                decimals=2,
                suffix="°",
            )
        )

        self.scale_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=100.0,
                value=1.0,
                decimals=3,
            )
        )

        form = QFormLayout()
        form.addRow(
            "Posición X:",
            self.position_x_input,
        )
        form.addRow(
            "Posición Y:",
            self.position_y_input,
        )
        form.addRow(
            "Posición Z:",
            self.position_z_input,
        )
        form.addRow(
            "Rotación X:",
            self.rotation_x_input,
        )
        form.addRow(
            "Rotación Y:",
            self.rotation_y_input,
        )
        form.addRow(
            "Rotación Z:",
            self.rotation_z_input,
        )
        form.addRow(
            "Escala:",
            self.scale_input,
        )

        group.setLayout(form)

        return group

    def _create_wall_dimensions_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Dimensiones del muro"
        )

        self.wall_length_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=10000.0,
                value=5.0,
                decimals=3,
                suffix=" m",
            )
        )

        self.wall_thickness_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=1000.0,
                value=0.20,
                decimals=3,
                suffix=" m",
            )
        )

        self.wall_height_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=1000.0,
                value=2.0,
                decimals=3,
                suffix=" m",
            )
        )

        form = QFormLayout()
        form.addRow(
            "Largo:",
            self.wall_length_input,
        )
        form.addRow(
            "Espesor:",
            self.wall_thickness_input,
        )
        form.addRow(
            "Altura:",
            self.wall_height_input,
        )

        group.setLayout(form)

        return group

    def _create_solar_structure_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Estructura fotovoltaica"
        )

        self.solar_structure_type_input = QComboBox()

        self.solar_structure_type_input.addItem(
            "Estructura fija",
            "fixed",
        )

        self.solar_structure_type_input.addItem(
            "Seguidor mono-fila de un eje",
            "single_row_tracker",
        )

        self.solar_structure_type_input.addItem(
            "Seguidor dual-row de un eje",
            "dual_row_tracker",
        )

        self.solar_modules_per_row_input = QSpinBox()
        self.solar_modules_per_row_input.setRange(
            1,
            500,
        )
        self.solar_modules_per_row_input.setValue(6)

        self.solar_module_length_input = (
            self._create_numeric_control(
                minimum=0.10,
                maximum=20.0,
                value=2.20,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_module_width_input = (
            self._create_numeric_control(
                minimum=0.10,
                maximum=20.0,
                value=1.10,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_module_thickness_input = (
            self._create_numeric_control(
                minimum=0.001,
                maximum=1.0,
                value=0.04,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_module_gap_input = (
            self._create_numeric_control(
                minimum=0.0,
                maximum=5.0,
                value=0.05,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_post_count_input = QSpinBox()
        self.solar_post_count_input.setRange(
            2,
            100,
        )
        self.solar_post_count_input.setValue(3)

        self.solar_post_height_input = (
            self._create_numeric_control(
                minimum=0.10,
                maximum=50.0,
                value=1.80,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_post_width_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=5.0,
                value=0.15,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_post_depth_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=5.0,
                value=0.15,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_torque_tube_radius_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=2.0,
                value=0.08,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_beam_thickness_input = (
            self._create_numeric_control(
                minimum=0.01,
                maximum=2.0,
                value=0.10,
                decimals=3,
                suffix=" m",
            )
        )

        self.solar_fixed_tilt_input = (
            self._create_numeric_control(
                minimum=-90.0,
                maximum=90.0,
                value=20.0,
                decimals=2,
                suffix="°",
            )
        )

        self.solar_tracker_angle_input = (
            self._create_numeric_control(
                minimum=-90.0,
                maximum=90.0,
                value=0.0,
                decimals=2,
                suffix="°",
            )
        )

        self.solar_tracker_min_angle_input = (
            self._create_numeric_control(
                minimum=-90.0,
                maximum=90.0,
                value=-60.0,
                decimals=2,
                suffix="°",
            )
        )

        self.solar_tracker_max_angle_input = (
            self._create_numeric_control(
                minimum=-90.0,
                maximum=90.0,
                value=60.0,
                decimals=2,
                suffix="°",
            )
        )

        self.solar_row_spacing_input = (
            self._create_numeric_control(
                minimum=0.10,
                maximum=100.0,
                value=4.0,
                decimals=3,
                suffix=" m",
            )
        )

        form = QFormLayout()

        form.addRow(
            "Tipo:",
            self.solar_structure_type_input,
        )

        form.addRow(
            "Módulos por fila:",
            self.solar_modules_per_row_input,
        )

        form.addRow(
            "Largo del módulo:",
            self.solar_module_length_input,
        )

        form.addRow(
            "Ancho del módulo:",
            self.solar_module_width_input,
        )

        form.addRow(
            "Espesor del módulo:",
            self.solar_module_thickness_input,
        )

        form.addRow(
            "Separación de módulos:",
            self.solar_module_gap_input,
        )

        form.addRow(
            "Cantidad de postes:",
            self.solar_post_count_input,
        )

        form.addRow(
            "Altura de postes:",
            self.solar_post_height_input,
        )

        form.addRow(
            "Ancho de postes:",
            self.solar_post_width_input,
        )

        form.addRow(
            "Profundidad de postes:",
            self.solar_post_depth_input,
        )

        form.addRow(
            "Radio del tubo:",
            self.solar_torque_tube_radius_input,
        )

        form.addRow(
            "Espesor de vigas:",
            self.solar_beam_thickness_input,
        )

        form.addRow(
            "Inclinación fija:",
            self.solar_fixed_tilt_input,
        )

        form.addRow(
            "Ángulo del seguidor:",
            self.solar_tracker_angle_input,
        )

        form.addRow(
            "Límite mínimo:",
            self.solar_tracker_min_angle_input,
        )

        form.addRow(
            "Límite máximo:",
            self.solar_tracker_max_angle_input,
        )

        form.addRow(
            "Separación entre filas:",
            self.solar_row_spacing_input,
        )

        group.setLayout(form)

        return group

    @staticmethod
    def _create_numeric_control(
        minimum: float,
        maximum: float,
        value: float,
        decimals: int,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox()

        control.setRange(
            minimum,
            maximum,
        )

        control.setValue(value)
        control.setDecimals(decimals)
        control.setSuffix(suffix)

        control.setMinimumWidth(150)
        control.setMinimumHeight(32)

        control.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        control.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        control.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 13px;
                padding: 3px 8px;
            }
        """)

        return control
    # =========================================================
    # CONEXIONES INTERNAS
    # =========================================================

    def _configure_connections(self) -> None:
        self.back_button.clicked.connect(
            self.back_requested.emit
        )

        self.save_button.clicked.connect(
            self.save_requested.emit
        )

        self.mark_home_button.clicked.connect(self.mark_home_requested.emit)

        self.export_button.clicked.connect(
            self.export_sdf_requested.emit
        )

        self.run_gazebo_button.clicked.connect(
            self.run_gazebo_requested.emit
        )

        self.object_tree.itemSelectionChanged.connect(
            self._update_add_button_state
        )

        self.add_object_button.clicked.connect(
            self._emit_add_object_request
        )

        self.import_structure_points_button.clicked.connect(
            self.import_structure_points_requested.emit
        )
        self.world_objects_list.currentItemChanged.connect(
            self._handle_world_object_selection
        )

        self.delete_object_button.clicked.connect(
            self._emit_delete_object_request
        )

        self._connect_property_controls()

    def _connect_property_controls(self) -> None:
        self.object_name_input.editingFinished.connect(
            self._emit_properties_edited
        )

        numeric_controls = [
            self.position_x_input,
            self.position_y_input,
            self.position_z_input,
            self.rotation_x_input,
            self.rotation_y_input,
            self.rotation_z_input,
            self.scale_input,

            self.wall_length_input,
            self.wall_thickness_input,
            self.wall_height_input,

            self.solar_module_length_input,
            self.solar_module_width_input,
            self.solar_module_thickness_input,
            self.solar_module_gap_input,
            self.solar_post_height_input,
            self.solar_post_width_input,
            self.solar_post_depth_input,
            self.solar_torque_tube_radius_input,
            self.solar_beam_thickness_input,
            self.solar_fixed_tilt_input,
            self.solar_tracker_angle_input,
            self.solar_tracker_min_angle_input,
            self.solar_tracker_max_angle_input,
            self.solar_row_spacing_input,
        ]

        integer_controls = [
            self.solar_modules_per_row_input,
            self.solar_post_count_input,
        ]

        for control in numeric_controls:
            control.editingFinished.connect(
                self._emit_properties_edited
            )

        for control in integer_controls:
            control.editingFinished.connect(
                self._emit_properties_edited
            )

        self.solar_structure_type_input.currentIndexChanged.connect(
            lambda _: self._emit_properties_edited()
        )
    # =========================================================
    # EVENTOS DE LA BIBLIOTECA
    # =========================================================

    def _update_add_button_state(self) -> None:
        selected_items = (
            self.object_tree.selectedItems()
        )

        if not selected_items:
            self.add_object_button.setEnabled(
                False
            )
            return

        selected_item = selected_items[0]

        object_type = selected_item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        self.add_object_button.setEnabled(
            object_type is not None
            and not selected_item.isDisabled()
        )

    def _emit_add_object_request(self) -> None:
        selected_items = (
            self.object_tree.selectedItems()
        )

        if not selected_items:
            return

        object_type = selected_items[0].data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        if object_type:
            self.add_object_requested.emit(
                object_type
            )

    # =========================================================
    # EVENTOS DE OBJETOS DEL MUNDO
    # =========================================================

    def _handle_world_object_selection(
        self,
        current_item: QListWidgetItem | None,
        previous_item: QListWidgetItem | None,
    ) -> None:
        del previous_item

        if current_item is None:
            self._selected_object_id = None
            self.delete_object_button.setEnabled(
                False
            )
            self.object_properties_group.setEnabled(
                False
            )
            return

        object_id = current_item.data(
            Qt.ItemDataRole.UserRole
        )

        self._selected_object_id = object_id

        self.delete_object_button.setEnabled(
            True
        )

        self.object_selected.emit(
            object_id
        )

    def _emit_delete_object_request(self) -> None:
        if self._selected_object_id is None:
            return

        self.delete_object_requested.emit(
            self._selected_object_id
        )

    # =========================================================
    # EDICIÓN DE PROPIEDADES
    # =========================================================

    def _emit_properties_edited(self) -> None:
        if self._updating_properties:
            return

        if self._selected_object_id is None:
            return

        properties = self.get_property_values()

        self.object_properties_edited.emit(
            self._selected_object_id,
            properties,
        )

    def get_property_values(self) -> dict:
        return {
            # Propiedades generales
            "name": self.object_name_input.text().strip(),
            "x": self.position_x_input.value(),
            "y": self.position_y_input.value(),
            "z": self.position_z_input.value(),
            "roll": self.rotation_x_input.value(),
            "pitch": self.rotation_y_input.value(),
            "yaw": self.rotation_z_input.value(),
            "scale": self.scale_input.value(),

            # Propiedades de muros
            "length": self.wall_length_input.value(),
            "thickness": self.wall_thickness_input.value(),
            "height": self.wall_height_input.value(),

            # Propiedades de estructuras fotovoltaicas
            "structure_type": (
                self.solar_structure_type_input.currentData()
            ),
            "modules_per_row": (
                self.solar_modules_per_row_input.value()
            ),
            "module_length": (
                self.solar_module_length_input.value()
            ),
            "module_width": (
                self.solar_module_width_input.value()
            ),
            "module_thickness": (
                self.solar_module_thickness_input.value()
            ),
            "module_gap": (
                self.solar_module_gap_input.value()
            ),
            "post_count": (
                self.solar_post_count_input.value()
            ),
            "post_height": (
                self.solar_post_height_input.value()
            ),
            "post_width": (
                self.solar_post_width_input.value()
            ),
            "post_depth": (
                self.solar_post_depth_input.value()
            ),
            "torque_tube_radius": (
                self.solar_torque_tube_radius_input.value()
            ),
            "beam_thickness": (
                self.solar_beam_thickness_input.value()
            ),
            "fixed_tilt_angle": (
                self.solar_fixed_tilt_input.value()
            ),
            "tracker_angle": (
                self.solar_tracker_angle_input.value()
            ),
            "tracker_min_angle": (
                self.solar_tracker_min_angle_input.value()
            ),
            "tracker_max_angle": (
                self.solar_tracker_max_angle_input.value()
            ),
            "row_spacing": (
                self.solar_row_spacing_input.value()
            ),
        }

    def set_property_values(
        self,
        object_id,
        object_type: str,
        properties: dict,
    ) -> None:
        self._updating_properties = True
        self._selected_object_id = object_id

        try:
            self.object_properties_group.setEnabled(
                True
            )

            is_wall = object_type == "wall"
            is_solar = object_type == "solar_structure"

            self.wall_dimensions_group.setVisible(
                is_wall
            )

            self.solar_structure_group.setVisible(
                is_solar
            )

            # Propiedades generales
            self.object_name_input.setText(
                str(properties.get("name", ""))
            )

            self.position_x_input.setValue(
                float(properties.get("x", 0.0))
            )

            self.position_y_input.setValue(
                float(properties.get("y", 0.0))
            )

            self.position_z_input.setValue(
                float(properties.get("z", 0.0))
            )

            self.rotation_x_input.setValue(
                float(properties.get("roll", 0.0))
            )

            self.rotation_y_input.setValue(
                float(properties.get("pitch", 0.0))
            )

            self.rotation_z_input.setValue(
                float(properties.get("yaw", 0.0))
            )

            self.scale_input.setValue(
                float(properties.get("scale", 1.0))
            )

            # Propiedades de muros
            self.wall_length_input.setValue(
                float(properties.get("length", 5.0))
            )

            self.wall_thickness_input.setValue(
                float(properties.get("thickness", 0.20))
            )

            self.wall_height_input.setValue(
                float(properties.get("height", 2.0))
            )

            # Tipo de estructura fotovoltaica
            structure_type = properties.get(
                "structure_type",
                "fixed",
            )

            structure_type_index = (
                self.solar_structure_type_input.findData(
                    structure_type
                )
            )

            if structure_type_index >= 0:
                self.solar_structure_type_input.setCurrentIndex(
                    structure_type_index
                )

            # Configuración de módulos
            self.solar_modules_per_row_input.setValue(
                int(
                    properties.get(
                        "modules_per_row",
                        6,
                    )
                )
            )

            self.solar_module_length_input.setValue(
                float(
                    properties.get(
                        "module_length",
                        2.20,
                    )
                )
            )

            self.solar_module_width_input.setValue(
                float(
                    properties.get(
                        "module_width",
                        1.10,
                    )
                )
            )

            self.solar_module_thickness_input.setValue(
                float(
                    properties.get(
                        "module_thickness",
                        0.04,
                    )
                )
            )

            self.solar_module_gap_input.setValue(
                float(
                    properties.get(
                        "module_gap",
                        0.05,
                    )
                )
            )

            # Configuración de postes
            self.solar_post_count_input.setValue(
                int(
                    properties.get(
                        "post_count",
                        3,
                    )
                )
            )

            self.solar_post_height_input.setValue(
                float(
                    properties.get(
                        "post_height",
                        1.80,
                    )
                )
            )

            self.solar_post_width_input.setValue(
                float(
                    properties.get(
                        "post_width",
                        0.15,
                    )
                )
            )

            self.solar_post_depth_input.setValue(
                float(
                    properties.get(
                        "post_depth",
                        0.15,
                    )
                )
            )

            # Elementos mecánicos
            self.solar_torque_tube_radius_input.setValue(
                float(
                    properties.get(
                        "torque_tube_radius",
                        0.08,
                    )
                )
            )

            self.solar_beam_thickness_input.setValue(
                float(
                    properties.get(
                        "beam_thickness",
                        0.10,
                    )
                )
            )

            # Ángulos de funcionamiento
            self.solar_fixed_tilt_input.setValue(
                float(
                    properties.get(
                        "fixed_tilt_angle",
                        20.0,
                    )
                )
            )

            self.solar_tracker_angle_input.setValue(
                float(
                    properties.get(
                        "tracker_angle",
                        0.0,
                    )
                )
            )

            self.solar_tracker_min_angle_input.setValue(
                float(
                    properties.get(
                        "tracker_min_angle",
                        -60.0,
                    )
                )
            )

            self.solar_tracker_max_angle_input.setValue(
                float(
                    properties.get(
                        "tracker_max_angle",
                        60.0,
                    )
                )
            )

            self.solar_row_spacing_input.setValue(
                float(
                    properties.get(
                        "row_spacing",
                        4.0,
                    )
                )
            )

        finally:
            self._updating_properties = False

    def clear_property_values(self) -> None:
        self._updating_properties = True
        self._selected_object_id = None

        try:
            self.object_properties_group.setEnabled(
                False
            )

            self.wall_dimensions_group.setVisible(
                False
            )

            self.solar_structure_group.setVisible(
                False
            )

            self.object_name_input.clear()

            self.delete_object_button.setEnabled(
                False
            )

        finally:
            self._updating_properties = False
    # =========================================================
    # CONFIGURACIÓN DEL PROYECTO Y TERRENO
    # =========================================================

    def configure_project(
        self,
        name: str,
        width: float,
        length: float,
    ) -> None:
        self.project_label.setText(
            f"{name} — {width:.2f} × "
            f"{length:.2f} m"
        )

        self.configure_terrain(
            width=width,
            length=length,
        )

    def configure_terrain(
        self,
        width: float,
        length: float,
    ) -> None:
        if self.terrain_item is not None:
            self.scene_3d.removeItem(
                self.terrain_item
            )

        if self.terrain_outline_item is not None:
            self.scene_3d.removeItem(
                self.terrain_outline_item
            )

        vertices = np.array(
            [
                [-width / 2, -length / 2, 0],
                [width / 2, -length / 2, 0],
                [width / 2, length / 2, 0],
                [-width / 2, length / 2, 0],
            ],
            dtype=float,
        )

        faces = np.array(
            [
                [0, 1, 2],
                [0, 2, 3],
            ],
            dtype=int,
        )

        terrain_mesh = gl.MeshData(
            vertexes=vertices,
            faces=faces,
        )

        self.terrain_item = gl.GLMeshItem(
            meshdata=terrain_mesh,
            smooth=False,
            shader="shaded",
            color=(0.22, 0.30, 0.22, 0.75),
        )

        self.scene_3d.addItem(
            self.terrain_item
        )

        outline_points = np.array(
            [
                [-width / 2, -length / 2, 0.02],
                [width / 2, -length / 2, 0.02],
                [width / 2, length / 2, 0.02],
                [-width / 2, length / 2, 0.02],
                [-width / 2, -length / 2, 0.02],
            ],
            dtype=float,
        )

        self.terrain_outline_item = (
            gl.GLLinePlotItem(
                pos=outline_points,
                width=3,
                antialias=True,
            )
        )

        self.scene_3d.addItem(
            self.terrain_outline_item
        )

        self.grid_item.setSize(
            width,
            length,
        )

        self.grid_item.setSpacing(
            1,
            1,
        )

        maximum_size = max(
            width,
            length,
        )

        self.scene_3d.setCameraPosition(
            distance=max(
                15,
                maximum_size * 1.1,
            ),
            elevation=45,
            azimuth=45,
        )

        self.status_label.setText(
            f"Terreno creado: {width:.2f} × "
            f"{length:.2f} metros."
        )

    # =========================================================
    # LISTA DE OBJETOS
    # =========================================================

    def add_world_object(
        self,
        object_id,
        display_name: str,
    ) -> None:
        item = QListWidgetItem(
            display_name
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            object_id,
        )

        self.world_objects_list.addItem(item)
        self.world_objects_list.setCurrentItem(
            item
        )

    def update_world_object_name(
        self,
        object_id,
        new_name: str,
    ) -> None:
        item = self._find_world_object_item(
            object_id
        )

        if item is not None:
            item.setText(new_name)

    def remove_world_object(
        self,
        object_id,
    ) -> None:
        item = self._find_world_object_item(
            object_id
        )

        if item is None:
            return

        row = self.world_objects_list.row(item)

        self.world_objects_list.takeItem(row)
        self.clear_property_values()

    def clear_world_objects(self) -> None:
        self.world_objects_list.clear()
        self.clear_property_values()

    def select_world_object(
        self,
        object_id,
    ) -> None:
        item = self._find_world_object_item(
            object_id
        )

        if item is not None:
            self.world_objects_list.setCurrentItem(
                item
            )

    def _find_world_object_item(
        self,
        object_id,
    ) -> QListWidgetItem | None:
        for index in range(
            self.world_objects_list.count()
        ):
            item = self.world_objects_list.item(
                index
            )

            stored_id = item.data(
                Qt.ItemDataRole.UserRole
            )

            if stored_id == object_id:
                return item

        return None

    # =========================================================
    # MÉTODOS DE APOYO PARA EL CONTROLADOR
    # =========================================================

    def add_scene_item(self, scene_item) -> None:
        self.scene_3d.addItem(scene_item)

    def remove_scene_item(self, scene_item) -> None:
        self.scene_3d.removeItem(scene_item)

    def set_status_message(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(message)

    def set_home_coordinates(self, x: float, y: float, z: float) -> None:
        self.home_x_input.blockSignals(True)
        self.home_y_input.blockSignals(True)

        self.home_x_input.setValue(x)
        self.home_y_input.setValue(y)
        self.home_z_input.setValue(z)

        self.home_x_input.blockSignals(False)
        self.home_y_input.blockSignals(False)

        self.home_group.setVisible(True)


    def clear_home_coordinates(self) -> None:
        self.home_group.setVisible(False)

    def should_generate_solar_structures(self) -> bool:
        return self.generate_solar_structures_checkbox.isChecked()

    def set_navigation_routes_enabled(self, enabled: bool) -> None:
        self.mark_dockout_button.setEnabled(enabled)
        self.generate_work_route_button.setEnabled(enabled)

    def _start_work_route_selection(self) -> None:
        self._home_selection_mode = False
        self._perimeter_selection_mode = False
        self._dockout_selection_mode = False

        self.mark_home_button.setText("Marcar Home")
        self.mark_perimeter_button.setText("Marcar perímetro")
        self.mark_dockout_button.setText("Marcar Dock Out")

        self._work_direction_selection = "x"
        self.generate_work_route_button.setText("Marque sentido X...")

        self.cancel_work_route_button.setVisible(True)

        self.start_work_route_requested.emit()


    def show_work_route_group(self) -> None:
        self.work_route_group.setVisible(True)


    def set_work_direction_label(self, direction: str, x: float, y: float) -> None:
        text = f"({x:.3f}, {y:.3f})"

        if direction == "x":
            self.work_x_direction_label.setText(text)

        elif direction == "y":
            self.work_y_direction_label.setText(text)

    def _cancel_work_route_selection(self) -> None:
        self._work_direction_selection = None
        self.generate_work_route_button.setText("Generar ruta de trabajo")
        self.cancel_work_route_button.setVisible(False)
        self.cancel_work_route_requested.emit()

    def get_work_route_parameters(self) -> tuple[float, float]:
        return self.work_width_input.value(), self.work_overlap_input.value()
