# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`articubot_one` is a ROS 2 differential-drive robot package originally based on the Articulated Robotics tutorial template. The repo targets **ROS 2 Jazzy Jalisco** with **Gazebo (new `gz-sim`, not Gazebo Classic)** via `ros_gz_sim` / `ros_gz_bridge`. The package has no compiled code — it ships only xacro robot descriptions, launch files, YAML configs, world files, and saved maps.

## Repository layout quirk

This is a **single-package workspace**: the package root *is* the workspace root. `build/` and `install/` sit directly next to `package.xml`, with no `src/` directory. Run `colcon build` from this same directory, not from a parent. `install/articubot_one/COLCON_IGNORE` exists to prevent colcon from recursing into the install tree.

## Commands

All commands run from the repo root (which is both the workspace root and the package root).

```bash
# Build (only needed after changing launch/config/description/worlds — nothing compiles)
colcon build --symlink-install

# Source the overlay (do this in every new shell before running launches)
source install/setup.bash

# Simulation: Gazebo + robot + bridges + twist_mux + joystick
ros2 launch articubot_one launch_sim.launch.py
ros2 launch articubot_one launch_sim.launch.py world:=./worlds/obstacles.world

# Real robot: rsp + ros2_control + twist_mux (diffdrive_arduino on /dev/ttyUSB0)
ros2 launch articubot_one launch_robot.launch.py

# SLAM (slam_toolbox, online async) — run alongside a sim or real robot launch
ros2 launch articubot_one online_async_launch.py

# Nav2 navigation + localization on an existing map
ros2 launch articubot_one localization_launch.py map:=./maps/my_map_save.yaml
ros2 launch articubot_one navigation_launch.py
```

There are no tests and no linters wired up beyond the stock `ament_lint_auto` in `CMakeLists.txt` (only active under `BUILD_TESTING`).

## Architecture

### Robot description (`description/`, xacro)

- `robot.urdf.xacro` is the top-level include hub. It pulls in `robot_core.xacro` (chassis, two drive wheels, caster), `gazebo_control.xacro`, `lidar.xacro`, `rgb_camera.xacro`, `depth_camera.xacro`.
- **`ros2_control.xacro` is intentionally NOT included** (the include line is commented out). In simulation, differential drive is handled by the native `gz-sim-diff-drive-system` plugin declared in `gazebo_control.xacro` — *not* by ros2_control. On the real robot, `launch_robot.launch.py` loads ros2_control with `diffdrive_arduino/DiffDriveArduinoHardware` talking to an Arduino on `/dev/ttyUSB0` at 57600 baud.
- Sensors use Gazebo Jazzy sensor syntax with explicit `<gz_frame_id>` tags (that's the Jazzy-compatible way to bind sensor output to a TF frame).

### Sim launch flow (`launch_sim.launch.py`)

1. `rsp.launch.py` — `robot_state_publisher` from processed xacro.
2. `joystick.launch.py` — `joy_node` + `teleop_twist_joy` + `twist_stamper`, publishing to `/cmd_vel_joy`.
3. `twist_mux` — merges `/cmd_vel` (nav) and `/cmd_vel_joy` (joystick, higher priority) → `/diff_cont/cmd_vel_unstamped`.
4. `ros_gz_sim` launches Gazebo with the chosen world; `ros_gz_sim create` spawns the robot from `/robot_description`.
5. Three bridges wire Gazebo ↔ ROS:
   - `ros_gz_bridge` (generic, config in `config/gz_bridge.yaml`): `clock`, `scan`, `odom`, `tf`, `joint_states`, `cmd_vel`, camera info.
   - `ros_gz_image` bridge: `/rgb_camera/image_raw`.
   - Second `ros_gz_bridge` instance for the depth camera point cloud (`/depth_camera/depth/points`).

> ⚠️ **Latent inconsistency**: `launch_sim.launch.py` still spawns `diff_cont` and `joint_broad` via the `controller_manager`'s `spawner`, but since `ros2_control.xacro` is not included, there is no `controller_manager` running in simulation. Those spawner nodes will fail / be no-ops. The actual diff-drive behaviour comes from the gz plugin in `gazebo_control.xacro`, and wheel commands flow through the bridge-remapped `/diff_cont/cmd_vel_unstamped` → gz `cmd_vel`.

### Real-robot launch flow (`launch_robot.launch.py`)

1. `rsp.launch.py` with `use_ros2_control:=true`.
2. `twist_mux` (same remap as sim).
3. `controller_manager` (`ros2_control_node`) loaded with `config/my_controllers.yaml` — **delayed by 3 s** via `TimerAction` because `robot_description` is fetched from the running `/robot_state_publisher` parameter (`ros2 param get --hide-type /robot_state_publisher robot_description`), which must be up first.
4. `diff_cont` and `joint_broad` spawners — both gated on `OnProcessStart(controller_manager)` so they only fire once the controller manager process is alive.

### Navigation / SLAM

- `online_async_launch.py` starts `slam_toolbox` async with `config/mapper_params_online_async.yaml`. Note the default mode in that YAML is `localization` (operating on an existing serialized map), not `mapping` — change `mode:` to `mapping` if you want to build a new map.
- `navigation_launch.py` and `localization_launch.py` are the stock Nav2 bringup launches (Apache-2.0 header from Intel), parameterised via `config/nav2_params.yaml` and `maps/my_map_save.yaml`.

### Config files that matter

- `config/gz_bridge.yaml` — single source of truth for Gazebo↔ROS topic bridges. When adding a sensor in a xacro file, add its topic here.
- `config/my_controllers.yaml` — `diff_cont` (diff_drive_controller) + `joint_broad` (joint_state_broadcaster). Used only on the real robot.
- `config/twist_mux.yaml` — joystick priority 100, navigation priority 10, 0.5 s timeouts.
- `config/nav2_params.yaml`, `config/mapper_params_online_async.yaml` — Nav2 and slam_toolbox tuning.

## Jazzy-specific notes

- Gazebo plugin filenames use the `gz-sim-*` form (e.g. `gz-sim-diff-drive-system`, `gz-sim-joint-state-publisher-system`), not Gazebo Classic's `libgazebo_ros_*.so`.
- Sensor frames are bound via `<gz_frame_id>` inside `<sensor>` — older Ignition/Iron syntax using `<ignition_frame_id>` or plugin-based frame remapping won't work on Jazzy.
- Bridge type names use the `gz.msgs.*` namespace (e.g. `gz.msgs.LaserScan`), not `ignition.msgs.*`.
