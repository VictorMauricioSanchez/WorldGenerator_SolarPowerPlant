import numpy as np
import pyqtgraph.opengl as gl

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class StartPage(QWidget):
    """
    Pantalla de configuración inicial del proyecto.

    Esta clase contiene únicamente la interfaz gráfica. No crea proyectos
    ni genera archivos SDF. Cuando el usuario pulsa el botón correspondiente,
    emite una señal para que el controlador procese la solicitud.
    """

    create_from_scratch_requested = pyqtSignal(
        str,
        float,
        float,
    )

    terrain_import_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()

        self.rotation_timer = QTimer(self)

        self._create_interface()
        self._configure_connections()
        self._start_3d_animation()

    # =========================================================
    # CREACIÓN DE LA INTERFAZ
    # =========================================================

    def _create_interface(self) -> None:
        title = QLabel("Vista previa del mundo")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            padding: 8px;
        """)

        self._create_3d_preview()
        creation_mode_group = self._create_mode_selector()
        self.mode_pages = self._create_mode_pages()

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 15, 20, 20)
        main_layout.setSpacing(12)

        main_layout.addWidget(title)
        main_layout.addWidget(self.preview_3d)
        main_layout.addWidget(creation_mode_group)
        main_layout.addWidget(self.mode_pages)

        self.setLayout(main_layout)

    def _create_3d_preview(self) -> None:
        self.preview_3d = gl.GLViewWidget()
        self.preview_3d.setMinimumHeight(430)
        self.preview_3d.setBackgroundColor("#101010")

        self.preview_3d.setCameraPosition(
            distance=30,
            elevation=25,
            azimuth=45,
        )

        grid = gl.GLGridItem()
        grid.setSize(20, 20)
        grid.setSpacing(1, 1)
        self.preview_3d.addItem(grid)

        axes = gl.GLAxisItem()
        axes.setSize(5, 5, 5)
        self.preview_3d.addItem(axes)

        sphere_mesh = gl.MeshData.sphere(
            rows=30,
            cols=60,
            radius=2,
        )

        self.animated_object = gl.GLMeshItem(
            meshdata=sphere_mesh,
            smooth=True,
            shader="shaded",
            color=(0.8, 0.15, 0.15, 1.0),
        )

        self.animated_object.translate(0, 0, 2)
        self.preview_3d.addItem(self.animated_object)

        self.animated_rings = []

        for radius in (3.0, 4.0, 5.0):
            angles = np.linspace(
                0,
                2 * np.pi,
                200,
            )

            points = np.column_stack(
                (
                    radius * np.cos(angles),
                    radius * np.sin(angles),
                    np.full_like(angles, 2.0),
                )
            )

            ring = gl.GLLinePlotItem(
                pos=points,
                width=2,
                antialias=True,
            )

            self.preview_3d.addItem(ring)
            self.animated_rings.append(ring)

    def _create_mode_selector(self) -> QGroupBox:
        group = QGroupBox(
            "Modo de creación del mundo"
        )

        self.create_from_scratch_radio = QRadioButton(
            "Generar mundo desde cero"
        )

        self.import_terrain_radio = QRadioButton(
            "Cargar archivo de terreno"
        )

        self.create_from_scratch_radio.setChecked(True)

        self.mode_button_group = QButtonGroup(self)

        self.mode_button_group.addButton(
            self.create_from_scratch_radio,
            0,
        )

        self.mode_button_group.addButton(
            self.import_terrain_radio,
            1,
        )

        layout = QHBoxLayout()
        layout.addWidget(
            self.create_from_scratch_radio
        )
        layout.addWidget(
            self.import_terrain_radio
        )
        layout.addStretch()

        group.setLayout(layout)

        return group

    def _create_mode_pages(self) -> QStackedWidget:
        pages = QStackedWidget()

        pages.addWidget(
            self._create_from_scratch_page()
        )

        pages.addWidget(
            self._create_terrain_import_page()
        )

        return pages

    def _create_from_scratch_page(self) -> QWidget:
        page = QWidget()

        configuration_group = QGroupBox(
            "Configuración del mundo nuevo"
        )

        self.world_name_input = QLineEdit()
        self.world_name_input.setText("mi_mundo")
        self.world_name_input.setPlaceholderText(
            "Nombre del proyecto"
        )

        self.world_width_input = QDoubleSpinBox()
        self.world_width_input.setRange(
            1.0,
            1000.0,
        )
        self.world_width_input.setValue(20.0)
        self.world_width_input.setDecimals(2)
        self.world_width_input.setSuffix(" m")

        self.world_length_input = QDoubleSpinBox()
        self.world_length_input.setRange(
            1.0,
            1000.0,
        )
        self.world_length_input.setValue(20.0)
        self.world_length_input.setDecimals(2)
        self.world_length_input.setSuffix(" m")

        form = QFormLayout()
        form.addRow(
            "Nombre:",
            self.world_name_input,
        )
        form.addRow(
            "Ancho:",
            self.world_width_input,
        )
        form.addRow(
            "Largo:",
            self.world_length_input,
        )

        configuration_group.setLayout(form)

        self.open_editor_button = QPushButton(
            "Crear mundo y abrir editor"
        )
        self.open_editor_button.setMinimumHeight(44)

        layout = QVBoxLayout()
        layout.addWidget(configuration_group)
        layout.addWidget(self.open_editor_button)

        page.setLayout(layout)

        return page

    def _create_terrain_import_page(self) -> QWidget:
        page = QWidget()

        terrain_group = QGroupBox(
            "Importación de terreno"
        )

        message = QLabel(
            "Esta sección queda reservada para cargar un "
            "archivo de terreno. Posteriormente, el terreno "
            "importado también se abrirá dentro del editor."
        )
        message.setWordWrap(True)

        self.terrain_path_input = QLineEdit()
        self.terrain_path_input.setReadOnly(True)
        self.terrain_path_input.setPlaceholderText(
            "Ruta del archivo de terreno"
        )

        self.select_terrain_button = QPushButton(
            "Seleccionar archivo"
        )
        self.select_terrain_button.setEnabled(True)

        self.open_imported_terrain_button = QPushButton(
            "Cargar terreno y abrir editor"
        )
        self.open_imported_terrain_button.setEnabled(False)
        self.open_imported_terrain_button.setMinimumHeight(44)

        form = QFormLayout()
        form.addRow(
            "Archivo:",
            self.terrain_path_input,
        )

        terrain_layout = QVBoxLayout()
        terrain_layout.addWidget(message)
        terrain_layout.addLayout(form)
        terrain_layout.addWidget(
            self.select_terrain_button
        )

        terrain_group.setLayout(terrain_layout)

        layout = QVBoxLayout()
        layout.addWidget(terrain_group)
        layout.addWidget(
            self.open_imported_terrain_button
        )

        page.setLayout(layout)

        return page

    # =========================================================
    # SEÑALES Y EVENTOS
    # =========================================================

    def _configure_connections(self) -> None:
        self.mode_button_group.idClicked.connect(
            self.mode_pages.setCurrentIndex
        )

        self.open_editor_button.clicked.connect(
            self._emit_create_from_scratch_request
        )

        self.select_terrain_button.clicked.connect(
            self._select_terrain_file
        )

        self.open_imported_terrain_button.clicked.connect(
            self._emit_terrain_import_request
        )

    def _emit_create_from_scratch_request(self) -> None:
        self.create_from_scratch_requested.emit(
            self.world_name_input.text(),
            self.world_width_input.value(),
            self.world_length_input.value(),
        )

    def _select_terrain_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar modelo digital del terreno",
            "",
            "GeoTIFF (*.tif *.tiff)",
        )

        if not file_path:
            return

        self.terrain_path_input.setText(
            file_path
        )

        self.open_imported_terrain_button.setEnabled(
            True
        )

    def _emit_terrain_import_request(self) -> None:
        self.terrain_import_requested.emit(
            self.terrain_path_input.text()
        )

    # =========================================================
    # ANIMACIÓN DE LA VISTA PREVIA
    # =========================================================

    def _start_3d_animation(self) -> None:
        self.rotation_timer.setInterval(30)
        self.rotation_timer.timeout.connect(
            self._animate_3d_preview
        )
        self.rotation_timer.start()

    def _animate_3d_preview(self) -> None:
        self.animated_object.rotate(
            1,
            0,
            0,
            1,
            local=False,
        )

        for index, ring in enumerate(
            self.animated_rings
        ):
            speed = 0.3 + index * 0.2

            ring.rotate(
                speed,
                1,
                0,
                0,
                local=False,
            )
