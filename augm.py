from PIL import Image, ImageDraw, ImageFilter
import os, random
from os import path
from pathlib import Path

# Our working space is 1280 by 720 pixels
# Cartesian space starting (0,0) on top left corner.
# The size is given by a 2-tuple (w,h).

imageWidth = 1280
imageHeight = 720

sourceFolder = "data/source"
sourceMasksFolder = "data/source masks"

destinationFolder = "data/destination"
destinationMasksFolder = "data/destination masks"

resultsFolder = "data/results"
labelsFolder = "data/labels"

scores = {
    "2x4_wood.png": 43.20,
    "backpack.png": 20.90,
    "log_slice.png": 23.12,
    "rock.png": 24.12,
    "shipping_box.png": 42.56,
    "styrofoam_box.png": 34.12,
    "traffic_cone.png": 13.23,
    "tennis_racquet.png": 34.12,
    "white_soccer_ball.png": 14.12,
    "wood_crate.png": 28.64,
    "wood_log.png": 34.12,
    "wood_pallet.png": 45.32
}

shortNotation = {
    "2x4_wood.png": "2x4",
    "backpack.png": "bp",
    "log_slice.png": "ls",
    "rock.png": "rk",
    "shipping_box.png": "sb",
    "styrofoam_box.png": "sb",
    "traffic_cone.png": "tc",
    "tennis_racquet.png": "tr",
    "white_soccer_ball.png": "wsb",
    "wood_crate.png": "wc",
    "wood_log.png": "wl",
    "wood_pallet.png": "wp"
}

rotations = {
    "wood_pallet.png": [0, 10, -10, 12, -14],
    "2x4_wood.png": [0, 14, 233],
    "light_green_soccer_ball.png": [90,-90],
    "shipping_box.png": 42.56,
    "traffic_cone.png": 13.23,
    "shipping_box_set.png": 55.18,
    "wood_crate.png": 28.64
}


# Crop boundary (transparent channel)
def cropAlpha(img):
    if (img.mode != "RGBA"):
        return img
    alpha = img.getchannel("A")
    return img.crop(alpha.getbbox())

def cropAroundBlack(img):
    # Convert image to RGB if it's not
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Find all pixels that are not black
    non_black_pixels = [(x, y) for x in range(img.width) for y in range(img.height) if img.getpixel((x, y)) != (0, 0, 0)]

    # Get the bounding box of those pixels
    if non_black_pixels:
        min_x = min(x for x, y in non_black_pixels)
        max_x = max(x for x, y in non_black_pixels)
        min_y = min(y for x, y in non_black_pixels)
        max_y = max(y for x, y in non_black_pixels)

        # Crop the image to this bounding box
        return img.crop((min_x, min_y, max_x, max_y))
    else:
        # If all pixels are black, return the original image
        return img


def rotateSource(source, angle):
    img = source.rotate(angle, expand=True)
    img = cropAlpha(img)
    return img

def openSource(filename):
    pathfile = path.join(sourceFolder, filename)
    src = Image.open(pathfile)
    return src


def openDestination(filename):
    filepath = path.join(destinationFolder, filename)
    dst = Image.open(filepath)
    return dst

# Origin point is the bottom middle point.
# Insertion point is the top left corner.

def attemptSourceToDestination(sourceFilename, destinationFilename, labelFilename):

    source = openSource(sourceFilename)
    destination = openDestination(destinationFilename)

    rotation = generateRotation()
    originPoint = pointInRegion(destinationFilename)
    if originPoint==None:
        originPoint = generateOriginPoint()

    sizing = relativeSizeInBackgroundPercent(originPoint[1])

    sizeChange = (sourceRelativeSizeBase(sourceFilename)*sizing)/100

    # Apply transformation on source
    source = transformSource(source, rotation, sizeChange)

    # Determine the final insertion point (after performing transformation)
    insertionPoint = convertOriginToInsertionPoint(originPoint, source)

    final = insertSourceIntodestination(source, insertionPoint, destination)

    validInsert = isValidInsert(sourceFilename, source, rotation, sizeChange, insertionPoint, destinationFilename)

    if validInsert:
        createYoloFile(labelFilename, insertionPoint, source)

    return validInsert, final


def createYoloFile(filename, point, source):
    filename = filenameNoExtension(filename)
    f = open(labelsFolder + "/" + filename + ".txt", "w")
    row = rowYolo(point, source)
    f.write(" ".join([str(i) for i in row]))
    f.close()

def rowYolo(point, source):
    h = source.height
    w = source.width

    x, y = point[0], point[1]

    xCenter = x + int (w/2)
    yCenter = y + int (h/2)

    xCenter, yCenter = normalizeXandY(xCenter, yCenter)

    width = w/imageWidth
    height = h/imageHeight

    row = (0, xCenter, yCenter, width, height)
    return row

