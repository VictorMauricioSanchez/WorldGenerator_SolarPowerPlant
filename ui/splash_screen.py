from pathlib import Path

from PyQt6.QtCore import (
    QElapsedTimer,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class SplashScreen(QWidget):
    """
    Pantalla de inicio de la aplicación.

    Muestra una imagen con bordes redondeados y una barra de progreso.
    Cuando termina el tiempo configurado, emite la señal `finished`.
    """

    finished = pyqtSignal()

    def __init__(
        self,
        image_path: Path,
        duration_ms: int = 7000,
    ) -> None:
        super().__init__()

        self.image_path = Path(image_path)
        self.duration_ms = duration_ms

        self.elapsed_timer = QElapsedTimer()
        self.update_timer = QTimer(self)

        self._configure_window()
        self._create_interface()
        self._configure_timer()

    def _configure_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setFixedSize(920, 570)

    def _create_interface(self) -> None:
        original_image = QPixmap(str(self.image_path))

        if original_image.isNull():
            raise FileNotFoundError(
                f"No se pudo cargar la imagen: {self.image_path}"
            )

        rounded_image = self._create_rounded_image(
            image=original_image,
            size=QSize(900, 506),
            radius=25,
        )

        self.image_label = QLabel()
        self.image_label.setPixmap(rounded_image)
        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Cargando... %p%")
        self.progress_bar.setFixedHeight(24)

        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #151515;
                color: white;
                border: 1px solid #555555;
                border-radius: 11px;
                text-align: center;
                font-weight: bold;
            }

            QProgressBar::chunk {
                background-color: #d71920;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        layout.addWidget(self.image_label)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def _configure_timer(self) -> None:
        self.update_timer.setInterval(30)
        self.update_timer.timeout.connect(
            self._update_progress
        )

    @staticmethod
    def _create_rounded_image(
        image: QPixmap,
        size: QSize,
        radius: float,
    ) -> QPixmap:
        scaled_image = image.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        crop_x = max(
            0,
            (scaled_image.width() - size.width()) // 2,
        )

        crop_y = max(
            0,
            (scaled_image.height() - size.height()) // 2,
        )

        scaled_image = scaled_image.copy(
            crop_x,
            crop_y,
            size.width(),
            size.height(),
        )

        result = QPixmap(size)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        clipping_path = QPainterPath()
        clipping_path.addRoundedRect(
            QRectF(
                0,
                0,
                size.width(),
                size.height(),
            ),
            radius,
            radius,
        )

        painter.setClipPath(clipping_path)
        painter.drawPixmap(0, 0, scaled_image)
        painter.end()

        return result

    def show_centered(self) -> None:
        screen = QApplication.primaryScreen()

        if screen is not None:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()

            window_geometry.moveCenter(
                screen_geometry.center()
            )

            self.move(window_geometry.topLeft())

        self.progress_bar.setValue(0)
        self.show()

        self.elapsed_timer.start()
        self.update_timer.start()

    def _update_progress(self) -> None:
        elapsed_ms = self.elapsed_timer.elapsed()

        percentage = int(
            elapsed_ms / self.duration_ms * 100
        )

        self.progress_bar.setValue(
            min(percentage, 100)
        )

        if elapsed_ms >= self.duration_ms:
            self.update_timer.stop()
            self.progress_bar.setValue(100)

            self.close()
            self.finished.emit()
