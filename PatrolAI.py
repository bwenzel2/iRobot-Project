import create
import time
import pygame
import numpy as np
import cv2
import os
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--source", type=int, help="specifies the camera that is the source of the video feed")
args = parser.parse_args()

camCode = 0
if (args.source == 1):
	camCode = 1;	#external webcam


# A helper function that attempts to detect the OS and return the appropriate port path
def getPortPath():
	osName = os.name
	if (osName == "posix"):
		portPath = "/dev/tty.KeySerial1"
	elif (osName == "Linux"):
		portPath = "/dev/ttyUSB0"
	elif (osName == "Windows"):
		portPath = "COM3" #see https://piazza.com/class/ijdbjj478bi10j?cid=273
	else:
		raise Exception("Could not determine your OS.")
	return portPath

# The speed at which the robot moves, in centimeters per second
ROBOT_SPEED = 10

# Get the port path/name string
portPath = getPortPath()

# Initialize the robot
robot = create.Create(portPath)

# The videostream used by OpenCV
cap = cv2.VideoCapture(camCode)

frame_count = 0
# Run the robot's logic loop
patrol = True
while (patrol):
	
	##### ROBOT LOGIC #####
	
	# Poll sensor values
	sensors = robot.sensors([create.LEFT_BUMP, create.RIGHT_BUMP])
	# If either of the bumpers is depressed, stop patrolling
	if (sensors[create.LEFT_BUMP] == 1 or sensors[create.RIGHT_BUMP] == 1):
		robot.stop()
		#back up
		robot.go(-ROBOT_SPEED,0)
		#pause the loop to let the robot back up a bit
		robot.stop()
		robot.turn(180, 100)
		robot.go(ROBOT_SPEED, 0)
	
	
	###### OPENCV LOGIC ######
	
	# Capture frame-by-frame
	frame = cap.read()[1]
	frame_count += 1
	print("=== FRAME " + str(frame_count) + " ===")
	
	# Remove noise in order to get cleaner contours later on
	frame = cv2.GaussianBlur(frame, (9,9), 0)
	
	# Convert BGR to HSV (Hue, Saturation, Value/Brightness) for threshholding
	hsv_image = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
	
	# Define upper and lower bounds in HSV colorspace for the color detection
	lower_blue = np.array([90,80,50])
	upper_blue = np.array([130,255,255])
	
	# Create the mask to remove all non-target colors
	mask = cv2.inRange(hsv_image, lower_blue, upper_blue)
	# Apply the mask
	masked_image = cv2.bitwise_and(frame, frame, mask=mask)
	
	# Convert to a greyscale image, otherwise cv2.findContours() complains (why is that?)
	greyscale_image = cv2.cvtColor(masked_image, cv2.COLOR_BGR2GRAY)
	
	# Threshhold the image so that all non-target color values are black and all target color values
	# are white
	thresh, black_white_image = cv2.threshold(greyscale_image, 0, 255, 0)
	
	# Find the contours
	# See http://stackoverflow.com/questions/25504964/opencv-python-valueerror-too-many-values-to-unpack
	output_image, contours, hierarchy = cv2.findContours(black_white_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
	
	# If there are any contours in the current frame, process them
	if (len(contours) > 0):
		# We only care about the largest contour (because this will most likely be our patrol node), so
		# sort the contours in place using a lambda to compare them by their size field (aka their area)
		contours.sort(key=lambda x: x.size, reverse=True)
		
		# Delete everything except the first (which is the largest) contour
		if (len(contours) > 1):
			del contours[1:]
		
		# If the largest contour has an area of less than 100 pixels, delete it too, as it's probably just noise
		if (len(contours[0]) < 100):
			del contours[0]
		
		# Now that we've culled the noise and (hopefully) isolated the node, detect the node's orientation
		if (len(contours) > 0):
			
			# Get the x,y coordinates of the bounding rect, as well as its width and height
			x,y,w,h = cv2.boundingRect(contours[0])
			node_left = x;
			node_right = x+h;
			# Get the height and width of the frame
			img_height, img_width, channels = frame.shape
			
			# The amount (in pixels) that the contour can shift to the left or right without being considered
			# off-center
			sensitivity = 150
			
			# Calculate any adjustments in the robot's direction by comparing the respective differences between
			# the left side of the contour bounding rect and the
			left_difference = node_left
			right_difference = img_width - node_right
			if (left_difference+sensitivity < right_difference):
				print("\tSkewed to the left")
				robot.go(ROBOT_SPEED, 10)
			elif (left_difference-sensitivity > right_difference):
				print("\tSkewed to the right")
				robot.go(ROBOT_SPEED, -10)
			else:
				robot.go(ROBOT_SPEED, 0)
			# Draw the bounding box of the contour
			cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),1)
	time.sleep(0.05)

	# Draw the computed contours to the image
	cv2.drawContours(frame,contours,-1, (255, 255, 255), -1)
	
	# Display the resulting frame
	cv2.imshow('Window', frame)
	if (cv2.waitKey(1) & 0xFF == ord('q')):
		break

# The logic loop is done, stop the robot and release the capture
robot.stop()
cap.release()
cv2.destroyAllWindows()
