from typing import List
from dataclasses import dataclass, fields
import struct
import numpy as np
from PIL import Image


# This is nothing more than a list of 256 colors, 3 numbers (RGB) for each
# We convert it to an array, so the index corresponds to each group of 3
# The .wal file pixel data is simply an index to this matrix to get the fixed color
quake2_palette = np.array([0, 15, 31, 47, 63, 75, 91, 107, 123, 139,
155, 171, 187, 203, 219, 235, 99, 91, 83, 79, 71,
63, 59, 51, 47, 43, 39, 35, 27, 23, 19, 15, 95, 91,
91, 87, 83, 79, 71, 63, 59, 51, 47, 39, 35, 27, 23,
19, 143, 123, 115, 103, 207, 167, 139, 111, 235, 203,
175, 147, 119, 91, 63, 35, 167, 159, 151, 139, 127,
115, 103, 87, 75, 67, 59, 51, 43, 35, 27, 19, 123,
115, 107, 103, 95, 87, 83, 75, 67, 63, 55, 47, 39,
31, 23, 15, 111, 95, 83, 67, 55, 39, 27, 15, 179,
191, 203, 215, 203, 179, 159, 135, 115, 91, 71, 47,
23, 19, 15, 11, 7, 7, 7, 0, 0, 0, 0, 0, 139, 131,
123, 115, 107, 99, 91, 87, 75, 63, 51, 43, 31, 19,
11, 0, 151, 143, 135, 127, 119, 115, 107, 99, 91,
79, 67, 55, 47, 35, 23, 15, 159, 147, 139, 127, 119,
107, 99, 87, 79, 67, 55, 43, 31, 23, 11, 0, 119,
111, 103, 99, 91, 83, 75, 71, 63, 55, 47, 39, 35,
27, 19, 11, 155, 143, 135, 123, 115, 103, 95, 87,
75, 63, 55, 47, 35, 27, 19, 11, 0, 35, 63, 83, 95,
95, 95, 255, 255, 255, 255, 255, 255, 255, 255, 255,
255, 255, 239, 227, 211, 199, 183, 171, 155, 143, 127,
115, 95, 71, 47, 27, 239, 55, 255, 0, 43, 27, 19,
235, 195, 159, 123, 235, 199, 167, 135, 159, 0, 15,
31, 47, 63, 75, 91, 107, 123, 139, 155, 171, 187,
203, 219, 235, 75, 67, 63, 59, 55, 47, 43, 39, 35,
31, 27, 23, 19, 15, 15, 11, 95, 91, 83, 79, 75, 71,
63, 59, 55, 47, 43, 39, 35, 27, 23, 19, 119, 99,
91, 79, 151, 123, 103, 83, 159, 139, 119, 99, 79,
59, 39, 23, 59, 47, 43, 39, 31, 23, 23, 19, 15, 15,
15, 11, 11, 11, 7, 7, 95, 87, 83, 79, 71, 67, 63,
55, 51, 47, 39, 35, 27, 23, 15, 11, 59, 55, 47, 43,
35, 27, 19, 11, 91, 123, 155, 187, 215, 199, 183,
167, 151, 135, 119, 103, 83, 75, 67, 63, 55, 47, 39,
31, 23, 15, 7, 0, 87, 79, 71, 67, 59, 51, 47, 43,
35, 31, 27, 19, 15, 11, 7, 0, 159, 151, 139, 131,
123, 115, 107, 99, 91, 79, 67, 55, 47, 35, 23, 15,
75, 67, 59, 55, 47, 43, 35, 31, 27, 23, 19, 15, 11,
7, 0, 0, 123, 115, 107, 99, 91, 87, 79, 71, 63, 55,
47, 39, 31, 23, 15, 7, 171, 159, 151, 139, 131, 119,
111, 103, 91, 79, 67, 59, 47, 35, 23, 15, 255, 231,
211, 187, 167, 143, 123, 255, 255, 255, 255, 255, 255,
235, 215, 191, 171, 147, 127, 107, 87, 71, 59, 43,
31, 23, 15, 7, 0, 0, 0, 0, 0, 55, 0, 0, 43, 27,
19, 151, 115, 87, 63, 211, 171, 139, 107, 91, 0, 15,
31, 47, 63, 75, 91, 107, 123, 139, 155, 171, 187,
203, 219, 235, 35, 31, 31, 27, 27, 23, 23, 19, 19,
19, 15, 15, 11, 11, 7, 7, 111, 103, 95, 91, 83, 75,
67, 59, 55, 47, 43, 39, 35, 27, 23, 19, 83, 67, 59,
47, 75, 59, 47, 39, 39, 35, 31, 27, 23, 15, 11, 7,
43, 35, 27, 19, 15, 11, 7, 0, 0, 0, 0, 0, 0, 0,
0, 0, 75, 67, 63, 59, 55, 51, 47, 43, 39, 35, 27,
23, 19, 15, 11, 7, 23, 23, 23, 23, 19, 15, 11, 7,
79, 111, 147, 183, 223, 211, 195, 183, 167, 155, 139,
127, 111, 103, 91, 83, 75, 63, 51, 43, 31, 19, 11,
0, 87, 79, 71, 67, 59, 51, 47, 43, 35, 31, 27, 19,
15, 11, 7, 0, 123, 115, 107, 99, 95, 87, 79, 71,
67, 59, 51, 43, 35, 27, 19, 11, 63, 55, 47, 39, 35,
27, 23, 19, 15, 11, 11, 7, 7, 0, 0, 0, 207, 195,
183, 167, 155, 143, 127, 115, 103, 87, 75, 63, 47,
35, 23, 7, 123, 111, 99, 87, 75, 67, 59, 51, 39,
27, 19, 11, 7, 0, 0, 0, 0, 15, 27, 39, 47, 51, 51,
255, 211, 167, 127, 83, 39, 31, 23, 15, 7, 0, 0,
0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255,
0, 255, 35, 23, 15, 127, 83, 51, 27, 199, 155, 119,
87, 83]).reshape((256,3))


