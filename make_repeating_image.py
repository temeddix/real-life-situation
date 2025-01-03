import math
import os

import cv2
import numpy as np

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

chunk = np.array(
    [
        [
            [255, 255, 255],
            [255, 0, 0],
            [0, 0, 255],
            [255, 255, 255],
            [0, 0, 0],
            [0, 255, 255],
            [255, 255, 0],
            [0, 0, 0],
        ]
    ],
    dtype=np.float32,
)

vertical_repeat = math.ceil(IMAGE_HEIGHT / chunk.shape[0])
horizontal_repeat = math.ceil(IMAGE_WIDTH / chunk.shape[1])
big_repeated_image = np.tile(chunk, reps=(vertical_repeat, horizontal_repeat, 1))  # type: ignore
color_converted_image = cv2.cvtColor(big_repeated_image, cv2.COLOR_RGB2BGR)
cut_image = color_converted_image[:IMAGE_HEIGHT, :IMAGE_WIDTH]

os.makedirs("./basket", exist_ok=True)
cv2.imwrite("./basket/repeating_image.png", cut_image)
