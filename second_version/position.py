# Import necessary libraries
import pygame
import serial
import serial.tools.list_ports
import os
import time
import math

# Define colors
RED = [255, 0, 0]
BLACK = [0, 0, 0]
WHITE = [255, 255, 255]
TAG_COLORS = [[255, 0, 0], [0, 128, 0], [0, 0, 255], [255, 165, 0]]  # colors per tag

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
            self.set_location(x, y)
            self.status = True

    def three_point_uwb(self, a_id, b_id):
        x, y = self.three_point(anc[a_id].x, anc[a_id].y, anc[b_id].x,
                                anc[b_id].y, self.list[a_id], self.list[b_id])
        return x, y

    def three_point(self, x1, y1, x2, y2, r1, r2):
        p2p = math.hypot(x2 - x1, y2 - y1)
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1 * r1 - r2 * r2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p
        return temp_x, temp_y

# Get the first available COM port
def get_frist_com():
    port_list = serial.tools.list_ports.comports()
    for port in port_list:
        if "usbserial" in port.device or "CH340" in port.description or \
           "wchusbserial" in port.device or "1A86:7523" in port.hwid:
            return port.device
    return None

# Draw UWB objects on the screen
def draw_uwb(uwb, show_range=True):
    pixel_x = int(uwb.x * cm2p + x_offset)
    pixel_y = SCREEN_Y - int(uwb.y * cm2p + y_offset)

    if uwb.status:
        r = 10
        temp_str = uwb.name + f" ({uwb.x},{uwb.y})"
        font = pygame.font.SysFont("Consola", 24)
        surf = font.render(temp_str, True, uwb.color)
        screen.blit(surf, [pixel_x, pixel_y])
        pygame.draw.circle(screen, uwb.color, [pixel_x + 20, pixel_y + 50], r, 0)

        # Draw all range circles for trilateration
        if show_range and uwb.type == 0:  # anchors
            for t_idx, t in enumerate(tag):
                if len(t.list) >= len(anc):
                    radius_value = t.list[anc.index(uwb)]
                    if radius_value > 0:
                        radius_px = int(radius_value * cm2p)
                        color = TAG_COLORS[t_idx % len(TAG_COLORS)]
                        pygame.draw.circle(screen, color, [pixel_x, pixel_y], radius_px, 1)

# Read data from serial
def read_data():
    line = ser.readline().decode('UTF-8').replace('\n', '')
    try:
        if line.startswith("AT+RANGE="):
            parts = line.split("=")[1].split(",")
            tid = int(parts[0].split(":")[1])
            ranges = parts[3].split(":")[1].strip("()")
            range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
            tag[tid].list = range_values
            valid_ranges = [r for r in range_values if r > 0]
            if len(valid_ranges) >= 3:
                tag[tid].cal()
        elif "nge:" in line:
            ranges = line.split("nge:(")[1].split(")")[0]
            range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
            tid = 0
            tag[tid].list = range_values
            valid_ranges = [r for r in range_values if r > 0]
            if len(valid_ranges) >= 3:
                tag[tid].cal()
    except:
        pass

# Refresh display
def fresh_page():
    screen.fill(WHITE)
    for uwb in anc:
        draw_uwb(uwb, show_range=True)
    for uwb in tag:
        draw_uwb(uwb, show_range=False)
    pygame.draw.line(screen, BLACK, (CENTER_X_PIEXL, 0), (CENTER_X_PIEXL, SCREEN_Y), 1)
    pygame.draw.line(screen, BLACK, (0, CENTER_Y_PIEXL), (SCREEN_X, CENTER_Y_PIEXL), 1)
    pygame.display.flip()

# Distance function
def distance(x1, y1, x2, y2):
    return math.hypot(x2-x1, y2-y1)

# Pygame manual input for anchors
def input_anchor_coordinates():
    font = pygame.font.SysFont("Consola", 24)
    coords = []
    for i in range(3):
        input_str = ""
        active = True
        while active:
            screen.fill(WHITE)
            prompt = font.render(f"Enter X,Y for ANC {i}:", True, BLACK)
            screen.blit(prompt, (50, 50))
            input_surface = font.render(input_str, True, RED)
            screen.blit(input_surface, (50, 100))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        try:
                            x_str, y_str = input_str.split(",")
                            coords.append((float(x_str), float(y_str)))
                            active = False
                        except:
                            input_str = ""
                    elif event.key == pygame.K_BACKSPACE:
                        input_str = input_str[:-1]
                    else:
                        input_str += event.unicode
    return coords

# --- Main setup ---
SCREEN_X = 800
SCREEN_Y = 800
pygame.init()
screen = pygame.display.set_mode([SCREEN_X, SCREEN_Y])
ser = serial.Serial(get_frist_com(), 115200)

anc_count = 3
tag_count = 1
anc = [UWB(f"ANC {i}", 0) for i in range(anc_count)]
tag = [UWB(f"TAG {i}", 1) for i in range(tag_count)]

# Manual anchor input
anchor_coords = input_anchor_coordinates()
for i, (x, y) in enumerate(anchor_coords):
    anc[i].set_location(x, y)

# --- Auto-scale anchors ---
min_x = min(a.x for a in anc)
max_x = max(a.x for a in anc)
min_y = min(a.y for a in anc)
max_y = max(a.y for a in anc)
range_x = max(max_x - min_x, 1)
range_y = max(max_y - min_y, 1)
margin = 0.1
cm2p = min(SCREEN_X * (1 - margin) / range_x, SCREEN_Y * (1 - margin) / range_y)
x_offset = SCREEN_X/2 - ((min_x + max_x)/2) * cm2p
y_offset = SCREEN_Y/2 - ((min_y + max_y)/2) * cm2p
CENTER_X_PIEXL = (min_x + max_x)/2 * cm2p + x_offset
CENTER_Y_PIEXL = SCREEN_Y - ((min_y + max_y)/2 * cm2p + y_offset)

fresh_page()
ser.write("begin".encode('UTF-8'))
ser.reset_input_buffer()
runtime = time.time()

# --- Main loop ---
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
