# Import necessary libraries
import pygame
import serial
import serial.tools.list_ports
import json
import csv
import os
import time
import math

# Define colors
RED = [255, 0, 0]
BLACK = [0, 0, 0]
WHITE = [255, 255, 255]

# UWB class to represent anchors and tags
class UWB:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []

        if self.type == 1:
            self.color = RED
        else:
            self.color = BLACK

    def set_location(self, x, y):
        self.x = x
        self.y = y
        self.status = True

    def cal(self):
        count = 0
        anc_id_list = []
        for range in self.list:
            if range != 0:
                anc_id_list.append(count)
            count += 1

        print(f"[DEBUG] Anchor IDs with valid ranges: {anc_id_list}")

        if len(anc_id_list) >= 3:
            x = 0.0
            y = 0.0

            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[1])
            x += temp_x
            y += temp_y

            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[2])
            x += temp_x
            y += temp_y

            temp_x, temp_y = self.three_point_uwb(anc_id_list[2], anc_id_list[1])
            x += temp_x
            y += temp_y

            x = int(x / 3)
            y = int(y / 3)

            print(f"[DEBUG] Calculated position for {self.name}: ({x}, {y})")

            self.set_location(x, y)
            self.status = True
        else:
            print(f"[WARNING] Not enough anchors to calculate position for {self.name}")

    def three_point_uwb(self, a_id, b_id):
        x, y = self.three_point(anc[a_id].x, anc[a_id].y, anc[b_id].x,
                                anc[b_id].y, self.list[a_id], self.list[b_id])

        return x, y

    def three_point(self, x1, y1, x2, y2, r1, r2):
        temp_x = 0.0
        temp_y = 0.0
        # Distance between anchor points
        p2p = (x1 - x2)*(x1 - x2) + (y1 - y2)*(y1 - y2)
        p2p = math.sqrt(p2p)

        # Check if circles intersect
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1 * r1 - r2 * r2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p

        return temp_x, temp_y

# Get the first available COM port
# def get_frist_com():
#     port_list = serial.tools.list_ports.comports()

#     if len(port_list) <= 0:
#         print("No COM")
#         return ""
#     else:
#         print("First COM")
#         for com in port_list:
#             print(com)
#             return list(com)[0]

def get_frist_com():
    port_list = serial.tools.list_ports.comports()
    for port in port_list:
        print("found port:", port.device)
        # Add a check for Mac-specific serial port names
        if  "usbserial" in port.device or \
            "CH340" in port.description or \
            "wchusbserial" in port.device or \
            "1A86:7523" in port.hwid:
            print(f"Found compatible port: {port.device}")
            return port.device
    print("WARNING: No compatible serial port found.")
    return None

# Draw UWB objects on the screen
def draw_uwb(uwb):
    # Convert coordinates to pixels
    pixel_x = int(uwb.x * cm2p + x_offset)
    pixel_y = SCREEN_Y - int(uwb.y * cm2p + y_offset)

    if uwb.status:
        r = 10

        temp_str = uwb.name + " (" + str(uwb.x) + "," + str(uwb.y)+")"

        font = pygame.font.SysFont("Consola", 24)
        surf = font.render(temp_str, True, uwb.color)
        screen.blit(surf, [pixel_x, pixel_y])

        pygame.draw.circle(screen, uwb.color, [
            pixel_x + 20, pixel_y + 50], r, 0)

