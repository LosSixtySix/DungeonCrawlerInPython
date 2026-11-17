from PIL import Image, ImageDraw, ImageFont

"""
Makes the game's icon: a white capital C in Forgore.otf on a black rounded square.
Writes icon.png (used by pygame.display.set_icon) and CRUEL.ico (used by CRUEL.spec for the exe).
Run it again after changing anything here:   python makeIcon.py
"""

SIZE = 256          # final icon size in pixels
SCALE = 4           # drawn this many times bigger, then shrunk, so edges are smooth
CORNER = 0.22       # corner radius as a fraction of the size
LETTER = 0.80       # height of the C as a fraction of the size
BACKGROUND = (0, 0, 0, 255)
LETTER_COLOR = (255, 255, 255, 255)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def makeIcon():
    big = SIZE * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * CORNER), fill=BACKGROUND)

    # Find the font size that makes the C's actual ink LETTER of the icon tall, then center the ink
    target = big * LETTER
    font = ImageFont.truetype("Forgore.otf", 100)
    left, top, right, bottom = draw.textbbox((0, 0), "C", font=font)
    font = ImageFont.truetype("Forgore.otf", int(100 * target / (bottom - top)))
    left, top, right, bottom = draw.textbbox((0, 0), "C", font=font)
    x = (big - (right - left)) / 2 - left
    y = (big - (bottom - top)) / 2 - top
    draw.text((x, y), "C", font=font, fill=LETTER_COLOR)

    icon = image.resize((SIZE, SIZE), Image.LANCZOS)
    icon.save("icon.png")
    icon.save("CRUEL.ico", sizes=ICO_SIZES)


if __name__ == "__main__":
    makeIcon()
