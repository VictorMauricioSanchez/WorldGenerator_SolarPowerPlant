from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Wall:
    """
    Representa un muro paramétrico dentro del mundo.

    Las posiciones y dimensiones se expresan en metros.
    Las rotaciones se almacenan en grados para coincidir con la interfaz.
    """

    name: str = "muro"

    x: float = 0.0
    y: float = 0.0
    z: float = 1.0

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    scale: float = 1.0

    length: float = 5.0
    thickness: float = 0.20
    height: float = 2.0

    object_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    object_type: str = field(
        default="wall",
        init=False,
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """
        Comprueba que el muro tenga valores físicamente válidos.
        """

        self.name = self.name.strip()

        if not self.name:
            raise ValueError(
                "El muro debe tener un nombre."
            )

        if self.scale <= 0:
            raise ValueError(
                "La escala del muro debe ser mayor que cero."
            )

        if self.length <= 0:
            raise ValueError(
                "El largo del muro debe ser mayor que cero."
            )

        if self.thickness <= 0:
            raise ValueError(
                "El espesor del muro debe ser mayor que cero."
            )

        if self.height <= 0:
            raise ValueError(
                "La altura del muro debe ser mayor que cero."
            )

    def update(self, properties: dict[str, Any]) -> None:
        """
        Actualiza las propiedades del muro usando los datos
        recibidos desde la interfaz.
        """

        editable_properties = {
            "name",
            "x",
            "y",
            "z",
            "roll",
            "pitch",
            "yaw",
            "scale",
            "length",
            "thickness",
            "height",
        }

        previous_values = self.to_dict()

        try:
            for key, value in properties.items():
                if key in editable_properties:
                    setattr(self, key, value)

            self.validate()

        except (TypeError, ValueError):
            self._restore_values(previous_values)
            raise

    def _restore_values(
        self,
        previous_values: dict[str, Any],
    ) -> None:
        """
        Restaura los valores anteriores cuando una actualización
        contiene datos inválidos.
        """

        for key in (
            "name",
            "x",
            "y",
            "z",
            "roll",
            "pitch",
            "yaw",
            "scale",
            "length",
            "thickness",
            "height",
        ):
            setattr(
                self,
                key,
                previous_values[key],
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Devuelve las propiedades del muro en un diccionario.
        """

        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "scale": self.scale,
            "length": self.length,
            "thickness": self.thickness,
            "height": self.height,
        }

    def get_scaled_dimensions(
        self,
    ) -> tuple[float, float, float]:
        """
        Retorna largo, espesor y altura aplicando la escala.
        """

        return (
            self.length * self.scale,
            self.thickness * self.scale,
            self.height * self.scale,
        )
