# uwb_ui_with_start.py
import pygame
import sys
import threading
import serial
import serial.tools.list_ports
import time
import math

# ------------------- UI / App Settings -------------------
WIDTH, HEIGHT = 900, 700
MARGIN = 20
FONT_SIZE = 26
INPUT_WIDTH, INPUT_HEIGHT = 60, 30
BUTTON_W, BUTTON_H = 140, 36

# ------------------- COLORS -------------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (180, 180, 180)
LIGHT_GRAY = (220, 220, 220)
RED = (255, 0, 0)
GREEN = (100, 200, 100)
BLUE = (50, 130, 230)
DARK = (30, 30, 30)

# ------------------- PYGAME INIT -------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("UWB Anchor Setup UI — Start Tracking")
font = pygame.font.SysFont(None, FONT_SIZE)

# ------------------- BACKGROUND -------------------
BG_FILENAME = "room3.jpg"
if not pygame.image.get_extended():
    pass
try:
    bg_image_orig = pygame.image.load(BG_FILENAME).convert()
except Exception as e:
    raise FileNotFoundError(f"{BG_FILENAME} not found or failed to load: {e}")
bg_image = bg_image_orig.copy()
bg_rect = None

# ------------------- ANCHORS UI -------------------
anchors = [
    {"name": "ANC 0", "x": None, "y": None},  # bottom-left
    {"name": "ANC 1", "x": None, "y": None},
    {"name": "ANC 2", "x": None, "y": None}   # top-right
]

input_boxes = []
for i, anc in enumerate(anchors):
    x_box = pygame.Rect(100, 50 + i * 60, INPUT_WIDTH, INPUT_HEIGHT)
    y_box = pygame.Rect(175, 50 + i * 60, INPUT_WIDTH, INPUT_HEIGHT)
    set_button = pygame.Rect(250, 50 + i * 60, 60, INPUT_HEIGHT)
    input_boxes.append({
        "x_box": x_box,
        "y_box": y_box,
        "button": set_button,
        "active": None,
        "text_x": "",
        "text_y": ""
    })

all_set = False
scale = 1.0

# ------------------- UWB classes (from your working code) -------------------
class UWB:
    def __init__(self, name, type):
        self.name = name
        self.type = type  # 0 anchor, 1 tag
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []
        self.color = RED if self.type == 1 else BLACK

    def set_location(self, x, y):
        self.x = x
        self.y = y
        self.status = True

    def cal(self):
        # same algorithm as working code
        count = 0
        anc_id_list = []
        for r in self.list:
            if r != 0:
                anc_id_list.append(count)
            count += 1

        # debug
        print(f"[DEBUG] Anchor IDs with valid ranges: {anc_id_list}")

        if len(anc_id_list) >= 3:
            x = 0.0
            y = 0.0

            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[1])
            x += temp_x; y += temp_y

            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[2])
            x += temp_x; y += temp_y

            temp_x, temp_y = self.three_point_uwb(anc_id_list[2], anc_id_list[1])
            x += temp_x; y += temp_y

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
        p2p = (x1 - x2)*(x1 - x2) + (y1 - y2)*(y1 - y2)
        p2p = math.sqrt(p2p)
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1 * r1 - r2 * r2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p
        return temp_x, temp_y

# Prepare anchor/tag objects (will set anchor locations after UI)
anc = [UWB(f"ANC {i}", 0) for i in range(3)]
tag = [UWB("TAG 0", 1)]

# ------------------- Serial / Threading state -------------------
serial_thread = None
serial_stop_event = threading.Event()
serial_lock = threading.Lock()
ser = None

# button rect
start_button = pygame.Rect(WIDTH - BUTTON_W - 30, 30, BUTTON_W, BUTTON_H)
stop_button = pygame.Rect(WIDTH - BUTTON_W - 30, 30 + BUTTON_H + 10, BUTTON_W, BUTTON_H)
tracking_started = False

