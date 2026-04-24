import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node


def generate_launch_description():

    # Check if we're told to use sim time
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_ros2_control = LaunchConfiguration('use_ros2_control')

    # Process the URDF file at launch time via the `xacro` CLI so mappings like
    # sim_mode (consumed by ros2_control.xacro) are propagated to the xacro call.
    xacro_file = PathJoinSubstitution([
        get_package_share_directory('articubot_one'),
        'description',
        'robot.urdf.xacro',
    ])
    robot_description = Command([
        'xacro ', xacro_file,
        ' sim_mode:=', use_ros2_control,
    ])

    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }]
    )


    # Launch!
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use sim time if true'),
        DeclareLaunchArgument(
            'use_ros2_control',
            default_value='false',
            description='Use ros2_control if true (also sets sim_mode for xacro)'),

        node_robot_state_publisher
    ])