def normalizeXandY(w,h):
    width = (w-0)/((imageWidth-1)-0)
    height = (h-0)/((imageHeight-1)-0)
    return width, height


def filenameNoExtension(filename):
    return Path(filename).stem

def insertSourceIntodestination(source, point, destination):
    res = destination.copy()
    res.paste(source, point, source)
    return res

def replaceSuffixToPNG(filename):
    p = Path(filename)
    filename = p.with_suffix(".png")
    return filename

def isValidInsert(sourceFilename, source, rotation, relativeSize, insertPt, destinationFilename):

    sourceMask = getSourceMask(sourceFilename)
    sourceMask = transformSource(sourceMask, rotation, relativeSize)

    sourceMask = cropAroundBlack(sourceMask)

    destinationFilenamePNG = replaceSuffixToPNG(destinationFilename)

    destinationMask = getDestinationMask(destinationFilenamePNG)

    x1,y1 = insertPt[0],insertPt[1]
    x2,y2 = insertPt[0]+sourceMask.width, insertPt[1]+sourceMask.height

    destinationMaskCropped = destinationMask.crop((x1,y1,x2,y2))

    percentInsideRoadRegion = sourceProportionInRegion(sourceMask, destinationMaskCropped)
    print(percentInsideRoadRegion)

    return (percentInsideRoadRegion>=50)

# Cropped destination mask assumed, same size for both masks
def sourceProportionInRegion(sourceMask, destinationMask):
    totalObjectPixels, totalIntersectionPixels = 0, 0

    for y in range(sourceMask.height):
        for x in range(sourceMask.width):

            coord = x,y
            sourcePixel = sourceMask.getpixel(coord)
            dstPixel = destinationMask.getpixel(coord)

            if isObjectPixel(sourcePixel):
                totalObjectPixels +=1

            if isObjectPixel(sourcePixel) and isRoadPixel(dstPixel):
                totalIntersectionPixels +=1

    print("Total Object Pixels: ", totalObjectPixels)
    print("Total Intersection Pixels: ", totalIntersectionPixels)

    return weird_division(totalIntersectionPixels, totalObjectPixels)*100

def weird_division(n, d):
    return n / d if d else 0

def isObjectPixel(pixel):
    if isBlackPixel(pixel):
        return False
    else:
        return True

def getDestinationMask(filename):
    path = os.path.join(destinationMasksFolder,filename) 
    dst = Image.open(path)
    # We use image as RGB
    dst = dst.convert('RGB')
    return dst

def getSourceMask(filename):
    fp = path.join(sourceMasksFolder,filename)
    return Image.open(fp)


def sourceRelativeSizeBase(filename):
    return scores.get(filename)

def convertOriginToInsertionPoint(originPoint, source):
    x = originPoint[0]-int(source.width/2)
    y = originPoint[1]-source.height
    return (x,y)

def transformSource(source, rotation, sizePercent):
    source = rotateSource(source, rotation)
    sourceFin = resizeSource(source, sizePercent)
    return sourceFin

def resizeSource(source, sizePercent):

    newHeight = int (source.height*sizePercent/100) + 1
    newWidth = int(source.width*sizePercent/100) + 1
    return source.resize((newWidth, newHeight))

def generateRotation():
    return random.choice([0,20,-15])
    # return random.randint(0, 360)

def generateOriginPoint():
    x = random.randrange(1280)
    y = random.randrange(720)
    return (x,y)

def relativeSizeInBackgroundPercent(h):
    h1, h2 = 300, 596
    p1, p2 = 5, 100
    p = 100
    if h < h1:
        p = 1
    elif h1 <= h <= h2:
        p = translate(h, h1, h2, p1, p2)
    else:
        p = 100
    return p

def translate(value, leftMin, leftMax, rightMin, rightMax):
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin
    valueScaled = float(value - leftMin) / float(leftSpan)
    return rightMin + (valueScaled * rightSpan)


def pointInRegion(destinationFilename):

    dstMask = getDestinationMask(replaceSuffixToPNG(destinationFilename))
    found = False

    for z in range(50):
        x,y = generateOriginPoint()
        rgb = dstMask.getpixel((x,y))
        
        if(isRoadPixel(rgb)):
            found = True
            break

    print("Attempts to find point in region: ", z)
    if found:
        return (x,y)
    else:
        return None


def isRoadPixel(pixel):
    if isBlackPixel(pixel):
        return False
    else:
        return True

def isBlackPixel(pixel):
    return sum(pixel)==0

def addId(filename, id):
    path = Path(filename)
    path = path.with_name(path.stem + "-" + id + path.suffix)
    return path

def run():

    directory = os.listdir(destinationFolder)

    for source in scores:
        for filename in directory:
            print("Source: ", source)
            name = addId(filename, shortNotation.get(source))
            isValid, imageResult = attemptSourceToDestination(source, filename, name)
            if(isValid):
                print("Name: ", name)
                imageResult.save(os.path.join(resultsFolder,name))

run()

















































