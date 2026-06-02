#!/usr/bin/env python3
"""
AsciIt - an interactive terminal utility that turns images and your webcam
into ASCII art. Combines a static image-to-ASCII converter with a live
webcam ASCII shader, all in one polished TUI.
"""

import os
import sys
import time
import shutil

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from pyfiglet import Figlet
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm
from rich.live import Live
from rich.align import Align
from rich.rule import Rule

console = Console()

# ----------------------------------------------------------------------------
# Core ASCII engine (shared by every mode)
# ----------------------------------------------------------------------------

EDGE_CHARS = {"vertical": "|", "horizontal": "_", "diagonal1": "\\", "diagonal2": "/"}

# Dark -> bright ramps the user can pick from.
RAMPS = {
    "blocks": [".", ";", "c", "o", "P", "O", "?", "@", "■"],
    "classic": list(" .:-=+*#%@"),
    "dense": list(" .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"),
    "minimal": list(" .oO@"),
}


def enhance_image(image, contrast=1.5):
    return ImageEnhance.Contrast(image).enhance(contrast)


def resize_image(image, new_width=120):
    width, height = image.size
    ratio = height / width / 2.2
    new_height = max(1, int(new_width * ratio))
    return image.resize((new_width, new_height))


def grayify(image):
    return image.convert("L")


def detect_edges(image):
    edges = image.filter(ImageFilter.FIND_EDGES)
    return np.array(edges, dtype=np.int16)


def classify_edges(edge_array):
    height, width = edge_array.shape
    rows = []
    for y in range(1, height - 1):
        row = []
        for x in range(1, width - 1):
            gx = int(edge_array[y, x + 1]) - int(edge_array[y, x - 1])
            gy = int(edge_array[y + 1, x]) - int(edge_array[y - 1, x])
            if abs(gx) > abs(gy):
                row.append(EDGE_CHARS["horizontal"])
            elif abs(gy) > abs(gx):
                row.append(EDGE_CHARS["vertical"])
            elif gx > 0 and gy > 0:
                row.append(EDGE_CHARS["diagonal1"])
            else:
                row.append(EDGE_CHARS["diagonal2"])
        rows.append(row)
    return rows