@dataclass
class wal_image(object):
    texture_name: str
    width: int
    height: int
    mip_level_offsets: List[int]
    anim_name: str
    flags: int
    contents: int
    value: int

    mipmap_level0_size: int
    mipmap_level1_size: int
    mipmap_level2_size: int
    mipmap_level3_size: int

    image: Image    # PIL Image

    def __init__(self, file_path):
        super().__init__()

        with open(file_path, 'rb') as f:
            # file_bytes = f.read()
            f.seek(0)
            self.texture_name = f.read(32).decode("ascii", "ignore").rstrip("\x00")
            self.width = struct.unpack("<I", f.read(4))[0]
            self.height = struct.unpack("<I", f.read(4))[0]
            self.mip_level_offsets = struct.unpack("<IIII", f.read(16))
            self.anim_name = f.read(32).decode("ascii", "ignore").rstrip("\x00")        # Next image if animated
            self.flags = struct.unpack("<i", f.read(4))[0]
            self.contents = struct.unpack("<i", f.read(4))[0]
            self.value = struct.unpack("<i", f.read(4))[0]

            self.mipmap_level0_size = self.width * self.height
            self.mipmap_level1_size = self.mip_level_offsets[2] - self.mip_level_offsets[1]
            self.mipmap_level2_size = self.mip_level_offsets[3] - self.mip_level_offsets[2]

            f.seek(0,2) # Move to end of file
            self.eof_offset = f.tell()

            self.mipmap_level3_size = self.eof_offset - self.mip_level_offsets[3]

            f.seek(self.mip_level_offsets[0])
            self.raw_data = list(f.read(self.mipmap_level0_size))

            self.pixel_cmap_indices = np.array(self.raw_data).reshape(self.height, self.width)
            self.image_rgb = quake2_palette[self.pixel_cmap_indices]

            self.image = Image.fromarray(np.uint8(self.image_rgb), 'RGB')


if __name__ == "__main__":
    # TEST CASE #
    wal_path = '/home/q/Documents/test/textures/e3u2/sflr1_1.wal'
    wal_object = wal_image(wal_path)

    print("--------------- .WAL HEADER VALUES -------------------")
    for field in fields(wal_object):
        print(f"{field.name} - ", getattr(wal_object, field.name))

    print("------------------------------------------------------")

    wal_object.image.show()


