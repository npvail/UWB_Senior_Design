import tkinter as tk
import math

# --- Circle intersection functions ---
def circle_intersections(c1, r1, c2, r2):
    x0, y0 = c1
    x1, y1 = c2
    dx = x1 - x0
    dy = y1 - y0
    d = math.hypot(dx, dy)

    # No intersection
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None

    a = (r1**2 - r2**2 + d**2) / (2*d)
    h = math.sqrt(r1**2 - a**2)
    xm = x0 + a*dx/d
    ym = y0 + a*dy/d

    xs1 = xm + h * dy/d
    ys1 = ym - h * dx/d
    xs2 = xm - h * dy/d
    ys2 = ym + h * dx/d

    return (xs1, ys1), (xs2, ys2)

def trilaterate_exact(p1, r1, p2, r2, p3, r3):
    intersections = circle_intersections(p1, r1, p2, r2)
    if not intersections:
        return None
    p_a, p_b = intersections
    # Choose the point closest to third circle
    dist_a = abs(math.hypot(p_a[0]-p3[0], p_a[1]-p3[1]) - r3)
    dist_b = abs(math.hypot(p_b[0]-p3[0], p_b[1]-p3[1]) - r3)
    return p_a if dist_a < dist_b else p_b

# --- UI Setup ---
root = tk.Tk()
root.title("UWB Tracking UI Prototype")
root.geometry("650x700")

canvas_size = 500
canvas = tk.Canvas(root, width=canvas_size, height=canvas_size, bg="white")
canvas.pack(pady=10)

# --- Input Frame ---
frame = tk.Frame(root)
frame.pack(pady=5)

entries = {}
labels = ["Room Length (X)", "Room Width (Y)",
          "Anchor1 (x,y)", "Anchor2 (x,y)", "Anchor3 (x,y)",
          "Dist1", "Dist2", "Dist3"]

for i, label in enumerate(labels):
    tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=2)
    entry = tk.Entry(frame, width=15)
    entry.grid(row=i, column=1, padx=5, pady=2)
    entries[label] = entry

# Pre-fill test values
entries["Room Length (X)"].insert(0, "6")
entries["Room Width (Y)"].insert(0, "5")
entries["Anchor1 (x,y)"].insert(0, "0,0")
entries["Anchor2 (x,y)"].insert(0, "5,0")
entries["Anchor3 (x,y)"].insert(0, "0,3")
entries["Dist1"].insert(0, "2.236")
entries["Dist2"].insert(0, "3.162")
entries["Dist3"].insert(0, "2.828")

# --- Status Label ---
status_label = tk.Label(root, text="", fg="red")
status_label.pack()

# --- Transform coordinates ---
def transform(x, y, room_length, room_width, canvas_size):
    scale_x = canvas_size / room_length
    scale_y = canvas_size / room_width
    scale = min(scale_x, scale_y)
    tx = x * scale
    ty = canvas_size - y * scale
    return tx, ty, scale

# --- Update Function ---
def update():
    status_label.config(text="")
    try:
        room_length = float(entries["Room Length (X)"].get())
        room_width = float(entries["Room Width (Y)"].get())

        p1 = tuple(map(float, entries["Anchor1 (x,y)"].get().split(',')))
        p2 = tuple(map(float, entries["Anchor2 (x,y)"].get().split(',')))
        p3 = tuple(map(float, entries["Anchor3 (x,y)"].get().split(',')))
        r1 = float(entries["Dist1"].get())
        r2 = float(entries["Dist2"].get())
        r3 = float(entries["Dist3"].get())

        anchors = [p1, p2, p3]
        distances = [r1, r2, r3]

        pos = trilaterate_exact(p1, r1, p2, r2, p3, r3)

        canvas.delete("all")
        # Draw room
        canvas.create_rectangle(0, 0, canvas_size, canvas_size, outline="black")

        # Draw anchors and distance circles
        colors = ["red", "blue", "green"]
        scale = min(canvas_size / room_length, canvas_size / room_width)

        for (x, y), r, color in zip(anchors, distances, colors):
            tx = x * scale
            ty = canvas_size - y * scale
            r_pixels = r * scale
            # Distance circle
            canvas.create_oval(tx - r_pixels, ty - r_pixels,
                               tx + r_pixels, ty + r_pixels,
                               outline=color, dash=(4,2))
            # Anchor point
            canvas.create_oval(tx-5, ty-5, tx+5, ty+5, fill=color)

        # Draw tag
        if pos:
            tx = pos[0] * scale
            ty = canvas_size - pos[1] * scale
            canvas.create_oval(tx-5, ty-5, tx+5, ty+5, fill="orange")
            status_label.config(text=f"Tag Position: ({pos[0]:.2f}, {pos[1]:.2f})", fg="green")
        else:
            status_label.config(text="No exact intersection possible.", fg="red")

    except Exception as e:
        status_label.config(text=f"Error: {e}", fg="red")

# --- Buttons ---
tk.Button(root, text="Update Position", command=update).pack(pady=5)

# Random test button
def test_random():
    import random
    for label in ["Dist1", "Dist2", "Dist3"]:
        entries[label].delete(0, tk.END)
        entries[label].insert(0, f"{random.uniform(1,5):.2f}")
    update()

tk.Button(root, text="Random Test", command=test_random).pack(pady=2)

root.mainloop()
