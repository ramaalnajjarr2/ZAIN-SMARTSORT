import cv2
import threading
import queue
import time
import serial
import customtkinter as ctk
import numpy as np

from PIL import Image
from transformers import pipeline


# ==========================================
# ZAIN SMARTSORT
# AI-Powered Waste Sorting System
# Developed by Zain Yaser Alnajjar
# ==========================================

# ---------- SETTINGS ----------

MODEL_NAME = "tribber93/my-trash-classification"

BG = "#0B1220"
CARD = "#142033"
CARD_LIGHT = "#1D2D43"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
GREEN = "#22C55E"
YELLOW = "#FBBF24"
RED = "#FB7185"

BIN_COLORS = {
    "PAPER": "#60A5FA",
    "PLASTIC": "#22C55E",
    "METAL": "#FBBF24"
}

MIN_CONFIDENCE = 0.40
SERIAL_PORT = "COM4"       # Change if Arduino uses a different port
SERIAL_BAUD = 9600

# Minimum percentage of changed pixels
OBJECT_THRESHOLD = 0.08

# Minimum brightness difference per pixel
PIXEL_DIFFERENCE = 30


# ==========================================
# APPLICATION SETUP
# ==========================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Zain SmartSort | AI Waste Sorting")
app.geometry("1120x860")
app.minsize(980, 760)
app.configure(fg_color=BG)

running = True
scanning = False
bin_open = False

current_frame = None
background_frame = None
classifier = None

# Protect frames shared between threads
frame_lock = threading.Lock()

# The serial connection is owned by one background thread.
arduino_ready = False
arduino_events = queue.Queue()
ui_events = queue.Queue()
arduino_commands = queue.Queue(maxsize=1)


# ==========================================
# MAIN LAYOUT
# ==========================================

main = ctk.CTkFrame(
    app,
    fg_color="transparent"
)
main.pack(
    fill="both",
    expand=True,
    padx=28,
    pady=18
)


# ==========================================
# HEADER
# ==========================================

header = ctk.CTkFrame(
    main,
    fg_color="transparent"
)
header.pack(fill="x", pady=(0, 16))

header_left = ctk.CTkFrame(
    header,
    fg_color="transparent"
)
header_left.pack(side="left")

ctk.CTkLabel(
    header_left,
    text="♻  ZAIN SMARTSORT",
    font=("Arial", 32, "bold"),
    text_color=TEXT
).pack(anchor="w")

ctk.CTkLabel(
    header_left,
    text="AI-POWERED WASTE SORTING SYSTEM",
    font=("Arial", 12),
    text_color=MUTED
).pack(anchor="w", pady=(3, 0))

system_badge = ctk.CTkLabel(
    header,
    text="●  LOADING AI...",
    font=("Arial", 12, "bold"),
    text_color=YELLOW,
    fg_color=CARD,
    corner_radius=12,
    padx=18,
    pady=12
)
system_badge.pack(side="right")

arduino_badge = ctk.CTkLabel(
    header,
    text="● ARDUINO NOT CONNECTED",
    font=("Arial", 12, "bold"),
    text_color=RED,
    fg_color=CARD,
    corner_radius=12,
    padx=14,
    pady=12
)
arduino_badge.pack(side="right", padx=(0, 10))


# ==========================================
# CAMERA AND ANALYSIS AREA
# ==========================================

content = ctk.CTkFrame(
    main,
    fg_color="transparent"
)
content.pack(fill="both", expand=True)

content.grid_columnconfigure(0, weight=3)
content.grid_columnconfigure(1, weight=2)
content.grid_rowconfigure(0, weight=1)


# ---------- CAMERA CARD ----------

camera_card = ctk.CTkFrame(
    content,
    fg_color=CARD,
    corner_radius=18
)
camera_card.grid(
    row=0,
    column=0,
    padx=(0, 14),
    sticky="nsew"
)

