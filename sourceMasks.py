from PIL import Image, ImageDraw, ImageFilter, ImageChops
import os
from pathlib import Path

obstacleFolder = "data/source"
maskFolder = "data/source masks"

def replaceSuffixToPNG(filename):
    p = Path(filename)
    filename = p.with_suffix(".png")
    return filename

def create_masks():

    for filename in os.listdir(obstacleFolder):

        filepath = os.path.join(obstacleFolder, filename)
        src = Image.open(filepath)

        filepathCheck = os.path.join(maskFolder, filename)

        if(os.path.isfile(filepathCheck)):
            continue

        # Create an empty image with the same size as the original image, filled with white
        mask_image = Image.new('L', src.size, color=0)

        # Iterate over each pixel in the image
        for y in range(src.size[1]):
            for x in range(src.size[0]):
                # Get the RGBA value of the pixel
                r, g, b, a = src.getpixel((x, y))
                # If the alpha channel is greater than 0, it's not transparent
                if a > 0:
                    mask_image.putpixel((x, y), 255)  # Fill the pixel with black
        mask_image.save(os.path.join(maskFolder,filename))

create_masks()










