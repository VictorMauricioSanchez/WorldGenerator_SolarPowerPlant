import numpy as np


class WorkRouteGenerator:
    """
    Generador geométrico de rutas de trabajo en zigzag.
    """

    @staticmethod
    def validate_directions(x_direction: np.ndarray, y_direction: np.ndarray) -> None:
        if x_direction.shape != (2,) or y_direction.shape != (2,):
            raise ValueError("Las direcciones X e Y deben ser vectores bidimensionales.")

        x_norm = np.linalg.norm(x_direction)
        y_norm = np.linalg.norm(y_direction)

        if x_norm <= 0.0 or y_norm <= 0.0:
            raise ValueError("Las direcciones X e Y no pueden tener magnitud cero.")

        x_unit = x_direction / x_norm
        y_unit = y_direction / y_norm

        cross = x_unit[0] * y_unit[1] - x_unit[1] * y_unit[0]

        if abs(cross) < 0.05:
            raise ValueError(
                "Las direcciones X e Y son demasiado paralelas. "
                "Debe existir una separación angular suficiente entre ambas."
            )

    @staticmethod
    def calculate_spacing(work_width: float, overlap: float) -> float:
        if work_width < 1.0:
            raise ValueError("El ancho de desbroce debe ser como mínimo de 1.0 m.")

        if overlap < 0.0 or overlap > 0.20:
            raise ValueError("El solapamiento debe estar entre 0.0 y 0.20 m.")

        spacing = work_width - overlap

        if spacing <= 0.0:
            raise ValueError("La separación entre pasadas debe ser mayor que cero.")

        return spacing

    @staticmethod
    def calculate_post_activation_radius(
        post_groups: list[list[tuple[float, float, float]]],
        minimum_radius: float = 1.0,
    ) -> float:
        group_centers = []
        longitudinal_distances = []

        for post_group in post_groups:
            if not post_group:
                continue

            points = np.array([(x, y) for x, y, _ in post_group], dtype=float)

            center = np.mean(points, axis=0)
            group_centers.append(center)

            if len(points) >= 2:
                for index in range(len(points) - 1):
                    distance = np.linalg.norm(points[index + 1] - points[index])

                    if distance > 0.01:
                        longitudinal_distances.append(distance)

        if len(group_centers) < 2:
            return minimum_radius

        centers = np.array(group_centers, dtype=float)

        differences = centers[:, None, :] - centers[None, :, :]
        distances = np.linalg.norm(differences, axis=2)

        np.fill_diagonal(distances, np.inf)

        nearest_distances = np.min(distances, axis=1)

        row_spacing = float(np.median(nearest_distances))

        if longitudinal_distances:
            post_spacing = float(np.median(longitudinal_distances))
        else:
            post_spacing = row_spacing

        activation_radius = 0.5 * np.hypot(
            row_spacing,
            post_spacing,
        )

        return max(minimum_radius, activation_radius)

    @staticmethod
    def generate_parallel_segments(
        perimeter_points: list[tuple[float, float, float]],
        x_direction: np.ndarray,
        y_direction: np.ndarray,
        spacing: float,
    ) -> list[list[tuple[float, float]]]:
        if len(perimeter_points) < 3:
            raise ValueError("El perímetro debe contener al menos 3 puntos.")

        WorkRouteGenerator.validate_directions(x_direction, y_direction)

        if spacing <= 0.0:
            raise ValueError("La separación entre pasadas debe ser mayor que cero.")

        x_unit = x_direction / np.linalg.norm(x_direction)
        y_unit = y_direction / np.linalg.norm(y_direction)

        normal = np.array([-x_unit[1], x_unit[0]], dtype=float)

        if np.dot(normal, y_unit) < 0.0:
            normal = -normal

        polygon = np.array([(x, y) for x, y, _ in perimeter_points], dtype=float)

        longitudinal = polygon @ x_unit
        transverse = polygon @ normal

        minimum_transverse = float(np.min(transverse))
        maximum_transverse = float(np.max(transverse))

        offsets = np.arange(
            minimum_transverse,
            maximum_transverse + spacing * 0.5,
            spacing,
        )

        scan_segments: list[list[tuple[float, float]]] = []

        for offset in offsets:
            intersections: list[float] = []

            for index in range(len(polygon)):
                point_a = polygon[index]
                point_b = polygon[(index + 1) % len(polygon)]

                transverse_a = float(np.dot(point_a, normal))
                transverse_b = float(np.dot(point_b, normal))

                crosses = (
                    transverse_a <= offset < transverse_b
                    or transverse_b <= offset < transverse_a
                )

                if not crosses:
                    continue

                interpolation = (offset - transverse_a) / (transverse_b - transverse_a)

                intersection = point_a + interpolation * (point_b - point_a)
                longitudinal_value = float(np.dot(intersection, x_unit))

                intersections.append(longitudinal_value)

            intersections.sort()

            if len(intersections) < 2:
                continue

            line_segments: list[tuple[float, float]] = []

            for index in range(0, len(intersections) - 1, 2):
                start_longitudinal = intersections[index]
                end_longitudinal = intersections[index + 1]

                start_point = x_unit * start_longitudinal + normal * offset
                end_point = x_unit * end_longitudinal + normal * offset

                line_segments.append(
                    (
                        float(start_point[0]),
                        float(start_point[1]),
                    )
                )

                line_segments.append(
                    (
                        float(end_point[0]),
                        float(end_point[1]),
                    )
                )

            if line_segments:
                scan_segments.append(line_segments)

        if not scan_segments:
            raise ValueError("No fue posible generar pasadas dentro del perímetro.")

        return scan_segments

    @staticmethod
    def filter_segments_by_posts(
        scan_segments: list[list[tuple[float, float]]],
        post_points: list[tuple[float, float, float]],
        activation_radius: float,
    ) -> list[list[tuple[float, float]]]:
        if not post_points:
            raise ValueError("No existen postes cargados para definir la zona de trabajo.")

        if activation_radius <= 0.0:
            raise ValueError("El radio de activación debe ser mayor que cero.")

        posts = np.array([(x, y) for x, y, _ in post_points], dtype=float)

        filtered_segments: list[list[tuple[float, float]]] = []

        for scan_line in scan_segments:
            filtered_line: list[tuple[float, float]] = []

            for index in range(0, len(scan_line) - 1, 2):
                start = np.array(scan_line[index], dtype=float)
                end = np.array(scan_line[index + 1], dtype=float)

                segment_vector = end - start
                segment_length = np.linalg.norm(segment_vector)

                if segment_length <= 0.0:
                    continue

                segment_unit = segment_vector / segment_length

                relative_posts = posts - start
                projections = relative_posts @ segment_unit

                clamped_projections = np.clip(projections, 0.0, segment_length)
                closest_points = start + clamped_projections[:, None] * segment_unit

                distances = np.linalg.norm(posts - closest_points, axis=1)
                relevant_posts = distances <= activation_radius

                if not np.any(relevant_posts):
                    continue

                relevant_projections = projections[relevant_posts]

                start_distance = max(
                    0.0,
                    float(np.min(relevant_projections)) - activation_radius,
                )

                end_distance = min(
                    segment_length,
                    float(np.max(relevant_projections)) + activation_radius,
                )

                if end_distance <= start_distance:
                    continue

                filtered_start = start + segment_unit * start_distance
                filtered_end = start + segment_unit * end_distance

                filtered_line.append(
                    (float(filtered_start[0]), float(filtered_start[1]))
                )

                filtered_line.append(
                    (float(filtered_end[0]), float(filtered_end[1]))
                )

            if filtered_line:
                filtered_segments.append(filtered_line)

        if not filtered_segments:
            raise ValueError("No existen zonas de desbroce próximas a los postes.")

        return filtered_segments

    @staticmethod
    def build_zigzag_route(
        scan_segments: list[list[tuple[float, float]]],
        x_direction: np.ndarray,
        start_point: tuple[float, float, float],
    ) -> list[tuple[float, float]]:
        if not scan_segments:
            raise ValueError("No existen pasadas para generar la ruta.")

        x_unit = x_direction / np.linalg.norm(x_direction)

        route: list[tuple[float, float]] = [
            (
                float(start_point[0]),
                float(start_point[1]),
            )
        ]

        for line_index, scan_line in enumerate(scan_segments):
            if len(scan_line) < 2:
                continue

            segment_pairs = []

            for index in range(0, len(scan_line) - 1, 2):
                point_a = scan_line[index]
                point_b = scan_line[index + 1]

                projection_a = np.dot(np.array(point_a), x_unit)
                projection_b = np.dot(np.array(point_b), x_unit)

                if projection_a <= projection_b:
                    segment_pairs.append((point_a, point_b))
                else:
                    segment_pairs.append((point_b, point_a))

            segment_pairs.sort(
                key=lambda pair: np.dot(np.array(pair[0]), x_unit)
            )

            if line_index % 2 == 0:
                for start, end in segment_pairs:
                    route.append(start)
                    route.append(end)

            else:
                for start, end in reversed(segment_pairs):
                    route.append(end)
                    route.append(start)

        if len(route) < 3:
            raise ValueError("No fue posible construir una ruta de trabajo válida.")

        return route

    @staticmethod
    def find_post_conflicts(
        route_points: list[tuple[float, float]],
        post_points: list[tuple[float, float, float]],
        safety_radius: float = 1.0,
    ) -> list[tuple[int, int, float]]:
        if len(route_points) < 2:
            return []

        if safety_radius <= 0.0:
            raise ValueError("El radio de seguridad debe ser mayor que cero.")

        posts = np.array([(x, y) for x, y, _ in post_points], dtype=float)

        conflicts: list[tuple[int, int, float]] = []

        for segment_index in range(len(route_points) - 1):
            start = np.array(route_points[segment_index], dtype=float)
            end = np.array(route_points[segment_index + 1], dtype=float)

            segment = end - start
            segment_length_squared = float(np.dot(segment, segment))

            if segment_length_squared <= 0.0:
                continue

            relative_posts = posts - start
            projection = (relative_posts @ segment) / segment_length_squared
            projection = np.clip(projection, 0.0, 1.0)

            closest_points = start + projection[:, None] * segment
            distances = np.linalg.norm(posts - closest_points, axis=1)

            conflicting_indices = np.where(distances < safety_radius)[0]

            for post_index in conflicting_indices:
                conflicts.append(
                    (
                        segment_index,
                        int(post_index),
                        float(distances[post_index]),
                    )
                )

        return conflicts


    @staticmethod
    def point_inside_perimeter(
        point: tuple[float, float],
        perimeter_points: list[tuple[float, float, float]],
    ) -> bool:
        if len(perimeter_points) < 3:
            return False

        x, y = point
        inside = False

        polygon = [(px, py) for px, py, _ in perimeter_points]
        previous_index = len(polygon) - 1

        for current_index in range(len(polygon)):
            x_current, y_current = polygon[current_index]
            x_previous, y_previous = polygon[previous_index]

            intersects = (
                (y_current > y) != (y_previous > y)
                and x
                < (
                    (x_previous - x_current)
                    * (y - y_current)
                    / (y_previous - y_current)
                    + x_current
                )
            )

            if intersects:
                inside = not inside

            previous_index = current_index

        return inside


    @staticmethod
    def create_post_detour(
        segment_start: tuple[float, float],
        segment_end: tuple[float, float],
        post_point: tuple[float, float, float],
        perimeter_points: list[tuple[float, float, float]],
        safety_radius: float = 1.0,
        clearance_margin: float = 0.10,
        angular_step_degrees: float = 10.0,
    ) -> list[tuple[float, float]]:
        start = np.array(segment_start, dtype=float)
        end = np.array(segment_end, dtype=float)
        post = np.array(post_point[:2], dtype=float)

        segment = end - start
        segment_length = np.linalg.norm(segment)

        if segment_length <= 0.0:
            raise ValueError("El segmento de ruta tiene longitud cero.")

        path_radius = safety_radius + clearance_margin
        segment_unit = segment / segment_length

        relative_post = post - start
        projection = float(np.dot(relative_post, segment_unit))
        projection = np.clip(projection, 0.0, segment_length)

        closest_point = start + projection * segment_unit
        distance_to_segment = float(np.linalg.norm(post - closest_point))

        if distance_to_segment >= safety_radius:
            return []

        if distance_to_segment >= path_radius:
            return []

        half_chord = np.sqrt(path_radius**2 - distance_to_segment**2)

        entry_distance = projection - half_chord
        exit_distance = projection + half_chord

        if entry_distance < 0.0 or exit_distance > segment_length:
            raise ValueError(
                "El poste está demasiado cerca del extremo del segmento para generar el desvío."
            )

        entry_point = start + entry_distance * segment_unit
        exit_point = start + exit_distance * segment_unit

        entry_angle = np.arctan2(
            entry_point[1] - post[1],
            entry_point[0] - post[0],
        )

        exit_angle = np.arctan2(
            exit_point[1] - post[1],
            exit_point[0] - post[0],
        )

        step_radians = np.radians(angular_step_degrees)

        counterclockwise_span = (exit_angle - entry_angle) % (2.0 * np.pi)
        clockwise_span = (entry_angle - exit_angle) % (2.0 * np.pi)

        candidates: list[list[tuple[float, float]]] = []

        for direction, span in ((1.0, counterclockwise_span), (-1.0, clockwise_span)):
            step_count = max(2, int(np.ceil(span / step_radians)))

            angles = entry_angle + direction * np.linspace(0.0, span, step_count + 1)

            candidate = []

            for angle in angles:
                point = post + path_radius * np.array(
                    [np.cos(angle), np.sin(angle)],
                    dtype=float,
                )

                point_tuple = (float(point[0]), float(point[1]))

                if not WorkRouteGenerator.point_inside_perimeter(
                    point_tuple,
                    perimeter_points,
                ):
                    candidate = []
                    break

                candidate.append(point_tuple)

            if candidate:
                candidates.append(candidate)

        if not candidates:
            raise ValueError(
                "No existe un desvío válido alrededor del poste dentro del perímetro."
            )

        candidates.sort(key=len)

        return candidates[0]


    @staticmethod
    def apply_post_detours(
        route_points: list[tuple[float, float]],
        post_points: list[tuple[float, float, float]],
        perimeter_points: list[tuple[float, float, float]],
        safety_radius: float = 1.0,
    ) -> list[tuple[float, float]]:
        if len(route_points) < 2:
            return list(route_points)

        conflicts = WorkRouteGenerator.find_post_conflicts(
            route_points,
            post_points,
            safety_radius,
        )

        if not conflicts:
            return list(route_points)

        conflicts_by_segment: dict[int, list[int]] = {}

        for segment_index, post_index, _ in conflicts:
            conflicts_by_segment.setdefault(segment_index, []).append(post_index)

        posts_xy = np.array(
            [(x, y) for x, y, _ in post_points],
            dtype=float,
        )

        adjusted_route: list[tuple[float, float]] = [
            route_points[0]
        ]

        for segment_index in range(len(route_points) - 1):
            start = np.array(route_points[segment_index], dtype=float)
            end = np.array(route_points[segment_index + 1], dtype=float)

            post_indices = conflicts_by_segment.get(segment_index, [])

            if not post_indices:
                adjusted_route.append((float(end[0]), float(end[1])))
                continue

            segment = end - start
            segment_length = np.linalg.norm(segment)

            if segment_length <= 0.0:
                continue

            segment_unit = segment / segment_length

            post_indices = sorted(
                set(post_indices),
                key=lambda index: float(
                    np.dot(posts_xy[index] - start, segment_unit)
                ),
            )

            for post_index in post_indices:
                try:
                    detour = WorkRouteGenerator.create_post_detour(
                        segment_start=(float(start[0]), float(start[1])),
                        segment_end=(float(end[0]), float(end[1])),
                        post_point=post_points[post_index],
                        perimeter_points=perimeter_points,
                        safety_radius=safety_radius,
                    )

                except ValueError:
                    continue

                if not detour:
                    continue

                for point in detour:
                    previous = np.array(adjusted_route[-1], dtype=float)
                    current = np.array(point, dtype=float)

                    if np.linalg.norm(current - previous) > 1e-6:
                        adjusted_route.append(point)

            previous = np.array(adjusted_route[-1], dtype=float)

            if np.linalg.norm(end - previous) > 1e-6:
                adjusted_route.append((float(end[0]), float(end[1])))

        return adjusted_route
