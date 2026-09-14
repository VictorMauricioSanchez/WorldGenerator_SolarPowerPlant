from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4


class WorldObject(Protocol):
    """
    Contrato mínimo que deben cumplir los objetos del mundo.

    Gracias a este protocolo, WorldProject podrá almacenar muros,
    calles, edificios, paneles y otros objetos sin depender de una
    clase concreta.
    """

    object_id: str
    object_type: str
    name: str

    def update(
        self,
        properties: dict[str, Any],
    ) -> None:
        ...

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass
class WorldProject:
    """
    Representa un proyecto completo de generación de mundo.

    Contiene:

    - Nombre del proyecto.
    - Dimensiones del terreno.
    - Método de creación.
    - Ruta opcional de un terreno importado.
    - Objetos añadidos al mundo.
    """

    name: str
    width: float
    length: float

    creation_mode: str = "scratch"
    terrain_path: str | None = None

    project_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    _objects: dict[str, WorldObject] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.validate()

    # =========================================================
    # VALIDACIÓN DEL PROYECTO
    # =========================================================

    def validate(self) -> None:
        self.name = self.name.strip()

        if not self.name:
            raise ValueError(
                "El proyecto debe tener un nombre."
            )

        if self.width <= 0:
            raise ValueError(
                "El ancho del mundo debe ser mayor que cero."
            )

        if self.length <= 0:
            raise ValueError(
                "El largo del mundo debe ser mayor que cero."
            )

        valid_modes = {
            "scratch",
            "terrain",
        }

        if self.creation_mode not in valid_modes:
            raise ValueError(
                "El modo de creación del proyecto no es válido."
            )

        if (
            self.creation_mode == "terrain"
            and not self.terrain_path
        ):
            raise ValueError(
                "Debe proporcionarse la ruta del terreno importado."
            )

    # =========================================================
    # ADMINISTRACIÓN DE OBJETOS
    # =========================================================

    def add_object(
        self,
        world_object: WorldObject,
    ) -> None:
        """
        Añade un objeto al proyecto.

        No permite identificadores ni nombres duplicados.
        """

        if world_object.object_id in self._objects:
            raise ValueError(
                "Ya existe un objeto con ese identificador."
            )

        if self.has_object_name(world_object.name):
            raise ValueError(
                f"Ya existe un objeto llamado "
                f"'{world_object.name}'."
            )

        self._objects[
            world_object.object_id
        ] = world_object

    def remove_object(
        self,
        object_id: str,
    ) -> WorldObject:
        """
        Elimina un objeto y devuelve la instancia eliminada.
        """

        if object_id not in self._objects:
            raise KeyError(
                "El objeto solicitado no existe."
            )

        return self._objects.pop(object_id)

    def get_object(
        self,
        object_id: str,
    ) -> WorldObject:
        """
        Obtiene un objeto mediante su identificador.
        """

        if object_id not in self._objects:
            raise KeyError(
                "El objeto solicitado no existe."
            )

        return self._objects[object_id]

    def update_object(
        self,
        object_id: str,
        properties: dict[str, Any],
    ) -> WorldObject:
        """
        Actualiza un objeto existente.

        Antes de cambiar su nombre, comprueba que no exista otro
        objeto con el mismo nombre.
        """

        world_object = self.get_object(object_id)

        new_name = str(
            properties.get(
                "name",
                world_object.name,
            )
        ).strip()

        if (
            new_name != world_object.name
            and self.has_object_name(
                new_name,
                exclude_object_id=object_id,
            )
        ):
            raise ValueError(
                f"Ya existe un objeto llamado "
                f"'{new_name}'."
            )

        world_object.update(properties)

        return world_object

    def clear_objects(self) -> None:
        """
        Elimina todos los objetos del proyecto.
        """

        self._objects.clear()

    # =========================================================
    # CONSULTAS
    # =========================================================

    def get_all_objects(
        self,
    ) -> tuple[WorldObject, ...]:
        """
        Devuelve todos los objetos como una colección de solo lectura.
        """

        return tuple(
            self._objects.values()
        )

    def get_objects_by_type(
        self,
        object_type: str,
    ) -> tuple[WorldObject, ...]:
        """
        Devuelve solamente los objetos del tipo indicado.
        """

        return tuple(
            world_object
            for world_object in self._objects.values()
            if world_object.object_type == object_type
        )

    def has_object(
        self,
        object_id: str,
    ) -> bool:
        return object_id in self._objects

    def has_object_name(
        self,
        name: str,
        exclude_object_id: str | None = None,
    ) -> bool:
        normalized_name = name.strip()

        return any(
            world_object.name == normalized_name
            and world_object.object_id
            != exclude_object_id
            for world_object in self._objects.values()
        )

    def object_count(self) -> int:
        return len(self._objects)

    # =========================================================
    # GENERACIÓN DE NOMBRES
    # =========================================================

    def generate_unique_name(
        self,
        base_name: str,
    ) -> str:
        """
        Genera nombres consecutivos, por ejemplo:

        muro_1
        muro_2
        muro_3
        """

        clean_base_name = (
            base_name.strip() or "objeto"
        )

        index = 1

        while True:
            candidate = (
                f"{clean_base_name}_{index}"
            )

            if not self.has_object_name(candidate):
                return candidate

            index += 1

    # =========================================================
    # LÍMITES DEL TERRENO
    # =========================================================

    def is_position_inside_terrain(
        self,
        x: float,
        y: float,
    ) -> bool:
        """
        Indica si una coordenada XY está dentro del terreno.
        """

        half_width = self.width / 2.0
        half_length = self.length / 2.0

        return (
            -half_width <= x <= half_width
            and -half_length <= y <= half_length
        )

    # =========================================================
    # SERIALIZACIÓN
    # =========================================================

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte todo el proyecto en un diccionario.

        Este método será utilizado posteriormente para guardar
        proyectos y generar archivos SDF.
        """

        return {
            "project_id": self.project_id,
            "name": self.name,
            "width": self.width,
            "length": self.length,
            "creation_mode": self.creation_mode,
            "terrain_path": self.terrain_path,
            "objects": [
                world_object.to_dict()
                for world_object
                in self._objects.values()
            ],
        }
