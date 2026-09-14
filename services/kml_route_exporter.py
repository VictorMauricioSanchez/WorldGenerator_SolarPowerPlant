from pathlib import Path
import xml.etree.ElementTree as ET

from rasterio.warp import transform

from services.geotiff_reader import GeoTiffReader


class KmlRouteExporter:
    KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
    GX_NAMESPACE = "http://www.google.com/kml/ext/2.2"

    ROUTE_FIELDS = (
        ("string", "headingStrategy", "Mower heading strategy"),
        ("double", "headingAutoLength", "Length for auto heading"),
        ("double", "headingFixedAngle", "Fixed heading angle"),
        ("double", "headingFixedTolerance", "Heading tolerance"),
        ("double", "speedLimit", "Speed limit"),
        ("string", "mowingHeightType", "Mowing height Type"),
        ("double", "mowingHeightValue", "Mowing height Value"),
        ("string", "mowingHeightChangeSlowdown", "Mowing height Change slowdown"),
        ("boolean", "enableMowing", "Enable mowing"),
        ("string", "enableMowingChangeSlowdown", "Enable mowing Change slowdown"),
        ("boolean", "expectNoGps", "Expect no GPS coverage"),
        ("boolean", "allowStaticFix", "Allow static fix"),
        ("boolean", "pauseBefore", "Pause before next segment"),
        ("string", "pauseBeforeMessage", "Message to display on RC if entering pauseBefore"),
        ("string", "sideMowingDeck", "Enable mowing Change slowdown"),
        ("string", "sideMowingDeckChangeSlowdown", "Side mowing deck Change slowdown"),
        ("double", "a1", "Analog value 1"),
        ("double", "a2", "Analog value 2"),
        ("boolean", "d1", "Digital value 1"),
        ("boolean", "d2", "Digital value 2"),
    )

    @classmethod
    def export(
        cls,
        route_points: list[tuple[float, float, float]],
        terrain_path: str | Path,
        output_path: str | Path,
        route_name: str,
        heading_strategy: str = "fixed",
        heading_fixed_angle: float = 12.4,
        heading_fixed_tolerance: float = 5.2,
    ) -> Path:
        if len(route_points) < 2:
            raise ValueError(
                "La ruta debe contener al menos dos puntos."
            )

        terrain_info = GeoTiffReader.read_info(
            terrain_path
        )

        if not terrain_info.crs or terrain_info.crs == "Desconocido":
            raise ValueError(
                "El GeoTIFF debe tener un sistema de coordenadas definido."
            )

        coordinates = cls._local_route_to_wgs84(
            route_points=route_points,
            terrain_path=terrain_path,
        )

        destination = Path(output_path)

        if destination.suffix.lower() != ".kml":
            destination = destination.with_suffix(".kml")

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        root = cls._build_kml(
            coordinates=coordinates,
            route_name=route_name,
            heading_strategy=heading_strategy,
            heading_fixed_angle=heading_fixed_angle,
            heading_fixed_tolerance=heading_fixed_tolerance,
        )

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        tree.write(
            destination,
            encoding="utf-8",
            xml_declaration=True,
        )

        return destination.resolve()

    @classmethod
    def _local_route_to_wgs84(
        cls,
        route_points: list[tuple[float, float, float]],
        terrain_path: str | Path,
    ) -> list[tuple[float, float]]:
        terrain_info = GeoTiffReader.read_info(
            terrain_path
        )

        center_easting = (
            terrain_info.min_x
            + terrain_info.max_x
        ) / 2.0

        center_northing = (
            terrain_info.min_y
            + terrain_info.max_y
        ) / 2.0

        eastings = [
            center_easting + x
            for x, _, _ in route_points
        ]

        northings = [
            center_northing + y
            for _, y, _ in route_points
        ]

        longitudes, latitudes = transform(
            terrain_info.crs,
            "EPSG:4326",
            eastings,
            northings,
        )

        return list(
            zip(
                longitudes,
                latitudes,
            )
        )

    @classmethod
    def _build_kml(
        cls,
        coordinates: list[tuple[float, float]],
        route_name: str,
        heading_strategy: str,
        heading_fixed_angle: float,
        heading_fixed_tolerance: float,
    ) -> ET.Element:
        ET.register_namespace(
            "",
            cls.KML_NAMESPACE,
        )

        ET.register_namespace(
            "gx",
            cls.GX_NAMESPACE,
        )

        root = ET.Element(
            cls._tag("kml"),
            {
                "xmlns:gx": cls.GX_NAMESPACE,
            },
        )

        document = ET.SubElement(
            root,
            cls._tag("Document"),
        )

        ET.SubElement(
            document,
            cls._tag("name"),
        ).text = route_name

        ET.SubElement(
            document,
            cls._tag("open"),
        ).text = "1"

        cls._add_route_style(
            document
        )

        cls._add_route_schema(
            document
        )

        cls._add_route_placemark(
            document=document,
            coordinates=coordinates,
            heading_strategy=heading_strategy,
            heading_fixed_angle=heading_fixed_angle,
            heading_fixed_tolerance=heading_fixed_tolerance,
        )

        return root

    @classmethod
    def _add_route_style(
        cls,
        document: ET.Element,
    ) -> None:
        style = ET.SubElement(
            document,
            cls._tag("Style"),
            {
                "id": "mowingRoute",
            },
        )

        line_style = ET.SubElement(
            style,
            cls._tag("LineStyle"),
        )

        ET.SubElement(
            line_style,
            cls._tag("color"),
        ).text = "FF00FFFF"

        ET.SubElement(
            line_style,
            cls._tag("width"),
        ).text = "02"

    @classmethod
    def _add_route_schema(
        cls,
        document: ET.Element,
    ) -> None:
        schema = ET.SubElement(
            document,
            cls._tag("Schema"),
            {
                "name": "RouteSettings",
                "id": "RouteSettings",
            },
        )

        for field_type, field_name, display_name in cls.ROUTE_FIELDS:
            simple_field = ET.SubElement(
                schema,
                cls._tag("SimpleField"),
                {
                    "type": field_type,
                    "name": field_name,
                },
            )

            ET.SubElement(
                simple_field,
                cls._tag("displayName"),
            ).text = display_name

    @classmethod
    def _add_route_placemark(
        cls,
        document: ET.Element,
        coordinates: list[tuple[float, float]],
        heading_strategy: str,
        heading_fixed_angle: float,
        heading_fixed_tolerance: float,
    ) -> None:
        placemark = ET.SubElement(
            document,
            cls._tag("Placemark"),
        )

        ET.SubElement(
            placemark,
            cls._tag("styleUrl"),
        ).text = "#mowingRoute"

        ET.SubElement(
            placemark,
            cls._tag("name"),
        ).text = "01 "

        extended_data = ET.SubElement(
            placemark,
            cls._tag("ExtendedData"),
        )

        schema_data = ET.SubElement(
            extended_data,
            cls._tag("SchemaData"),
            {
                "schemaUrl": "#RouteSettings",
            },
        )

        cls._add_simple_data(
            schema_data,
            "headingStrategy",
            heading_strategy,
        )

        cls._add_simple_data(
            schema_data,
            "headingFixedAngle",
            f"{heading_fixed_angle:.1f}",
        )

        cls._add_simple_data(
            schema_data,
            "headingFixedTolerance",
            f"{heading_fixed_tolerance:.1f}",
        )

        line_string = ET.SubElement(
            placemark,
            cls._tag("LineString"),
        )

        ET.SubElement(
            line_string,
            cls._tag("tessellate"),
        ).text = "1"

        coordinates_element = ET.SubElement(
            line_string,
            cls._tag("coordinates"),
        )

        coordinates_element.text = "\n" + "\n".join(
            f"{longitude:.9f},{latitude:.9f}"
            for longitude, latitude in coordinates
        ) + "\n"

    @classmethod
    def _add_simple_data(
        cls,
        schema_data: ET.Element,
        name: str,
        value: str,
    ) -> None:
        ET.SubElement(
            schema_data,
            cls._tag("SimpleData"),
            {
                "name": name,
            },
        ).text = value

    @classmethod
    def _tag(
        cls,
        name: str,
    ) -> str:
        return (
            f"{{{cls.KML_NAMESPACE}}}"
            f"{name}"
        )