ctk.CTkLabel(
    camera_card,
    text="◉  LIVE WASTE DETECTION",
    font=("Arial", 15, "bold"),
    text_color=TEXT
).pack(anchor="w", padx=20, pady=(18, 10))

camera_label = ctk.CTkLabel(
    camera_card,
    text="Starting camera...",
    width=580,
    height=350,
    fg_color="#050A12",
    corner_radius=12
)
camera_label.pack(
    padx=18,
    pady=(0, 12),
    fill="both",
    expand=True
)

ctk.CTkLabel(
    camera_card,
    text="PLACE THE OBJECT INSIDE THE GREEN SQUARE",
    font=("Arial", 11),
    text_color=MUTED
).pack(pady=(0, 8))

keyboard_frame = ctk.CTkFrame(
    camera_card,
    fg_color=CARD_LIGHT,
    corner_radius=12
)
keyboard_frame.pack(
    fill="x",
    padx=20,
    pady=(0, 18)
)

ctk.CTkLabel(
    keyboard_frame,
    text="SPACE  →  SCAN",
    font=("Arial", 13, "bold"),
    text_color=GREEN
).pack(side="left", padx=18, pady=12)

ctk.CTkLabel(
    keyboard_frame,
    text="B  →  SET EMPTY BACKGROUND",
    font=("Arial", 12, "bold"),
    text_color=YELLOW
).pack(side="right", padx=18, pady=12)


# ---------- ANALYSIS CARD ----------

result_card = ctk.CTkFrame(
    content,
    fg_color=CARD,
    corner_radius=18
)
result_card.grid(
    row=0,
    column=1,
    sticky="nsew"
)

ctk.CTkLabel(
    result_card,
    text="AI ANALYSIS",
    font=("Arial", 15, "bold"),
    text_color=TEXT
).pack(anchor="w", padx=22, pady=(20, 15))

status_label = ctk.CTkLabel(
    result_card,
    text="● INITIALIZING",
    font=("Arial", 13, "bold"),
    text_color=YELLOW
)
status_label.pack(anchor="w", padx=22)

ctk.CTkLabel(
    result_card,
    text="DETECTED MATERIAL",
    font=("Arial", 11),
    text_color=MUTED
).pack(anchor="w", padx=22, pady=(28, 5))

material_label = ctk.CTkLabel(
    result_card,
    text="—",
    font=("Arial", 30, "bold"),
    text_color=TEXT
)
material_label.pack(anchor="w", padx=22)

ctk.CTkLabel(
    result_card,
    text="SELECTED DESTINATION",
    font=("Arial", 11),
    text_color=MUTED
).pack(anchor="w", padx=22, pady=(23, 5))

destination_label = ctk.CTkLabel(
    result_card,
    text="Waiting for scan",
    font=("Arial", 19, "bold"),
    text_color=GREEN
)
destination_label.pack(anchor="w", padx=22)

ctk.CTkLabel(
    result_card,
    text="MODEL SCORE",
    font=("Arial", 11),
    text_color=MUTED
).pack(anchor="w", padx=22, pady=(25, 5))

confidence_label = ctk.CTkLabel(
    result_card,
    text="—",
    font=("Arial", 22, "bold"),
    text_color=TEXT
)
confidence_label.pack(anchor="w", padx=22)

confidence_bar = ctk.CTkProgressBar(
    result_card,
    height=12,
    progress_color=GREEN,
    fg_color=CARD_LIGHT
)
confidence_bar.pack(
    fill="x",
    padx=22,
    pady=(10, 18)
)
confidence_bar.set(0)

separator = ctk.CTkFrame(
    result_card,
    height=2,
    fg_color=CARD_LIGHT
)
separator.pack(fill="x", padx=22, pady=12)

ctk.CTkLabel(
    result_card,
    text="SYSTEM WORKFLOW",
    font=("Arial", 12, "bold"),
    text_color=TEXT
).pack(anchor="w", padx=22, pady=(4, 10))

