import csv
import math
from pathlib import Path

import rclpy

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node


class RouteFollower(Node):

    MAX_LINEAR_SPEED = 1.0
    MAX_ANGULAR_SPEED = 0.8

    KP_ANGULAR = 1.0

    WAYPOINT_TOLERANCE = 0.50
    TURN_IN_PLACE_ENTER = math.radians(45.0)
    TURN_IN_PLACE_EXIT = math.radians(15.0)
    LOOKAHEAD_DISTANCE = 0.00

    CONTROL_PERIOD = 0.10

    def __init__(self) -> None:
        super().__init__("route_follower")

        project_directory = Path(__file__).resolve().parent.parent

        route_path = (
            project_directory
            / "generated_worlds"
            / "routes"
            / "simulation_route.csv"
        )

        self.route = self._load_route(route_path)

        if len(self.route) < 2:
            raise ValueError(
                "La ruta debe contener al menos dos waypoints."
            )

        self.current_waypoint = 1

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0

        self.odometry_received = False
        self.route_finished = False

        self.turning_in_place = False

        self.cmd_vel_publisher = self.create_publisher(
            Twist,
            "/simple_route_robot/cmd_vel",
            10,
        )

        self.odometry_subscription = self.create_subscription(
            Odometry,
            "/simple_route_robot/odometry",
            self._odometry_callback,
            10,
        )

        self.control_timer = self.create_timer(
            self.CONTROL_PERIOD,
            self._control,
        )

        self.get_logger().info(
            f"Ruta cargada: {len(self.route)} waypoints."
        )

        self.get_logger().info(
            "Esperando odometría del robot..."
        )

    @staticmethod
    def _load_route(
        route_path: Path,
    ) -> list[tuple[float, float]]:
        if not route_path.exists():
            raise FileNotFoundError(
                f"No existe la ruta: {route_path}"
            )

        route: list[tuple[float, float]] = []

        with route_path.open(
            "r",
            encoding="utf-8",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                route.append(
                    (
                        float(row["x"]),
                        float(row["y"]),
                    )
                )

        return route

    def _odometry_callback(
        self,
        message: Odometry,
    ) -> None:
        self.robot_x = message.pose.pose.position.x
        self.robot_y = message.pose.pose.position.y

        orientation = message.pose.pose.orientation

        self.robot_yaw = self._quaternion_to_yaw(
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w,
        )

        if not self.odometry_received:
            self.odometry_received = True

            self.get_logger().info(
                "Odometría recibida. Iniciando seguimiento."
            )

    def _control(self) -> None:
        if not self.odometry_received:
            return

        if self.route_finished:
            return

        self._advance_reached_waypoints()

        if self.current_waypoint >= len(self.route):
            self._finish_route()
            return

        target_index = self._find_lookahead_waypoint()

        target_x, target_y = self.route[
            target_index
        ]

        delta_x = target_x - self.robot_x
        delta_y = target_y - self.robot_y

        distance = math.hypot(
            delta_x,
            delta_y,
        )

        desired_heading = math.atan2(
            delta_y,
            delta_x,
        )

        heading_error = self._wrap_angle(
            desired_heading - self.robot_yaw
        )

        if self.turning_in_place:
            if abs(heading_error) <= self.TURN_IN_PLACE_EXIT:
                self.turning_in_place = False
        else:
            if abs(heading_error) >= self.TURN_IN_PLACE_ENTER:
                self.turning_in_place = True

        angular_velocity = self.KP_ANGULAR * heading_error

        angular_velocity = max(
            -self.MAX_ANGULAR_SPEED,
            min(
                self.MAX_ANGULAR_SPEED,
                angular_velocity,
            ),
        )

        if self.turning_in_place:
            linear_velocity = 0.0
        else:
            heading_factor = max(
                0.80,
                math.cos(heading_error),
            )

            linear_velocity = (
                self.MAX_LINEAR_SPEED
                * heading_factor
            )
        command = Twist()

        command.linear.x = linear_velocity
        command.angular.z = angular_velocity

        self.cmd_vel_publisher.publish(
            command
        )

    def _find_lookahead_waypoint(self) -> int:
        target_index = self.current_waypoint

        for waypoint_index in range(
            self.current_waypoint,
            len(self.route),
        ):
            target_x, target_y = self.route[
                waypoint_index
            ]

            distance = math.hypot(
                target_x - self.robot_x,
                target_y - self.robot_y,
            )

            target_index = waypoint_index

            if distance >= self.LOOKAHEAD_DISTANCE:
                break

        return target_index

    def _advance_reached_waypoints(self) -> None:
        while self.current_waypoint < len(self.route):
            target_x, target_y = self.route[
                self.current_waypoint
            ]

            distance = math.hypot(
                target_x - self.robot_x,
                target_y - self.robot_y,
            )

            if distance > self.WAYPOINT_TOLERANCE:
                break

            self.current_waypoint += 1

            if self.current_waypoint % 100 == 0:
                self.get_logger().info(
                    f"Waypoint {self.current_waypoint}/{len(self.route) - 1}"
                )

    def _finish_route(self) -> None:
        command = Twist()

        command.linear.x = 0.0
        command.angular.z = 0.0

        self.cmd_vel_publisher.publish(
            command
        )

        self.route_finished = True

        self.get_logger().info(
            "Ruta completada."
        )

    @staticmethod
    def _quaternion_to_yaw(
        x: float,
        y: float,
        z: float,
        w: float,
    ) -> float:
        sin_yaw = 2.0 * (
            w * z
            + x * y
        )

        cos_yaw = 1.0 - 2.0 * (
            y * y
            + z * z
        )

        return math.atan2(
            sin_yaw,
            cos_yaw,
        )

    @staticmethod
    def _wrap_angle(
        angle: float,
    ) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi

        while angle < -math.pi:
            angle += 2.0 * math.pi

        return angle


def main() -> None:
    rclpy.init()

    node = RouteFollower()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        stop_command = Twist()

        node.cmd_vel_publisher.publish(
            stop_command
        )

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()