# ------------------- Helpers -------------------
def draw_text(text, x, y, color=BLACK):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))

def all_anchors_set():
    return all(a["x"] is not None and a["y"] is not None for a in anchors)

def resize_background_and_scale():
    global bg_image, bg_rect, scale
    anc0 = anchors[0]
    anc2 = anchors[2]
    room_width = abs(anc2["x"] - anc0["x"])
    room_height = abs(anc2["y"] - anc0["y"])
    if room_width == 0 or room_height == 0:
        return
    scale_x = (WIDTH - 2 * MARGIN) / room_width
    scale_y = (HEIGHT - 2 * MARGIN) / room_height
    scale = min(scale_x, scale_y)
    rect_width = int(room_width * scale)
    rect_height = int(room_height * scale)
    px0 = MARGIN
    py0 = HEIGHT - MARGIN - rect_height
    bg_image = pygame.transform.scale(bg_image_orig, (rect_width, rect_height))
    bg_rect = bg_image.get_rect(topleft=(px0, py0))

def draw_anchors():
    anc0 = anchors[0]
    for a in anchors:
        if a["x"] is not None and a["y"] is not None:
            px = int((a["x"] - anc0["x"]) * scale + MARGIN)
            py = HEIGHT - int((a["y"] - anc0["y"]) * scale + MARGIN)
            pygame.draw.circle(screen, RED, (px, py), 8)
            draw_text(f'{a["name"]} ({a["x"]},{a["y"]})', px + 10, py - 10)

def draw_tag():
    with serial_lock:
        t = tag[0]
        if t.status:
            anc0 = anchors[0]
            px = int((t.x - anc0["x"]) * scale + MARGIN)
            py = HEIGHT - int((t.y - anc0["y"]) * scale + MARGIN)
            pygame.draw.circle(screen, GREEN, (px, py), 10)
            draw_text(f'{t.name} ({int(t.x)},{int(t.y)})', px + 10, py - 10)

# ------------------- Serial port utilities (match your working code) -------------------
def get_frist_com():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print("found port:", port.device)
        if  "usbserial" in port.device or \
            "CH340" in port.description or \
            "wchusbserial" in port.device or \
            "1A86:7523" in port.hwid:
            print(f"Found compatible port: {port.device}")
            return port.device
    print("WARNING: No compatible serial port found.")
    return None

