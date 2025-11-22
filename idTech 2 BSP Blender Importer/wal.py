from typing import List
from dataclasses import dataclass, fields
import struct
import numpy as np
from PIL import Image
from pathlib import Path
import io

# quake2_colormap = Path.cwd() / Path('quake2.lmp')     # Testing

ADDON_DIR = Path(__file__).parent
quake2_colormap = ADDON_DIR / "quake2.lmp"


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

        # load palette from quake2.lmp
        if not quake2_colormap.exists():
            raise FileNotFoundError(f"colormap file not found: {quake2_colormap}")
        lmp_bytes = quake2_colormap.read_bytes()
        # quake2 .lmp is expected to be 256 * 3 = 768 bytes (R,G,B per entry)
        if len(lmp_bytes) < 768:
            raise ValueError("quake2.lmp is too small to contain a 256-color palette")
        # take first 768 bytes and reshape into (256,3)
        palette = np.frombuffer(lmp_bytes[:768], dtype=np.uint8).reshape((256, 3))

        with open(file_path, 'rb') as f:
            f.seek(0)
            self.texture_name = f.read(32).decode("ascii", "ignore").rstrip("\x00")
            self.width = struct.unpack("<I", f.read(4))[0]
            self.height = struct.unpack("<I", f.read(4))[0]
            self.mip_level_offsets = struct.unpack("<IIII", f.read(16))
            self.anim_name = f.read(32).decode("ascii", "ignore").rstrip("\x00")
            self.flags = struct.unpack("<i", f.read(4))[0]
            self.contents = struct.unpack("<i", f.read(4))[0]
            self.value = struct.unpack("<i", f.read(4))[0]

            self.mipmap_level0_size = self.width * self.height
            self.mipmap_level1_size = self.mip_level_offsets[2] - self.mip_level_offsets[1]
            self.mipmap_level2_size = self.mip_level_offsets[3] - self.mip_level_offsets[2]

            f.seek(0,2)
            self.eof_offset = f.tell()
            self.mipmap_level3_size = self.eof_offset - self.mip_level_offsets[3]

            f.seek(self.mip_level_offsets[0])
            self.raw_data = list(f.read(self.mipmap_level0_size))

            self.pixel_cmap_indices = np.array(self.raw_data, dtype=np.uint8).reshape(self.height, self.width)
            self.image_rgb = palette[self.pixel_cmap_indices]

            self.image = Image.fromarray(np.uint8(self.image_rgb), 'RGB')


if __name__ == "__main__":
    wal_path = '/home/q/Documents/quake2_test/textures/e1u1/color1_2.wal'
    wal_object = wal_image(wal_path)

    print("--------------- .WAL HEADER VALUES -------------------")
    for field in fields(wal_object):
        print(f"{field.name} - ", getattr(wal_object, field.name))
    print("------------------------------------------------------")
    print(f"Image Mode: {wal_object.image.mode}")

    wal_object.image.show()
    # wal_object.image.save("/home/q/Documents/BlenderCode/idTech 2 BSP Blender Importer/output.png", format="PNG")
