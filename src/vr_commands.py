#!/usr/bin/env python3

import sys
import rospy
from sensor_msgs.msg import JointState
from control_msgs.msg import JointTrajectoryControllerState
from geometry_msgs.msg import Pose, PoseArray
from std_msgs.msg import Header, Bool
from geometry_msgs.msg import Point, Quaternion, Vector3, PoseStamped, TwistStamped, Twist
from std_msgs.msg import Float64MultiArray
from farming_robot_control_msgs.msg import ExternalReference
from canopies_simulator.msg import BoundBoxArray
from quest2ros.msg import OVR2ROSInputs
import os
import numpy as np
import time
import datetime
import copy

class TrajectoryHandler:
    def __init__(self):
        self.init_data_arrays()
        self.save_dir = "/home/adriano/Desktop/canopies/code/CanopiesSimulatorROS/workspace/src/imitation_learning/data"
        os.makedirs(self.save_dir,exist_ok=True)

    def init_data_arrays(self):
        self.data_joints_pos = []
        self.data_joints_vel = []
        self.data_pos = []
        self.data_or = []
        self.data_vel = []

    def size(self):
        return len(self.data_joints_pos) 

    def store_joints_pos(self, joints_pos):
        #self.data_empty = False
        self.data_joints_pos.append(joints_pos)

    def store_joints_vel(self, joints_vel):
        self.data_joints_vel.append(joints_vel)

    def store_pos(self, pos):
        self.data_pos.append(pos)

    def store_orientation(self, orientation):
        self.data_or.append(orientation)

    def store_velocity(self, vel):
        self.data_vel.append(vel)
    
    def store_external_objs(self, objects:list):
        self.data_external_objs = []
        for box in objects:
            self.data_external_objs.append(np.array([[[box.xmin, box.xmax], [box.ymin, box.ymax], [box.zmin, box.zmax]]]))
        self.data_external_objs = np.concatenate(self.data_external_objs, 0)
        #print('data_external_objs shape: ',self.data_external_objs.shape)

    def show_current_status(self):
        print('---')
        print('data_joints_pos: ', len(self.data_joints_pos))
        print('data_joints_vel: ', len(self.data_joints_vel))
        print('data_pos: ', len(self.data_pos))
        print('data_or: ', len(self.data_or))
        print('data_vel: ', len(self.data_vel))


    def save_trajectory(self, name):
        if self.size()>100:
            file = os.path.join(self.save_dir,f"trj_n={name}.npz")
            np.savez(file,
                np.concatenate(self.data_joints_pos, 0),
                np.concatenate(self.data_joints_vel, 0),
                np.concatenate(self.data_pos, 0),
                np.concatenate(self.data_or, 0),
                np.concatenate(self.data_vel, 0),
                self.data_external_objs
            )
            print(f'Trajectory of {len(self.data_joints_pos)} steps saved in {file}')
            traj_data.show_current_status()
        
    def reset(self):
        self.init_data_arrays()
        
grapes_info = np.array([])
vr_pos = np.array([0.0, 0.0, 0.0])
vr_rot = np.array([0.0, 0.0, 0.0])
vr_pos_vel = np.array([0.0, 0.0, 0.0])
vr_rot_vel = np.array([0.0, 0.0, 0.0])
d_vr_pos = np.array([0.0, 0.0, 0.0])
#current state variables
curr_pos = np.array([])
curr_or = np.array([])
curr_joints_pos = np.array([])
curr_joints_vel = np.array([])
cur_data_vel = np.array([])
curr_action = np.array([0,0,0])
init_time = time.time()

# Data to record
## CHANGED
traj_data = TrajectoryHandler()
init_pos = Point(x=0.093, y=0.1, z=-0.0728)
init_or = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

publisher_controller_right = rospy.Publisher('/external_references_for_right_arm', ExternalReference, queue_size=1)
publisher_recording = rospy.Publisher('recording_traj', Bool, queue_size=10)

resetting = False
recording = False
discard = False
save = False
block = False
term = False

def callback_recording(data):
    global traj_data
    traj_data.store_joints_pos(curr_joints_pos)
    traj_data.store_joints_vel(curr_joints_vel)
    traj_data.store_pos(curr_pos)
    traj_data.store_orientation(curr_or)
    traj_data.store_velocity(np.expand_dims(curr_action, 0))


def callback_vr_velocity_right_arm(vr_twist):
    global vr_pos_vel, vr_rot_vel
    pass 
    #vr_pos_vel[0], vr_pos_vel[1], vr_pos_vel[2] = vr_twist.linear.x, vr_twist.linear.y, vr_twist.linear.z
    #vr_rot_vel = vr_twist.angular


def callback_vr_position_right_arm(vr_pose):
    global vr_pos, vr_rot, d_vr_pos
    vr_old_pos = copy.deepcopy(vr_pos)
    vr_pos[0],vr_pos[1],vr_pos[2] = vr_pose.pose.position.x, vr_pose.pose.position.y, vr_pose.pose.position.z
    #vr_rot = vr_pose.pose.orientation
    d_vr_pos = (vr_pos - vr_old_pos)*2

def callback_grapes_info(graps_pos):
    global grapes_info
    grapes_info = graps_pos

def callback_vr_inputs_right_arm(vr_inputs):
    global term, block, resetting, recording, save, discard

    #A - Save traj
    #B - Discard traj
    #mid - REC
    #index - block
    #resetting = vr_inputs.button_upper 
    
    discard = vr_inputs.button_upper
    recording = vr_inputs.press_index 
    block = vr_inputs.press_middle
    save = vr_inputs.button_lower
    #term = vr_inputs.button_upper 
    #save = (not recording) and (traj_data.size()>0)