def pixels_to_ascii(image, edges, ramp, edge_threshold=100, use_edges=True):
    pixels = np.array(image, dtype=np.int16)
    edge_map = classify_edges(edges) if use_edges else None
    n = len(ramp)
    lines = []
    for y in range(image.height - 2):
        row = []
        for x in range(image.width - 2):
            if use_edges and edges[y, x] > edge_threshold:
                row.append(edge_map[y][x])
            else:
                row.append(ramp[int(pixels[y, x]) * n // 256])
        lines.append("".join(row))
    return "\n".join(lines)


def compute_ascii_grid(rgb_image, settings):
    """Return a list of rows; each row is a list of (char, (r, g, b)) tuples."""
    enhanced = enhance_image(rgb_image, settings["contrast"])
    target = settings.get("target_size")
    if target is not None:
        color = enhanced.resize(target)
    else:
        color = resize_image(enhanced, settings["width"])
    gray = grayify(color)
    edges = detect_edges(gray)

    color_arr = np.array(color, dtype=np.uint8)
    pixels = np.array(gray, dtype=np.int16)
    edge_map = classify_edges(edges) if settings["use_edges"] else None
    ramp = RAMPS[settings["ramp"]]
    n = len(ramp)
    threshold = settings["edge_threshold"]
    use_edges = settings["use_edges"]

    grid = []
    for y in range(gray.height - 2):
        row = []
        for x in range(gray.width - 2):
            if use_edges and edges[y, x] > threshold:
                ch = edge_map[y][x]
            else:
                ch = ramp[int(pixels[y, x]) * n // 256]
            r, g, b = color_arr[y, x]
            row.append((ch, (int(r), int(g), int(b))))
        grid.append(row)
    return grid


def grid_to_plain(grid):
    return "\n".join("".join(ch for ch, _ in row) for row in grid)


def grid_to_text(grid):
    text = Text()
    for row in grid:
        for ch, (r, g, b) in row:
            text.append(ch, style=f"rgb({r},{g},{b})")
        text.append("\n")
    return text


def grid_to_html_body(grid):
    import html as _html

    lines = []
    for row in grid:
        parts = []
        for ch, (r, g, b) in row:
            parts.append(f'<span style="color:rgb({r},{g},{b})">{_html.escape(ch)}</span>')
        lines.append("".join(parts))
    return "\n".join(lines)


def image_to_ascii(image, settings):
    image = enhance_image(image, settings["contrast"])
    image = grayify(resize_image(image, settings["width"]))
    edges = detect_edges(image)
    return pixels_to_ascii(
        image,
        edges,
        RAMPS[settings["ramp"]],
        settings["edge_threshold"],
        settings["use_edges"],
    )


def image_to_ascii_colored(rgb_image, settings):
    """Like image_to_ascii but returns a rich Text colored with the source pixels."""
    return grid_to_text(compute_ascii_grid(rgb_image, settings))


# ----------------------------------------------------------------------------
# Presentation helpers
# ----------------------------------------------------------------------------

THEME = "#daa520"  # goldenrod, matching the original web UI

SETTINGS = {
    "width": 120,
    "contrast": 1.5,
    "ramp": "blocks",
    "edge_threshold": 100,
    "use_edges": True,
}


def banner():
    fig = Figlet(font="slant")
    art = fig.renderText("AsciIt")
    text = Text(art, style=f"bold {THEME}")
    return Panel(
        Align.center(text),
        border_style=THEME,
        padding=(0, 2),
    )


def clear():
    console.clear()


def settings_summary():
    edges = "on" if SETTINGS["use_edges"] else "off"
    return Text(
        f"width {SETTINGS['width']}  |  ramp {SETTINGS['ramp']}  |  "
        f"contrast {SETTINGS['contrast']}  |  edges {edges}",
        style="dim",
    )


def main_menu():
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style=f"bold {THEME}")
    table.add_column(style="white")
    table.add_row("1", "Convert an image to ASCII")
    table.add_row("2", "Live webcam ASCII shader")
    table.add_row("3", "Settings")
    table.add_row("4", "About")
    table.add_row("q", "Quit")
    return Panel(
        table,
        title="[bold]What would you like to do?[/]",
        border_style=THEME,
        padding=(1, 2),
    )


def render_home():
    clear()
    console.print(banner())
    console.print()
    console.print(Align.center(settings_summary()))
    console.print()
    console.print(main_menu())


# ----------------------------------------------------------------------------
# Mode 1: image -> ascii
# ----------------------------------------------------------------------------


def mode_image():
    clear()
    console.print(Rule(f"[bold {THEME}]Image -> ASCII[/]", style=THEME))
    path = Prompt.ask("[bold]Path to an image[/] (or 'b' to go back)").strip()
    if path.lower() == "b":
        return
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        console.print(f"[red]✗ '{path}' is not a valid file.[/]")
        Prompt.ask("\n[dim]press enter to continue[/]", default="")
        return

    try:
        image = Image.open(path).convert("RGB")
    except Exception as exc:
        console.print(f"[red]✗ Could not open image:[/] {exc}")
        Prompt.ask("\n[dim]press enter to continue[/]", default="")
        return

    orig_w, orig_h = image.size
    console.print(f"[dim]original size: {orig_w} x {orig_h} px[/]")
    scale = FloatPrompt.ask(
        "Scaling factor (smaller = smaller image, e.g. 0.05 = 5%)",
        default=0.05,
    )
    scale = max(0.005, min(scale, 0.5))
    target_w = max(10, int(round(orig_w * scale)))
    target_h = max(10, int(round(orig_h * scale)))

    if Confirm.ask("Adjust width and height manually?", default=False):
        target_w = max(1, IntPrompt.ask("Width (characters)", default=target_w))
        target_h = max(1, IntPrompt.ask("Height (characters)", default=target_h))

    img_settings = dict(SETTINGS, target_size=(target_w, target_h))

    with console.status("[bold]rendering ascii...[/]", spinner="dots"):
        grid = compute_ascii_grid(image, img_settings)

    base = Prompt.ask("Output name (without extension)", default="ascii_art")
    html_path = save_outputs(grid, base)

    if Confirm.ask("View output in browser?", default=True):
        import webbrowser

        webbrowser.open(f"file://{os.path.abspath(html_path)}")
    Prompt.ask("\n[dim]press enter to return to menu[/]", default="")


def save_outputs(grid, base):
    html_path = f"{base}.html"

    html_body = grid_to_html_body(grid)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AsciIt - ASCII Art</title>
    <style>
        body {{
            background-color: black;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre;
            font-size: 6px;
            line-height: 6px;
            padding: 20px;
        }}
    </style>
</head>
<body>
<pre>{html_body}</pre>
</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    console.print(
        Panel(
            f"[green]✓ saved[/]\n  • {html_path}",
            border_style="green",
            padding=(0, 2),
        )
    )
    return html_path


# ----------------------------------------------------------------------------
# Mode 2: live webcam -> ascii (rendered in the terminal)
# ----------------------------------------------------------------------------


def mode_webcam():
    clear()
    console.print(Rule(f"[bold {THEME}]Live Webcam ASCII Shader[/]", style=THEME))

    try:
        import cv2
    except ImportError:
        console.print("[red]✗ opencv-python is not installed.[/]")
        Prompt.ask("\n[dim]press enter to continue[/]", default="")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        console.print("[red]✗ Could not access the webcam (device 0).[/]")
        Prompt.ask("\n[dim]press enter to continue[/]", default="")
        return

    # Fit width to the terminal so it always looks right.
    term_width = shutil.get_terminal_size((100, 30)).columns
    width = min(SETTINGS["width"], max(40, term_width - 2))

    console.print("[dim]press Ctrl+C to stop streaming...[/]\n")
    time.sleep(0.6)

    frames = 0
    start = time.time()
    try:
        with Live(console=console, refresh_per_second=30, screen=True) as live:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame)
                stream_settings = dict(SETTINGS, width=width)
                ascii_data = image_to_ascii(image, stream_settings)

                frames += 1
                fps = frames / (time.time() - start + 1e-9)
                body = Group(
                    Text(ascii_data, style=THEME),
                    Text(f"\n{fps:4.1f} fps   ·   Ctrl+C to stop", style="dim"),
                )
                live.update(Align.center(body))
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()

    console.print("[green]✓ stream stopped.[/]")
    Prompt.ask("\n[dim]press enter to return to menu[/]", default="")


# ----------------------------------------------------------------------------
# Mode 3: settings
# ----------------------------------------------------------------------------


def mode_settings():
    while True:
        clear()
        console.print(Rule(f"[bold {THEME}]Settings[/]", style=THEME))
        table = Table.grid(padding=(0, 2))
        table.add_column(justify="right", style=f"bold {THEME}")
        table.add_column()
        table.add_row("1", f"Width ............ {SETTINGS['width']}")
        table.add_row("2", f"Contrast ......... {SETTINGS['contrast']}")
        table.add_row("3", f"Character ramp ... {SETTINGS['ramp']}  ({''.join(RAMPS[SETTINGS['ramp']][:6])}...)")
        table.add_row("4", f"Edge threshold ... {SETTINGS['edge_threshold']}")
        table.add_row("5", f"Edge detection ... {'on' if SETTINGS['use_edges'] else 'off'}")
        table.add_row("b", "Back")
        console.print(Panel(table, border_style=THEME, padding=(1, 2)))

        choice = Prompt.ask("Edit which setting?", choices=["1", "2", "3", "4", "5", "b"], default="b")
        if choice == "b":
            return
        if choice == "1":
            SETTINGS["width"] = IntPrompt.ask("New width", default=SETTINGS["width"])
        elif choice == "2":
            raw = Prompt.ask("New contrast (e.g. 1.5)", default=str(SETTINGS["contrast"]))
            try:
                SETTINGS["contrast"] = float(raw)
            except ValueError:
                pass
        elif choice == "3":
            SETTINGS["ramp"] = Prompt.ask(
                "Character ramp", choices=list(RAMPS.keys()), default=SETTINGS["ramp"]
            )
        elif choice == "4":
            SETTINGS["edge_threshold"] = IntPrompt.ask(
                "Edge threshold (0-255)", default=SETTINGS["edge_threshold"]
            )
        elif choice == "5":
            SETTINGS["use_edges"] = not SETTINGS["use_edges"]


# ----------------------------------------------------------------------------
# Mode 4: about
# ----------------------------------------------------------------------------


def mode_about():
    clear()
    console.print(banner())
    text = Text.from_markup(
        "[bold]AsciIt[/] turns pictures and live video into ASCII art.\n\n"
        f"[{THEME}]• Image mode[/]  converts any image and exports .txt + .html\n"
        f"[{THEME}]• Webcam mode[/] streams your camera as ASCII, right in the terminal\n"
        f"[{THEME}]• Settings[/]    tune width, contrast, character ramps and edge detection\n\n"
        "[dim]Built with Pillow, NumPy, OpenCV, pyfiglet and rich.[/]"
    )
    console.print(Panel(text, border_style=THEME, padding=(1, 2)))
    Prompt.ask("\n[dim]press enter to return to menu[/]", default="")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------


def main():
    try:
        while True:
            render_home()
            choice = Prompt.ask(
                "[bold]select[/]", choices=["1", "2", "3", "4", "q"], default="1", show_choices=False
            )
            if choice == "1":
                mode_image()
            elif choice == "2":
                mode_webcam()
            elif choice == "3":
                mode_settings()
            elif choice == "4":
                mode_about()
            elif choice == "q":
                clear()
                console.print(
                    Panel(
                        Align.center(Text("Thanks for using AsciIt ✦", style=f"bold {THEME}")),
                        border_style=THEME,
                    )
                )
                break
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]bye![/]")
        sys.exit(0)


if __name__ == "__main__":
    main()