# Serial reader thread — uses same parsing + logic as your working code
def serial_reader_thread():
    global ser
    port = get_frist_com()
    if not port:
        print("[ERROR] No port found - serial reader exiting.")
        return
    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print("[ERROR] Failed to open serial:", e)
        return

    print(f"[INFO] Serial opened on {port}")
    try:
        ser.write("begin".encode('UTF-8'))
    except:
        pass
    ser.reset_input_buffer()
    runtime = time.time()

    while not serial_stop_event.is_set():
        try:
            line = ser.readline().decode('UTF-8').replace('\n', '')
            if not line:
                continue

            tid = None
            range_values = []

            # ---------------- Parse AT+RANGE=... ----------------
            if line.startswith("AT+RANGE="):
                try:
                    # Example line formats seen in the wild:
                    # AT+RANGE=tag:0,ts:12345,anc:3,rng:(227,0,0)
                    # or sometimes with spaces or missing parentheses
                    rest = line.split("=", 1)[1]
                    parts = [p.strip() for p in rest.split(",")]
                    # find tag id
                    tid = None
                    for p in parts:
                        if p.startswith("tag:") or p.startswith("tid:"):
                            try:
                                tid = int(p.split(":", 1)[1])
                            except:
                                pass

                    # find ranges part (look for 'rng:' or parentheses)
                    ranges_candidate = None
                    for p in parts:
                        if p.startswith("rng:") or p.startswith("ranges:") or p.startswith("r:") or "(" in p:
                            ranges_candidate = p
                            break

                    if ranges_candidate is None:
                        # maybe the ranges are in the last part after an anc:...
                        ranges_candidate = parts[-1]

                    # extract numbers from the candidate
                    rng_text = ranges_candidate
                    if ":(" in rng_text:
                        rng_text = rng_text.split(":(" ,1)[1].rstrip(")")
                    elif "(" in rng_text and ")" in rng_text:
                        rng_text = rng_text.split("(",1)[1].split(")",1)[0]
                    elif ":" in rng_text:
                        rng_text = rng_text.split(":",1)[1]

                    # split by commas and filter empty
                    rng_parts = [r.strip() for r in rng_text.split(",") if r.strip() != ""]
                    # convert to ints, keep 0 as 0
                    range_values = []
                    for r in rng_parts:
                        try:
                            range_values.append(int(r))
                        except:
                            # ignore non-int tokens
                            pass

                    if tid is None:
                        tid = 0

                    print(f"[DEBUG] Raw AT+RANGE line: '{line}'")
                    print(f"[LOG] AT+RANGE parsed: tid={tid}, ranges={range_values}")
                except Exception as e:
                    print(f"[ERROR] Failed to parse AT+RANGE line: {line}, {e}")
                    continue

            # ---------------- Parse nge:(...) ----------------
            elif "nge:" in line:
                try:
                    ranges_str = line.split("nge:(")[1].split(")")[0]
                    range_values = [int(r) if r != "0" else 0 for r in ranges_str.split(",")]
                    tid = 0  # always tag 0 for nge format
                    print(f"[LOG] nge parsed: tid={tid}, ranges={range_values}")
                except Exception as e:
                    print(f"[ERROR] Failed to parse nge line: {line}, {e}")
                    continue

            else:
                print(f"[LOG] Unrecognized data format: {line}")
                continue

            # ---------------- Update tag and compute ----------------
            with serial_lock:
                if tid is not None and tid < len(tag):
                    tag[tid].list = range_values
                    valid_ranges = [r for r in range_values if r > 0]

                    if len(valid_ranges) >= 3:
                        if all_anchors_set():
                            # ensure UWB anchor objects have coordinates from UI
                            for i in range(len(anchors)):
                                anc[i].set_location(anchors[i]["x"], anchors[i]["y"])
                            tag[tid].cal()
                        else:
                            print("[WARN] Anchors not set yet — skipping calculation")
                    else:
                        print(f"[WARNING] Not enough valid ranges for tag {tid}: {valid_ranges}")

            # ---------------- Optional flush ----------------
            if (time.time() - runtime) > 0.5:
                runtime = time.time()
                try:
                    ser.reset_input_buffer()
                except:
                    pass

        except Exception as e:
            print("[ERROR] Serial read error:", e)
            time.sleep(0.05)

    # exiting
    try:
        ser.close()
    except:
        pass
    print("[INFO] Serial thread exiting.")

# ------------------- Main Loop -------------------
running = True
clock = pygame.time.Clock()