def callback_joint_state(joints_msg):
    global curr_joints_pos, curr_joints_vel
    curr_joints_pos = np.expand_dims(np.array(joints_msg.actual.positions), 0)
    curr_joints_vel = np.expand_dims(np.array(joints_msg.actual.velocities), 0)


def callback_end_effector_state(end_effector_msg):
    global curr_pos, curr_or
    pos = end_effector_msg.pose.position
    orient = end_effector_msg.pose.orientation
    curr_pos = np.expand_dims(np.array([pos.x,pos.y,pos.z] ), 0)
    curr_or = np.expand_dims(np.array([orient.x,orient.y,orient.z, orient.w]), 0)

def main():

    global traj_data, curr_action, save, curr_pos,curr_or,curr_joints_pos,curr_joints_vel,grapes_info

    rospy.init_node("vr_commands", anonymous=True)

    rospy.sleep(2)


    rospy.Subscriber('/q2r_right_hand_pose', PoseStamped, callback_vr_position_right_arm,queue_size=1)
    rospy.Subscriber('/q2r_right_hand_twist', Twist, callback_vr_velocity_right_arm,queue_size=1)
    rospy.Subscriber('/q2r_right_hand_inputs', OVR2ROSInputs, callback_vr_inputs_right_arm,queue_size=1)
    rospy.Subscriber('/canopies_simulator/arm_right_controller/state', JointTrajectoryControllerState, callback_joint_state)
    rospy.Subscriber('/task_2_value', PoseStamped, callback_end_effector_state)
    rospy.Subscriber('recording_traj',Bool, callback_recording)
    rospy.Subscriber('/canopies_simulator/grape_boxes', BoundBoxArray,callback_grapes_info)

    #grapes_info = rospy.wait_for_message('/canopies_simulator/grape_boxes', BoundBoxArray, timeout=5)


    control_loop_rate = rospy.Rate(100)  # 10Hz

    #collecting_init_values
    joints_msg = rospy.wait_for_message('/canopies_simulator/arm_right_controller/state', JointTrajectoryControllerState, timeout=None)
    end_effector_msg = rospy.wait_for_message('/task_2_value', PoseStamped, timeout=None)


    #get the initial pose
    curr_pos = np.expand_dims(np.array(joints_msg.actual.positions), 0)
    curr_or = np.expand_dims(np.array(joints_msg.actual.velocities), 0)
    curr_joints_pos = np.expand_dims(np.array(joints_msg.actual.positions), 0)
    curr_joints_vel = np.expand_dims(np.array(joints_msg.actual.velocities), 0)
    print("starting ...")

    # velocity_msg = Float64MultiArray()
    # velocity_msg.data = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    # Initialize arm in a standard position
    ee_pos_msg = ExternalReference()
    ee_pos_msg.position = init_pos 
    ee_pos_msg.orientation = init_or
    publisher_controller_right.publish(ee_pos_msg)
    
    rospy.sleep(2)

    pos = np.array([0.093, 0.1, -0.0728])

    print("ready ...")

    t = time.time()
    while not rospy.is_shutdown():

        # vr_inputs = rospy.wait_for_message('/q2r_right_hand_inputs', OVR2ROSInputs, timeout=5)

        if term:
            break

        if discard:
            if traj_data.size()>10:
                print('Trajectory discarded')
            traj_data.reset()

        elif resetting:
            #print('Resetting')
            ee_pos_msg = ExternalReference()
            ee_pos_msg.position = init_pos
            ee_pos_msg.orientation = init_or
            publisher_controller_right.publish(ee_pos_msg)
            pos = np.array([0.093, 0.1, -0.0728])

        elif save:
            #print('save')
            traj_data.store_external_objs(grapes_info.boxes)
            trj_n = str(datetime.datetime.now().timestamp())
            traj_data.save_trajectory(trj_n)
            traj_data.reset()
            save = False
        
        elif block:
            #print('Blocking')
            pass
        else:
            
            # TODO: still not sure if 100Hz is the best frequency (send array of waypoints?)
            # TODO: signs are wrong for some directions
            # TODO: now all actions are saved, definitely too much, on the other hand maybe I don't even need them

            # joints_info = rospy.wait_for_message('/canopies_simulator/arm_right_controller/state', JointTrajectoryControllerState, timeout=5)
            # data_joints_pos.append(np.expand_dims(np.array(joints_info.actual.positions), 0))
            # data_joints_vel.append(np.expand_dims(np.array(joints_info.actual.velocities), 0))
            #
            # ee_info = rospy.wait_for_message('/task_2_value', PoseStamped, timeout=5)
            # data_pos.append(np.expand_dims(np.array(ee_info.pose.position), 0))
            # data_or.append(np.expand_dims(np.array(ee_info.pose.orientation), 0))            

            #action = vr_pos_vel * (time.time() - t)
            action = d_vr_pos
            curr_action = action
            
            pos += action
            t = time.time()
            ee_pos_msg.position = Point(x=pos[0], y=pos[1], z=pos[2])
            ee_pos_msg.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
            publisher_controller_right.publish(ee_pos_msg)
            if recording>0.0:
                traj_data.store_joints_pos(copy.deepcopy(curr_joints_pos))
                traj_data.store_joints_vel(copy.deepcopy(curr_joints_vel))
                traj_data.store_pos(copy.deepcopy(curr_pos))
                traj_data.store_orientation(copy.deepcopy(curr_or))
                traj_data.store_velocity(np.expand_dims(action, 0))

                #publisher_recording.publish(True)
                
            control_loop_rate.sleep()



if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass


