bl_info = {
    "name": "idTech 2 BSP Importer",
    "author": "GeneralProtectionFault",
    "version": (1,2,0),
    "blender": (4,3,0),
    "location": "File > Import > idTech 2 Quake II/Anachronox (.BSP)",
    "warning": "",
    "github_url": "https://github.com/GeneralProtectionFault/idTech-2-BSP-Blender-Importer",
    "category": "Import-Export"
}


from bpy_extras.io_utils import ImportHelper
from bpy.props import BoolProperty, StringProperty
import bpy
import os
import sys
import platform
import subprocess
import stat
from importlib import reload # required when a self-written module is imported that's edited simultaneously


# path to python.exe
if platform.system() == "Linux":
    # Depending on the environment, the binary might be "python" or "python3.11", etc...
    # Stupid...but need to "find" the python binary to avoid a crash...
    python_bin_folder = os.path.join(sys.prefix, 'bin')

    # Search for binary files
    executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    for filename in os.listdir(python_bin_folder):
        full_python_path = os.path.join(python_bin_folder, filename)
        if os.path.isfile(full_python_path):
            st = os.stat(full_python_path)
            mode = st.st_mode
            # If file is an executable and contains the text "python"
            if mode & executable and 'python' in filename:
                # print(filename,oct(mode))
                break

    python_exe = full_python_path
else:
    python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')

try:
    # upgrade pip
    subprocess.call([python_exe, "-m", "ensurepip"])
    
    # This doesn't jive well with Blender's Python environment for whatever reason...
    # subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
except Exception as argument:
    print(f"Issue ensuring/upgrading pip:\n{argument}")



# install required packages
try:
    subprocess.call([python_exe, "-m", "pip", "install", "pillow"])
    # subprocess.call([python_exe, "-m", "pip", "install", "mathutils"])

except ImportError as argument:
    print(f"ERROR: Pillow/PIL failed to install\n{argument}")

from .idtech2_bsp import load_idtech2_bsp


class ImportBSP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_idtech2.bsp"
    bl_label = "Import idtech 2 BSP"

    filter_glob: StringProperty(
        default="*.bsp", # only shows bsp files in opening screen
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    model_scale: bpy.props.FloatProperty(name="New Model Scale",
                                    description='Desired scale for the model.\nDefault is 1%, as idTech 2 did not consider vertex coordinates "meters" :)',
                                    default=.01)
    
    apply_transforms: BoolProperty(name="Apply transforms",
                                        description="Applies the previous transforms.",
                                        default=True)

    search_from_parent: BoolProperty(name="Search for textures from parent folder",
                                        description="""In a typical Quake game folder, a .BSP file may refer to textures in a textures folder not within itself.
                                        In this case, all files under the PARENT folder from the .BSP will be searched.""",
                                        default=False)

    def execute(self, context):
        try:
            return load_idtech2_bsp(self.filepath, self.model_scale, self.apply_transforms, self.search_from_parent)
        except Exception as argument:
            self.report({'ERROR'}, str(argument))


def menu_func_import(self, context):
    self.layout.operator(ImportBSP.bl_idname, text="idTech 2 [Quake II/Anachronox] (.BSP)")


classes = [
    ImportBSP
]

def register():
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
    for cls in classes:
        print(f'Registering: {cls}')
        bpy.utils.register_class(cls)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def missing_file(self, context):
    self.layout.label(text="File does not exist in currently selected directory! Perhaps you didn't select the correct .bsp file?")


if __name__ == "__main__":
    register()
    print("Quake II/Anachronox BSP Importer loaded.")