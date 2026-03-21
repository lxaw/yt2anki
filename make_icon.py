"""Generate a simple app icon (play button on red/blue gradient)."""
from PIL import Image, ImageDraw

def make_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded red square (YouTube-ish)
    margin = 40
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=60, fill="#CC0000"
    )

    # White play triangle
    cx, cy = size // 2, size // 2
    tri_size = 100
    play = [
        (cx - tri_size // 2 + 15, cy - tri_size),
        (cx - tri_size // 2 + 15, cy + tri_size),
        (cx + tri_size + 15, cy),
    ]
    draw.polygon(play, fill="#FFFFFF")

    # Small card/flash icon in bottom-right
    card_x, card_y = size - margin - 120, size - margin - 100
    draw.rounded_rectangle(
        [card_x, card_y, card_x + 90, card_y + 65],
        radius=8, fill="#4A90D9"
    )
    draw.rounded_rectangle(
        [card_x + 10, card_y + 10, card_x + 80, card_y + 55],
        radius=4, fill="#FFFFFF"
    )

    # Save as PNG
    img.save("icon.png")

    # Save as ICNS for macOS
    icon_sizes = [16, 32, 64, 128, 256, 512]
    imgs = []
    for s in icon_sizes:
        imgs.append(img.resize((s, s), Image.LANCZOS))
    imgs[0].save("icon.icns", format="ICNS", append_images=imgs[1:])

    print("Created icon.png and icon.icns")

if __name__ == "__main__":
    make_icon()
