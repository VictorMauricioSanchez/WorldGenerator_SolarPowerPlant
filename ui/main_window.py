from PyQt6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
)

from ui.editor_page import EditorPage
from ui.start_page import StartPage


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación.

    Su responsabilidad es contener las distintas páginas y cambiar
    entre ellas. No crea proyectos, no añade objetos y no genera SDF.
    Esas operaciones pertenecen a los controladores.
    """

    def __init__(self) -> None:
        super().__init__()

        self._configure_window()
        self._create_pages()

    # =========================================================
    # CONFIGURACIÓN DE LA VENTANA
    # =========================================================

    def _configure_window(self) -> None:
        self.setWindowTitle(
            "Generador de Mundos"
        )

        self.resize(
            1100,
            850,
        )

        self.setMinimumSize(
            900,
            650,
        )

    # =========================================================
    # CREACIÓN DE LAS PÁGINAS
    # =========================================================

    def _create_pages(self) -> None:
        self.page_stack = QStackedWidget()

        self.start_page = StartPage()
        self.editor_page = EditorPage()

        self.page_stack.addWidget(
            self.start_page
        )

        self.page_stack.addWidget(
            self.editor_page
        )

        self.setCentralWidget(
            self.page_stack
        )
        
        self.page_stack.setCurrentWidget(self.start_page)

        self.setWindowTitle("Generador de Mundos")

    # =========================================================
    # NAVEGACIÓN
    # =========================================================

    def show_start_page(self) -> None:
        """
        Muestra la pantalla de configuración inicial.
        """

        self.page_stack.setCurrentWidget(
            self.start_page
        )

        self.setWindowTitle(
            "Generador de Mundos"
        )

        self.showNormal()

    def show_editor_page(
        self,
        project_name: str,
    ) -> None:
        """
        Muestra el editor del mundo.
        """

        self.page_stack.setCurrentWidget(
            self.editor_page
        )

        self.setWindowTitle(
            f"Generador de Mundos — {project_name}"
        )

        self.showMaximized()

    # =========================================================
    # CONSULTAS
    # =========================================================

    def is_editor_visible(self) -> bool:
        """
        Indica si el editor es la página actualmente visible.
        """

        return (
            self.page_stack.currentWidget()
            is self.editor_page
        )

    def is_start_page_visible(self) -> bool:
        """
        Indica si la configuración inicial está visible.
        """

        return (
            self.page_stack.currentWidget()
            is self.start_page
        )