ctk.CTkLabel(
    result_card,
    text=(
        "01   OBJECT DETECTION\n\n"
        "02   AI CLASSIFICATION\n\n"
        "03   BIN SELECTION\n\n"
        "04   ARDUINO BIN CONTROL"
    ),
    font=("Arial", 12),
    text_color=MUTED,
    justify="left"
).pack(anchor="w", padx=22)


# ==========================================
# SMART BINS
# ==========================================

bins_section = ctk.CTkFrame(
    main,
    fg_color="transparent"
)
bins_section.pack(fill="x", pady=(16, 8))

ctk.CTkLabel(
    bins_section,
    text="SMART SORTING BINS",
    font=("Arial", 15, "bold"),
    text_color=TEXT
).pack(anchor="w", pady=(0, 10))

bins_frame = ctk.CTkFrame(
    bins_section,
    fg_color="transparent"
)
bins_frame.pack(fill="x")

bin_widgets = {}

bin_details = [
    ("PAPER", "▤", "#60A5FA"),
    ("PLASTIC", "♻", "#22C55E"),
    ("METAL", "▣", "#FBBF24")
]

for name, icon, color in bin_details:

    box = ctk.CTkFrame(
        bins_frame,
        fg_color=CARD,
        corner_radius=15,
        border_width=2,
        border_color=CARD_LIGHT
    )
    box.pack(
        side="left",
        fill="both",
        expand=True,
        padx=6
    )

    ctk.CTkLabel(
        box,
        text=icon,
        font=("Arial", 27),
        text_color=color
    ).pack(pady=(12, 4))

    ctk.CTkLabel(
        box,
        text=f"{name} BIN",
        font=("Arial", 14, "bold"),
        text_color=TEXT
    ).pack()

    state_label = ctk.CTkLabel(
        box,
        text="● CLOSED",
        font=("Arial", 11),
        text_color=MUTED
    )
    state_label.pack(pady=(5, 12))

    bin_widgets[name] = {
        "frame": box,
        "state": state_label
    }


# ==========================================
# DEVELOPER CREDIT
# ==========================================

credit_card = ctk.CTkFrame(
    main,
    fg_color=CARD,
    corner_radius=14,
    border_width=1,
    border_color=CARD_LIGHT
)
credit_card.pack(fill="x", pady=(8, 0))

credit_accent = ctk.CTkFrame(
    credit_card,
    height=3,
    fg_color=GREEN,
    corner_radius=0
)
credit_accent.pack(fill="x")

ctk.CTkLabel(
    credit_card,
    text="CREATED & DEVELOPED BY",
    font=("Arial", 10, "bold"),
    text_color=MUTED
).pack(pady=(12, 3))

ctk.CTkLabel(
    credit_card,
    text="Zain Yaser Alnajjar",
    font=("Arial", 19, "bold"),
    text_color=GREEN
).pack()

ctk.CTkLabel(
    credit_card,
    text="ZAIN SMARTSORT  •  SCIENCE & TECHNOLOGY PROJECT",
    font=("Arial", 10),
    text_color=MUTED
).pack(pady=(4, 12))


# ==========================================
# CAMERA SETUP
# ==========================================

camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not camera.isOpened():
    camera = cv2.VideoCapture(0)

if not camera.isOpened():
    system_badge.configure(
        text="● CAMERA ERROR",
        text_color=RED
    )


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def set_status(text, color=GREEN):
    status_label.configure(
        text=f"● {text}",
        text_color=color
    )


def reset_bins():

    for widgets in bin_widgets.values():

        widgets["frame"].configure(
            border_color=CARD_LIGHT
        )

        widgets["state"].configure(
            text="● CLOSED",
            text_color=MUTED
        )


def reset_result():

    material_label.configure(
        text="—",
        text_color=TEXT
    )

    destination_label.configure(
        text="Waiting for scan",
        text_color=GREEN
    )

    confidence_label.configure(text="—")
    confidence_bar.set(0)


