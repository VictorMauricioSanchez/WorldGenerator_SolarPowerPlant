import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from controllers.editor_controller import EditorController
from controllers.project_controller import ProjectController
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen


def main() -> int:
    app = QApplication(sys.argv)

    project_directory = Path(__file__).resolve().parent
    splash_image_path = project_directory / "splash.png"

    if not splash_image_path.exists():
        print(
            f"No se encontró la imagen de inicio: "
            f"{splash_image_path}"
        )
        return 1

    # Interfaz principal
    main_window = MainWindow()

    # Controladores
    editor_controller = EditorController(
        editor_page=main_window.editor_page
    )

    project_controller = ProjectController(
        main_window=main_window,
        editor_controller=editor_controller,
    )

    # Conservamos referencias durante toda la ejecución.
    app.editor_controller = editor_controller
    app.project_controller = project_controller

    # Pantalla de inicio
    splash_screen = SplashScreen(
        image_path=splash_image_path,
        duration_ms=7000,
    )

    app.splash_screen = splash_screen

    splash_screen.finished.connect(
        main_window.show
    )

    splash_screen.show_centered()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