while running:
    screen.fill(WHITE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            # stop serial thread if running
            serial_stop_event.set()
            if serial_thread and serial_thread.is_alive():
                serial_thread.join(timeout=1)
            if ser and ser.is_open:
                try: ser.close()
                except: pass
            pygame.quit()
            sys.exit()

        # input handling only until all_set
        if not all_set:
            if event.type == pygame.MOUSEBUTTONDOWN:
                for i, boxes in enumerate(input_boxes):
                    if boxes["x_box"].collidepoint(event.pos):
                        boxes["active"] = "x"
                    elif boxes["y_box"].collidepoint(event.pos):
                        boxes["active"] = "y"
                    elif boxes["button"].collidepoint(event.pos):
                        try:
                            anchors[i]["x"] = float(boxes["text_x"])
                            anchors[i]["y"] = float(boxes["text_y"])
                        except ValueError:
                            pass
                        boxes["active"] = None

                        if all_anchors_set():
                            all_set = True
                            # compute scale and resize bg
                            resize_background_and_scale()
            elif event.type == pygame.KEYDOWN:
                for boxes in input_boxes:
                    if boxes["active"] == "x":
                        if event.key == pygame.K_BACKSPACE:
                            boxes["text_x"] = boxes["text_x"][:-1]
                        elif event.key == pygame.K_RETURN:
                            boxes["active"] = None
                        else:
                            boxes["text_x"] += event.unicode
                    elif boxes["active"] == "y":
                        if event.key == pygame.K_BACKSPACE:
                            boxes["text_y"] = boxes["text_y"][:-1]
                        elif event.key == pygame.K_RETURN:
                            boxes["active"] = None
                        else:
                            boxes["text_y"] += event.unicode

        # When anchors set, allow clicking Start/Stop
        else:
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # Start Tracking
                if start_button.collidepoint((mx, my)) and not tracking_started:
                    # set UWB anchor coordinates into anc objects
                    for i in range(3):
                        anc[i].set_location(anchors[i]["x"], anchors[i]["y"])
                    # start serial thread
                    serial_stop_event.clear()
                    serial_thread = threading.Thread(target=serial_reader_thread, daemon=True)
                    serial_thread.start()
                    tracking_started = True
                # Stop Tracking
                if stop_button.collidepoint((mx, my)) and tracking_started:
                    serial_stop_event.set()
                    if serial_thread and serial_thread.is_alive():
                        serial_thread.join(timeout=1)
                    tracking_started = False

        # handle window resize
        if event.type == pygame.VIDEORESIZE:
            WIDTH, HEIGHT = event.w, event.h
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            # reposition buttons based on new width
            start_button.x = WIDTH - BUTTON_W - 30
            stop_button.x = WIDTH - BUTTON_W - 30
            if all_set:
                resize_background_and_scale()

    # Draw UI or scene
    if not all_set:
        draw_text("Enter Anchor Coordinates (cm):", 50, 15)
        for i, anc_item in enumerate(anchors):
            boxes = input_boxes[i]
            # right-align the label so it sits just left of the x input box and won't be clipped
            label_text = anc_item["name"]
            text_w = font.size(label_text)[0]
            label_right = boxes["x_box"].x - 10
            label_x = max(5, label_right - text_w)
            draw_text(label_text, label_x, boxes["x_box"].y + 2)
            pygame.draw.rect(screen, LIGHT_GRAY if boxes["active"] == "x" else GRAY, boxes["x_box"])
            pygame.draw.rect(screen, LIGHT_GRAY if boxes["active"] == "y" else GRAY, boxes["y_box"])
            pygame.draw.rect(screen, GREEN, boxes["button"])
            draw_text(boxes["text_x"], boxes["x_box"].x + 5, boxes["x_box"].y + 5)
            draw_text(boxes["text_y"], boxes["y_box"].x + 5, boxes["y_box"].y + 5)
            draw_text("Set", boxes["button"].x + 10, boxes["button"].y + 5, WHITE)
    else:
        # draw scaled background and anchors
        if bg_rect:
            screen.blit(bg_image, bg_rect)
        draw_anchors()

        # Draw Start/Stop buttons
        if not tracking_started:
            pygame.draw.rect(screen, BLUE, start_button, border_radius=6)
            draw_text("Start Tracking", start_button.x + 14, start_button.y + 8, WHITE)
        else:
            pygame.draw.rect(screen, DARK, start_button, border_radius=6)
            draw_text("Tracking...", start_button.x + 24, start_button.y + 8, WHITE)

        pygame.draw.rect(screen, (200, 60, 60) if tracking_started else GRAY, stop_button, border_radius=6)
        draw_text("Stop Tracking", stop_button.x + 18, stop_button.y + 8, WHITE)

        # draw computed tag (thread updates tag[0].x/y/status)
        draw_tag()

    pygame.display.flip()
    clock.tick(30)

# cleanup on exit
serial_stop_event.set()
if serial_thread and serial_thread.is_alive():
    serial_thread.join(timeout=1)
if ser:
    try: ser.close()
    except: pass
pygame.quit()