# Read data from the serial port
def read_data():
    line = ser.readline().decode('UTF-8').replace('\n', '')

    try:
        if line.startswith("AT+RANGE="):
            # Parse the AT+RANGE format
            parts = line.split("=")[1].split(",")
            tid = int(parts[0].split(":")[1])
            ranges = parts[3].split(":")[1].strip("()")
            range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]

            print(f"[LOG] Parsed data: tid={tid}, ranges={range_values}")

            tag[tid].list = range_values

            # Check if there are at least three valid ranges
            valid_ranges = [r for r in range_values if r > 0]
            if len(valid_ranges) >= 3:
                tag[tid].cal()
            else:
                print(f"[WARNING] Insufficient valid ranges for tag {tid}: {valid_ranges}")
        elif "nge:" in line:
            # Handle the nge:(...) format
            try:
                ranges = line.split("nge:(")[1].split(")")[0]
                range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]

                print(f"[LOG] Parsed data from 'nge': ranges={range_values}")

                # Assuming tid=0 for this format
                tid = 0
                tag[tid].list = range_values

                # Check if there are at least three valid ranges
                valid_ranges = [r for r in range_values if r > 0]
                if len(valid_ranges) >= 3:
                    tag[tid].cal()
                else:
                    print(f"[WARNING] Insufficient valid ranges for tag {tid}: {valid_ranges}")
            except Exception as e:
                print(f"[ERROR] Failed to parse 'nge' format: {line}, Error: {e}")
        else:
            print(f"[LOG] Unrecognized data format: {line}")

    except Exception as e:
        print(f"[ERROR] Failed to parse data: {line}, Error: {e}")

# Refresh the display
def fresh_page():
    runtime = time.time()
    screen.fill(WHITE)
    for uwb in anc:
        draw_uwb(uwb)
    for uwb in tag:
        draw_uwb(uwb)

    pygame.draw.line(screen, BLACK, (CENTER_X_PIEXL, 0),
                     (CENTER_X_PIEXL, SCREEN_Y), 1)
    pygame.draw.line(screen, BLACK, (0, CENTER_Y_PIEXL),
                     (SCREEN_X, CENTER_Y_PIEXL), 1)

    pygame.display.flip()

    print("Fresh Over, Use Time:")
    print(time.time() - runtime)

# Calculate distance between two points
def distance(x1, y1, x2, y2):
    return math.sqrt((x2-x1) ** 2 + (y2 - y1)**2)

# Main Function .............................................................

SCREEN_X = 800
SCREEN_Y = 800

pygame.init()
screen = pygame.display.set_mode([SCREEN_X, SCREEN_Y])
ser = serial.Serial(get_frist_com(), 115200)

anc = []
tag = []
anc_count = 3
tag_count = 1

# Anchor positions
A0X, A0Y = 0, 0
A1X, A1Y = 130, 0
A2X, A2Y = 130, 130
A3X, A3Y = 0, 130

CENTER_X = int((A0X+A1X+A2X)/3)
CENTER_Y = int((A0Y+A1Y+A2Y)/3)

r0 = distance(A0X, A0Y, CENTER_X, CENTER_Y)
r1 = distance(A1X, A1Y, CENTER_X, CENTER_Y)
r2 = distance(A2X, A2Y, CENTER_X, CENTER_Y)
r3 = distance(A3X, A3Y, CENTER_X, CENTER_Y)

r = max(r0, r1, r2, r3)

cm2p = SCREEN_X / 2 * 0.9 / r

# Meter to pixel conversion
x_offset = SCREEN_X / 2 - CENTER_X * cm2p
y_offset = SCREEN_Y / 2 - CENTER_Y * cm2p

CENTER_X_PIEXL = CENTER_X * cm2p + x_offset
CENTER_Y_PIEXL = CENTER_Y * cm2p + y_offset

for i in range(anc_count):
    name = "ANC " + str(i)
    anc.append(UWB(name, 0))
for i in range(tag_count):
    name = "TAG " + str(i)
    tag.append(UWB(name, 1))
anc[0].set_location(A0X, A0Y)
anc[1].set_location(A1X, A1Y)
anc[2].set_location(A2X, A2Y)

fresh_page()
ser.write("begin".encode('UTF-8'))
ser.reset_input_buffer()

runtime = time.time()

# Add a pygame event loop to keep the window responsive
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    read_data()

    if (time.time() - runtime) > 0.5:
        fresh_page()
        runtime = time.time()
        ser.reset_input_buffer()

# Package Command
# pyinstaller --onefile .\position.py  