# ==========================================
# CAMERA UPDATE
# ==========================================

def update_camera():

    global current_frame

    if not running:
        return

    if camera.isOpened():

        ret, frame = camera.read()

        if ret:

            h, w = frame.shape[:2]

            size = min(w, h) // 2

            x1 = (w - size) // 2
            y1 = (h - size) // 2

            x2 = x1 + size
            y2 = y1 + size

            with frame_lock:
                current_frame = frame[
                    y1:y2,
                    x1:x2
                ].copy()

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (34, 197, 94),
                3
            )

            cv2.putText(
                frame,
                "DETECTION AREA",
                (x1, max(y1 - 12, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (34, 197, 94),
                2
            )

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            image = Image.fromarray(rgb)
            image = image.resize((580, 350))

            photo = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(580, 350)
            )

            camera_label.configure(
                image=photo,
                text=""
            )

            camera_label.image = photo

    app.after(40, update_camera)


# ==========================================
# BACKGROUND DETECTION
# ==========================================

def prepare_background(frame):

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.GaussianBlur(
        gray,
        (11, 11),
        0
    )

    return gray


def save_background(event=None):

    global background_frame

    if scanning or bin_open:
        return

    with frame_lock:
        if current_frame is None:
            return

        frame = current_frame.copy()

    background_frame = prepare_background(frame)

    reset_result()
    reset_bins()

    set_status(
        "EMPTY BACKGROUND SAVED",
        GREEN
    )

    destination_label.configure(
        text="Ready to scan"
    )

    print("[SYSTEM] Empty background saved.")


def object_detected(frame):

    if background_frame is None:
        return False

    current = prepare_background(frame)

    difference = cv2.absdiff(
        background_frame,
        current
    )

    _, threshold = cv2.threshold(
        difference,
        PIXEL_DIFFERENCE,
        255,
        cv2.THRESH_BINARY
    )

    changed_pixels = cv2.countNonZero(
        threshold
    )

    total_pixels = threshold.size

    change_ratio = changed_pixels / total_pixels

    print(
        f"[DETECTION] Changed area: "
        f"{change_ratio * 100:.1f}%"
    )

    return change_ratio >= OBJECT_THRESHOLD


# ==========================================
# LOAD AI MODEL
# ==========================================

def load_model():

    global classifier

    try:

        print("[AI] Loading model...")

        model = pipeline(
            "image-classification",
            model=MODEL_NAME,
            device=-1
        )

        classifier = model

        ui_events.put(("model_ready", None))

    except Exception as error:

        print("[AI ERROR]", error)

        ui_events.put(("model_error", None))


def model_ready():

    if not running:
        return

    system_badge.configure(
        text="● AI SYSTEM ONLINE",
        text_color=GREEN
    )

    if background_frame is None:
        set_status(
            "PRESS B TO SET BACKGROUND",
            YELLOW
        )
    else:
        set_status("READY TO SORT")


def model_error():

    if not running:
        return

    system_badge.configure(
        text="● AI MODEL ERROR",
        text_color=RED
    )

    set_status(
        "MODEL UNAVAILABLE",
        RED
    )


# ==========================================
# ARDUINO SERIAL COMMUNICATION
# ==========================================

def arduino_worker():
    """Read/write COM4 without blocking the camera or Tkinter window."""
    global running
    connected = False

    while running:
        try:
            print(f"[ARDUINO] Connecting to {SERIAL_PORT}...")
            with serial.Serial(
                SERIAL_PORT,
                SERIAL_BAUD,
                timeout=0.25,
                write_timeout=1
            ) as board:
                # Opening the serial port resets most Arduino UNO boards.
                # Wait for the READY line emitted by Arduino setup().
                deadline = time.monotonic() + 8
                while running and time.monotonic() < deadline:
                    line = board.readline().decode("utf-8", errors="replace").strip()
                    if line == "READY":
                        break
                else:
                    raise RuntimeError("No READY response from Arduino")

                if not running:
                    break

                connected = True
                arduino_events.put(("connected", None))
                print("[ARDUINO] Connected and ready")

                while running:
                    try:
                        command = arduino_commands.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    print(f"[ARDUINO] Sending {command}")
                    board.write((command + "\n").encode("ascii"))
                    board.flush()

                    # One command at a time. Do not permit the next scan
                    # until the physical Arduino reports DONE.
                    deadline = time.monotonic() + 10
                    completed = False
                    while running and time.monotonic() < deadline:
                        response = board.readline().decode("utf-8", errors="replace").strip()
                        if response == "BUSY":
                            arduino_events.put(("busy", command))
                        elif response == "DONE":
                            completed = True
                            arduino_events.put(("done", command))
                            break

                    if not completed and running:
                        raise RuntimeError(f"Timed out waiting for DONE ({command})")

        except (serial.SerialException, OSError, RuntimeError) as error:
            if running:
                print(f"[ARDUINO ERROR] {error}")
                if connected:
                    arduino_events.put(("failed", str(error)))
                else:
                    arduino_events.put(("disconnected", str(error)))
        finally:
            connected = False
            # Never deliver an old sorting command after a reconnect.
            while True:
                try:
                    arduino_commands.get_nowait()
                except queue.Empty:
                    break

        # Reconnect in the background if the cable is absent/unplugged.
        if running:
            time.sleep(2)


def process_arduino_events():
    """Update Tkinter widgets on the GUI thread only."""
    global arduino_ready, bin_open

    if not running:
        return

    try:
        while True:
            event, value = arduino_events.get_nowait()

            if event == "connected":
                arduino_ready = True
                arduino_badge.configure(text="● ARDUINO CONNECTED", text_color=GREEN)

            elif event == "busy":
                reset_bins()
                bin_widgets[value]["frame"].configure(border_color=BIN_COLORS[value])
                bin_widgets[value]["state"].configure(
                    text="● OPEN", text_color=BIN_COLORS[value]
                )
                set_status("SORTING IN PROGRESS", GREEN)

            elif event == "done":
                reset_bins()
                bin_open = False
                set_status("READY TO SORT", GREEN)
                print(f"[ARDUINO] {value} bin closed")

            elif event in ("failed", "disconnected"):
                arduino_ready = False
                bin_open = False
                reset_bins()
                arduino_badge.configure(text="● ARDUINO NOT CONNECTED", text_color=RED)
                if event == "failed":
                    set_status("ARDUINO CONNECTION ERROR", RED)

    except queue.Empty:
        pass

    app.after(100, process_arduino_events)


def open_bin(name):
    """Queue a physical servo command; never pretend a bin has opened."""
    global bin_open

    if not arduino_ready:
        set_status("CLASSIFIED - ARDUINO NOT CONNECTED", RED)
        print(f"[OFFLINE] Classified as {name}; no physical bin moved")
        return

    if bin_open:
        return

    bin_open = True
    set_status("SENDING TO ARDUINO...", YELLOW)
    try:
        arduino_commands.put_nowait(name)
    except queue.Full:
        bin_open = False
        set_status("ARDUINO BUSY", YELLOW)


# ==========================================
# AI CLASSIFICATION
# ==========================================

def classify_image(image):

    try:

        predictions = classifier(
            image,
            top_k=6
        )

        scores = {
            item["label"].lower(): item["score"]
            for item in predictions
        }

        paper_score = (
            scores.get("paper", 0)
            + scores.get("cardboard", 0)
        )

        bin_scores = {
            "PAPER": paper_score,
            "PLASTIC": scores.get("plastic", 0),
            "METAL": scores.get("metal", 0)
        }

        best_bin = max(
            bin_scores,
            key=bin_scores.get
        )

        best_score = bin_scores[best_bin]

        unsupported = max(
            scores.get("glass", 0),
            scores.get("trash", 0)
        )

        if unsupported > best_score:
            result = "UNSUPPORTED"
            score = unsupported

        elif best_score < MIN_CONFIDENCE:
            result = "UNCERTAIN"
            score = best_score

        else:
            result = best_bin
            score = best_score

        ui_events.put(("scan_result", (result, score)))

    except Exception as error:

        print("[SCAN ERROR]", error)

        ui_events.put(("scan_error", None))


def show_result(result, score):

    global scanning

    if not running:
        return

    scanning = False

    confidence_label.configure(
        text=f"{score * 100:.1f}%"
    )

    confidence_bar.set(
        min(score, 1.0)
    )

    if result in bin_widgets:

        material_label.configure(
            text=result,
            text_color=BIN_COLORS[result]
        )

        destination_label.configure(
            text=f"{result} BIN",
            text_color=BIN_COLORS[result]
        )

        open_bin(result)

    else:

        material_label.configure(
            text=result,
            text_color=RED
        )

        destination_label.configure(
            text="NO BIN SELECTED",
            text_color=RED
        )

        set_status(
            "PLEASE TRY AGAIN",
            RED
        )


def scan_error():

    global scanning

    if not running:
        return

    scanning = False

    set_status(
        "SCAN FAILED",
        RED
    )


# ==========================================
# SCAN USING SPACE
# ==========================================

def scan_waste(event=None):

    global scanning

    if scanning or bin_open:
        return

    if classifier is None:
        set_status(
            "AI MODEL STILL LOADING",
            YELLOW
        )
        return

    if background_frame is None:
        set_status(
            "PRESS B TO SET BACKGROUND",
            YELLOW
        )
        return

    with frame_lock:
        if current_frame is None:
            return

        frame = current_frame.copy()

    # Check if an object is present
    if not object_detected(frame):

        reset_result()
        reset_bins()

        material_label.configure(
            text="EMPTY",
            text_color=YELLOW
        )

        destination_label.configure(
            text="NO OBJECT DETECTED",
            text_color=YELLOW
        )

        set_status(
            "WAITING FOR OBJECT",
            YELLOW
        )

        print("[SYSTEM] No object detected.")
        return

    scanning = True

    reset_bins()

    set_status(
        "ANALYZING...",
        YELLOW
    )

    material_label.configure(
        text="SCANNING",
        text_color=TEXT
    )

    destination_label.configure(
        text="Identifying material...",
        text_color=TEXT
    )

    confidence_label.configure(text="—")
    confidence_bar.set(0)

    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    image = Image.fromarray(rgb)

    threading.Thread(
        target=classify_image,
        args=(image,),
        daemon=True
    ).start()


# ==========================================
# KEYBOARD CONTROLS
# ==========================================

app.bind("<space>", scan_waste)
app.bind("<b>", save_background)
app.bind("<B>", save_background)


# ==========================================
# CLOSE APPLICATION
# ==========================================

def close_app():

    global running

    running = False

    if camera.isOpened():
        camera.release()

    app.destroy()


app.protocol(
    "WM_DELETE_WINDOW",
    close_app
)

app.bind(
    "<Escape>",
    lambda event: close_app()
)


# ==========================================
# THREAD-SAFE AI UI EVENTS
# ==========================================

def process_ui_events():
    """Only the Tkinter main thread touches the interface."""
    if not running:
        return

    try:
        while True:
            event, value = ui_events.get_nowait()
            if event == "model_ready":
                model_ready()
            elif event == "model_error":
                model_error()
            elif event == "scan_result":
                show_result(*value)
            elif event == "scan_error":
                scan_error()
    except queue.Empty:
        pass

    app.after(100, process_ui_events)


# ==========================================
# START SYSTEM
# ==========================================

threading.Thread(
    target=arduino_worker,
    daemon=True
).start()

process_arduino_events()
process_ui_events()

threading.Thread(
    target=load_model,
    daemon=True
).start()

update_camera()

app.mainloop()
