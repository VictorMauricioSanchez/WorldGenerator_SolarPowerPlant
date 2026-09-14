from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal
from uuid import uuid4


SolarStructureType = Literal[
    "fixed",
    "single_row_tracker",
    "dual_row_tracker",
]


@dataclass
class SolarStructure:
    """
    Representa una estructura fotovoltaica paramétrica.

    Tipos disponibles:

    - fixed:
      Estructura fija con un ángulo de inclinación constante.

    - single_row_tracker:
      Seguidor de un eje con una sola fila.

    - dual_row_tracker:
      Seguidor de un eje con dos filas paralelas sincronizadas.

    La posición Z representa la elevación de la base respecto
    al terreno. Normalmente su valor inicial será cero.
    """

    VALID_STRUCTURE_TYPES: ClassVar[set[str]] = {
        "fixed",
        "single_row_tracker",
        "dual_row_tracker",
    }

    EDITABLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "structure_type",
        "x",
        "y",
        "z",
        "roll",
        "pitch",
        "yaw",
        "scale",
        "modules_per_row",
        "module_length",
        "module_width",
        "module_thickness",
        "module_gap",
        "post_count",
        "post_height",
        "post_width",
        "post_depth",
        "torque_tube_radius",
        "beam_thickness",
        "fixed_tilt_angle",
        "tracker_angle",
        "tracker_min_angle",
        "tracker_max_angle",
        "row_spacing",
    )

    name: str = "estructura_fotovoltaica"

    structure_type: SolarStructureType = "fixed"

    # Posición de la estructura completa
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # Orientación global de la estructura
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    scale: float = 1.0

    # Configuración de los módulos fotovoltaicos
    modules_per_row: int = 6

    # Dimensión del módulo a lo largo de la fila
    module_length: float = 2.20

    # Dimensión perpendicular a la fila
    module_width: float = 1.10

    module_thickness: float = 0.04
    module_gap: float = 0.05

    # Configuración de los postes
    post_count: int = 3
    post_height: float = 1.80
    post_width: float = 0.15
    post_depth: float = 0.15

    # Coordenadas locales reales de los postes obtenidas del CSV.
    # Cada punto contiene (x, y, z) en el mundo Gazebo.
    post_points: list[tuple[float, float, float]] = field(
        default_factory=list
    )

    # Elementos mecánicos principales
    torque_tube_radius: float = 0.08
    beam_thickness: float = 0.10

    # Ángulo utilizado solamente por la estructura fija
    fixed_tilt_angle: float = 20.0

    # Ángulo actual de los seguidores
    tracker_angle: float = 0.0
    tracker_min_angle: float = -60.0
    tracker_max_angle: float = 60.0

    # Distancia entre los centros de las dos filas del dual-row
    row_spacing: float = 4.0

    object_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    object_type: str = field(
        default="solar_structure",
        init=False,
    )

    def __post_init__(self) -> None:
        self.validate()

    # =========================================================
    # VALIDACIÓN
    # =========================================================

    def validate(self) -> None:
        self.name = self.name.strip()

        if not self.name:
            raise ValueError(
                "La estructura fotovoltaica debe tener un nombre."
            )

        if self.structure_type not in self.VALID_STRUCTURE_TYPES:
            raise ValueError(
                "El tipo de estructura fotovoltaica no es válido."
            )

        if self.scale <= 0:
            raise ValueError(
                "La escala debe ser mayor que cero."
            )

        if self.modules_per_row < 1:
            raise ValueError(
                "Debe existir al menos un módulo por fila."
            )

        if self.module_length <= 0:
            raise ValueError(
                "El largo del módulo debe ser mayor que cero."
            )

        if self.module_width <= 0:
            raise ValueError(
                "El ancho del módulo debe ser mayor que cero."
            )

        if self.module_thickness <= 0:
            raise ValueError(
                "El espesor del módulo debe ser mayor que cero."
            )

        if self.module_gap < 0:
            raise ValueError(
                "La separación entre módulos no puede ser negativa."
            )

        if self.post_count < 2:
            raise ValueError(
                "La estructura debe tener al menos dos postes."
            )

        if self.post_height <= 0:
            raise ValueError(
                "La altura de los postes debe ser mayor que cero."
            )

        if self.post_width <= 0 or self.post_depth <= 0:
            raise ValueError(
                "Las dimensiones de los postes deben ser mayores que cero."
            )

        if self.torque_tube_radius <= 0:
            raise ValueError(
                "El radio del tubo de torsión debe ser mayor que cero."
            )

        if self.beam_thickness <= 0:
            raise ValueError(
                "El espesor de las vigas debe ser mayor que cero."
            )

        if not -90.0 <= self.fixed_tilt_angle <= 90.0:
            raise ValueError(
                "La inclinación fija debe estar entre -90° y 90°."
            )

        if self.tracker_min_angle >= self.tracker_max_angle:
            raise ValueError(
                "El ángulo mínimo debe ser menor que el ángulo máximo."
            )

        if not -90.0 <= self.tracker_min_angle <= 90.0:
            raise ValueError(
                "El límite mínimo del seguidor debe estar "
                "entre -90° y 90°."
            )

        if not -90.0 <= self.tracker_max_angle <= 90.0:
            raise ValueError(
                "El límite máximo del seguidor debe estar "
                "entre -90° y 90°."
            )

        if not (
            self.tracker_min_angle
            <= self.tracker_angle
            <= self.tracker_max_angle
        ):
            raise ValueError(
                "El ángulo actual del seguidor debe estar "
                "dentro de sus límites."
            )

        if (
            self.structure_type == "dual_row_tracker"
            and self.row_spacing <= 0
        ):
            raise ValueError(
                "La separación entre las dos filas debe ser "
                "mayor que cero."
            )

    # =========================================================
    # ACTUALIZACIÓN
    # =========================================================

    def update(
        self,
        properties: dict[str, Any],
    ) -> None:
        """
        Actualiza las propiedades de la estructura.

        Si algún dato no es válido, restaura automáticamente
        todos los valores anteriores.
        """

        previous_values = self.to_dict()

        try:
            for key, value in properties.items():
                if key in self.EDITABLE_FIELDS:
                    setattr(self, key, value)

            self.validate()

        except (TypeError, ValueError):
            self._restore_values(previous_values)
            raise

    def _restore_values(
        self,
        previous_values: dict[str, Any],
    ) -> None:
        for field_name in self.EDITABLE_FIELDS:
            setattr(
                self,
                field_name,
                previous_values[field_name],
            )

    # =========================================================
    # PROPIEDADES CALCULADAS
    # =========================================================

    @property
    def row_count(self) -> int:
        """
        Devuelve la cantidad de filas de la estructura.
        """

        if self.structure_type == "dual_row_tracker":
            return 2

        return 1

    @property
    def is_tracker(self) -> bool:
        return self.structure_type in {
            "single_row_tracker",
            "dual_row_tracker",
        }

    @property
    def active_angle(self) -> float:
        """
        Devuelve el ángulo que debe aplicarse a los paneles.
        """

        if self.structure_type == "fixed":
            return self.fixed_tilt_angle

        return self.tracker_angle

    def get_row_length(self) -> float:
        """
        Calcula la longitud total de una fila de módulos,
        incluyendo las separaciones.
        """

        modules_length = (
            self.modules_per_row
            * self.module_length
        )

        gaps_length = (
            max(0, self.modules_per_row - 1)
            * self.module_gap
        )

        return modules_length + gaps_length

    def get_row_offsets(self) -> tuple[float, ...]:
        """
        Devuelve la posición lateral de cada fila respecto
        al centro de la estructura.
        """

        if self.structure_type == "dual_row_tracker":
            half_spacing = self.row_spacing / 2.0

            return (
                -half_spacing,
                half_spacing,
            )

        return (0.0,)

    # =========================================================
    # SERIALIZACIÓN
    # =========================================================

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "name": self.name,
            "structure_type": self.structure_type,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "scale": self.scale,
            "modules_per_row": self.modules_per_row,
            "module_length": self.module_length,
            "module_width": self.module_width,
            "module_thickness": self.module_thickness,
            "module_gap": self.module_gap,
            "post_count": self.post_count,
            "post_height": self.post_height,
            "post_width": self.post_width,
            "post_depth": self.post_depth,
            "torque_tube_radius": self.torque_tube_radius,
            "beam_thickness": self.beam_thickness,
            "fixed_tilt_angle": self.fixed_tilt_angle,
            "tracker_angle": self.tracker_angle,
            "tracker_min_angle": self.tracker_min_angle,
            "tracker_max_angle": self.tracker_max_angle,
            "row_spacing": self.row_spacing,
        }
