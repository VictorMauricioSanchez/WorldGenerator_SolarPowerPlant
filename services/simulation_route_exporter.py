import csv
import math
from pathlib import Path


class SimulationRouteExporter:

    @classmethod
    def export(
        cls,
        dockout_points: list[tuple[float, float, float]],
        work_route_points: list[tuple[float, float, float]],
        output_path: str | Path,
    ) -> Path:
        if len(dockout_points) < 2:
            raise ValueError(
                "La ruta Dock Out debe contener al menos dos puntos."
            )

        if len(work_route_points) < 2:
            raise ValueError(
                "La ruta de trabajo debe contener al menos dos puntos."
            )

        home_x, home_y, _ = dockout_points[0]

        first_target_x, first_target_y, _ = dockout_points[1]

        yaw_origin = math.atan2(
            first_target_y - home_y,
            first_target_x - home_x,
        )

        full_route = list(dockout_points)

        last_dockout = dockout_points[-1]
        first_work = work_route_points[0]

        distance = math.hypot(
            first_work[0] - last_dockout[0],
            first_work[1] - last_dockout[1],
        )

        if distance < 1e-6:
            full_route.extend(work_route_points[1:])
        else:
            full_route.extend(work_route_points)

        local_route: list[tuple[float, float]] = []

        cos_yaw = math.cos(yaw_origin)
        sin_yaw = math.sin(yaw_origin)

        for x, y, _ in full_route:
            delta_x = x - home_x
            delta_y = y - home_y

            local_x = delta_x * cos_yaw + delta_y * sin_yaw
            local_y = -delta_x * sin_yaw + delta_y * cos_yaw

            local_route.append(
                (
                    local_x,
                    local_y,
                )
            )

        destination = Path(output_path)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with destination.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as csv_file:
            writer = csv.writer(csv_file)

            writer.writerow(
                (
                    "waypoint",
                    "x",
                    "y",
                )
            )

            for waypoint_index, (x, y) in enumerate(local_route):
                writer.writerow(
                    (
                        waypoint_index,
                        f"{x:.6f}",
                        f"{y:.6f}",
                    )
                )

        return destination.resolve()

