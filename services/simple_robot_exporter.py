from pathlib import Path


class SimpleRobotExporter:
    """
    Genera el modelo Gazebo del robot diferencial simple
    utilizado para ejecutar la ruta de simulación.
    """

    @classmethod
    def export(
        cls,
        output_directory: str | Path,
    ) -> Path:
        model_directory = (
            Path(output_directory)
            / "simple_route_robot"
        )

        model_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        model_config_path = (
            model_directory
            / "model.config"
        )

        model_sdf_path = (
            model_directory
            / "model.sdf"
        )

        model_config_path.write_text(
            cls._generate_model_config(),
            encoding="utf-8",
        )

        model_sdf_path.write_text(
            cls._generate_model_sdf(),
            encoding="utf-8",
        )

        return model_sdf_path.resolve()

    @staticmethod
    def _generate_model_config() -> str:
        return """<?xml version="1.0"?>
<model>
  <name>Simple Route Robot</name>
  <version>1.0</version>
  <sdf version="1.10">model.sdf</sdf>
  <description>
    Robot diferencial simple para seguimiento automático de rutas.
  </description>
</model>
"""

    @staticmethod
    def _generate_model_sdf() -> str:
        return """<?xml version="1.0"?>
    <sdf version="1.10">

      <model name="simple_route_robot">

        <link name="base_link">
          <pose>0 0 0.30 0 0 0</pose>

          <inertial>
            <mass>15.0</mass>
            <inertia>
              <ixx>0.43</ixx>
              <iyy>1.30</iyy>
              <izz>1.63</izz>
            </inertia>
          </inertial>

          <collision name="base_collision">
            <geometry>
              <box>
                <size>1.00 0.55 0.20</size>
              </box>
            </geometry>
          </collision>

          <visual name="base_visual">
            <geometry>
              <box>
                <size>1.00 0.55 0.20</size>
              </box>
            </geometry>

            <material>
              <ambient>0.10 0.20 0.90 1</ambient>
              <diffuse>0.10 0.20 0.90 1</diffuse>
            </material>
          </visual>
        </link>


        <!-- RUEDA MOTRIZ IZQUIERDA -->

        <link name="left_wheel">
          <pose>0 0.32 0.15 0 0 0</pose>

          <inertial>
            <mass>1.0</mass>
            <inertia>
              <ixx>0.0062</ixx>
              <iyy>0.0113</iyy>
              <izz>0.0062</izz>
            </inertia>
          </inertial>

          <collision name="collision">
            <pose>0 0 0 1.570796 0 0</pose>

            <geometry>
              <cylinder>
                <radius>0.15</radius>
                <length>0.08</length>
              </cylinder>
            </geometry>

            <surface>
              <friction>
                <ode>
                  <mu>5.0</mu>
                  <mu2>5.0</mu2>
                </ode>
              </friction>
            </surface>
          </collision>

          <visual name="visual">
            <pose>0 0 0 1.570796 0 0</pose>

            <geometry>
              <cylinder>
                <radius>0.15</radius>
                <length>0.08</length>
              </cylinder>
            </geometry>

            <material>
              <ambient>0.05 0.05 0.05 1</ambient>
              <diffuse>0.05 0.05 0.05 1</diffuse>
            </material>
          </visual>
        </link>


        <!-- RUEDA MOTRIZ DERECHA -->

        <link name="right_wheel">
          <pose>0 -0.32 0.15 0 0 0</pose>

          <inertial>
            <mass>1.0</mass>
            <inertia>
              <ixx>0.0062</ixx>
              <iyy>0.0113</iyy>
              <izz>0.0062</izz>
            </inertia>
          </inertial>

          <collision name="collision">
            <pose>0 0 0 1.570796 0 0</pose>

            <geometry>
              <cylinder>
                <radius>0.15</radius>
                <length>0.08</length>
              </cylinder>
            </geometry>

            <surface>
              <friction>
                <ode>
                  <mu>5.0</mu>
                  <mu2>5.0</mu2>
                </ode>
              </friction>
            </surface>
          </collision>

          <visual name="visual">
            <pose>0 0 0 1.570796 0 0</pose>

            <geometry>
              <cylinder>
                <radius>0.15</radius>
                <length>0.08</length>
              </cylinder>
            </geometry>

            <material>
              <ambient>0.05 0.05 0.05 1</ambient>
              <diffuse>0.05 0.05 0.05 1</diffuse>
            </material>
          </visual>
        </link>


        <!-- CASTER DELANTERO -->

        <link name="front_caster">
          <pose>0.38 0 0.08 0 0 0</pose>

          <inertial>
            <mass>0.20</mass>
            <inertia>
              <ixx>0.0005</ixx>
              <iyy>0.0005</iyy>
              <izz>0.0005</izz>
            </inertia>
          </inertial>

          <collision name="collision">
            <geometry>
              <sphere>
                <radius>0.06</radius>
              </sphere>
            </geometry>

            <surface>
              <friction>
                <ode>
                  <mu>0.05</mu>
                  <mu2>0.05</mu2>
                </ode>
              </friction>
            </surface>
          </collision>

          <visual name="visual">
            <geometry>
              <sphere>
                <radius>0.08</radius>
              </sphere>
            </geometry>

            <material>
              <ambient>0.30 0.30 0.30 1</ambient>
              <diffuse>0.30 0.30 0.30 1</diffuse>
            </material>
          </visual>
        </link>


        <!-- CASTER TRASERO -->

        <link name="rear_caster">
          <pose>-0.38 0 0.08 0 0 0</pose>

          <inertial>
            <mass>0.20</mass>
            <inertia>
              <ixx>0.0005</ixx>
              <iyy>0.0005</iyy>
              <izz>0.0005</izz>
            </inertia>
          </inertial>

          <collision name="collision">
            <geometry>
              <sphere>
                <radius>0.08</radius>
              </sphere>
            </geometry>

            <surface>
              <friction>
                <ode>
                  <mu>0.05</mu>
                  <mu2>0.05</mu2>
                </ode>
              </friction>
            </surface>
          </collision>

          <visual name="visual">
            <geometry>
              <sphere>
                <radius>0.08</radius>
              </sphere>
            </geometry>

            <material>
              <ambient>0.30 0.30 0.30 1</ambient>
              <diffuse>0.30 0.30 0.30 1</diffuse>
            </material>
          </visual>
        </link>


        <!-- JOINTS DE LAS RUEDAS MOTRICES -->

        <joint name="left_wheel_joint" type="revolute">
          <parent>base_link</parent>
          <child>left_wheel</child>

          <axis>
            <xyz>0 1 0</xyz>
          </axis>
        </joint>

        <joint name="right_wheel_joint" type="revolute">
          <parent>base_link</parent>
          <child>right_wheel</child>

          <axis>
            <xyz>0 1 0</xyz>
          </axis>
        </joint>


        <!-- JOINTS LIBRES DE LOS CASTER -->

        <joint name="front_caster_joint" type="ball">
          <parent>base_link</parent>
          <child>front_caster</child>
        </joint>

        <joint name="rear_caster_joint" type="ball">
          <parent>base_link</parent>
          <child>rear_caster</child>
        </joint>


        <!-- CONTROL DIFERENCIAL -->

        <plugin
          filename="gz-sim-diff-drive-system"
          name="gz::sim::systems::DiffDrive">

          <left_joint>left_wheel_joint</left_joint>
          <right_joint>right_wheel_joint</right_joint>

          <wheel_separation>0.64</wheel_separation>
          <wheel_radius>0.15</wheel_radius>

          <odom_publish_frequency>20</odom_publish_frequency>

          <topic>/simple_route_robot/cmd_vel</topic>
          <odom_topic>/simple_route_robot/odometry</odom_topic>

        </plugin>

      </model>

    </sdf>
    """
