from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# ASCII characters for edges and shading
EDGE_CHARS = { "vertical": "|", "horizontal": "_", "diagonal1": "\\", "diagonal2": "/" }

# brightness ■(least)  --> .(brightest)
#ASCII_CHARS = ["■", "@", "?", "O", "P", "o", "c", ";", "."]

# brightness .(least)  --> ■ (brightest)
ASCII_CHARS = [".", ";", "c", "o", "P", "O", "?", "@", "■"]

def enhance_image(image):
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(1.5)

def resize_image(image, new_width=200):
    width, height = image.size
    ratio = height / width / 2.2  
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))

def grayify(image):
    return image.convert("L")

def detect_edges(image):
    """Apply edge detection and return an array of edge strengths."""
    edges = image.filter(ImageFilter.FIND_EDGES)
    return np.array(edges, dtype=np.int16)  # Convert to int16 to prevent overflow

def classify_edges(edge_array):
    """Classifies edges into horizontal, vertical, or diagonal using Sobel-like filtering."""
    height, width = edge_array.shape
    ascii_representation = []

    for y in range(1, height - 1):
        row = []
        for x in range(1, width - 1):
            gx = int(edge_array[y, x+1]) - int(edge_array[y, x-1])  # Horizontal change
            gy = int(edge_array[y+1, x]) - int(edge_array[y-1, x])  # Vertical change

            # Determine edge direction
            if abs(gx) > abs(gy):  # Horizontal
                row.append(EDGE_CHARS["horizontal"])
            elif abs(gy) > abs(gx):  # Vertical
                row.append(EDGE_CHARS["vertical"])
            elif gx > 0 and gy > 0:  # Diagonal ↘
                row.append(EDGE_CHARS["diagonal1"])
            else:  # Diagonal ↙
                row.append(EDGE_CHARS["diagonal2"])
        ascii_representation.append(row)
    
    return ascii_representation  # Return a list of lists (not a string!)

def pixels_to_ascii(image, edges):
    pixels = np.array(image, dtype=np.int16)  # Convert to int16 to prevent overflow
    ascii_image = classify_edges(edges)  

    final_ascii = []
    for y in range(image.height - 2):  
        row = ""
        for x in range(image.width - 2):
            if edges[y, x] > 100:  
                row += ascii_image[y][x]  
            else:
                row += ASCII_CHARS[int(pixels[y, x]) * len(ASCII_CHARS) // 256]  # Fix applied here
        final_ascii.append(row)

    return "\n".join(final_ascii)


def main(new_width=200):
    path = input("Enter a valid pathname to an image:\n")
    try:
        image = Image.open(path)
    except:
        print(path, " is not a valid pathname to an image.")
        return

    image = enhance_image(image)
    image = grayify(resize_image(image))
    edges = detect_edges(image)
    ascii_data = pixels_to_ascii(image, edges)

    # Save to plain text
    with open("ascii_edges.txt", "w", encoding="utf-8") as f:
        f.write(ascii_data)

    # Save to HTML file
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ASCII Edge Art</title>
    <style>
        body {{
            background-color: black;
            color: #fcf0d3;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre;
            font-size: 6px;
            padding: 20px;
        }}
    </style>
</head>
<body>
<pre>{ascii_data}</pre>
</body>
</html>"""

    with open("ascii_edges.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("\n✅ ASCII edge image saved to 'ascii_edges.txt' and 'ascii_edges.html'.")
    print("📂 Open 'ascii_edges.html' in a browser to view the ASCII art.")

main()
