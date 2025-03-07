bl_info = {
    "name": "Quake II/Anachronox BSP Importer",
    "author": "GeneralProtectionFault",
    "version": (0,0,1),
    "blender": (4,4,0),
    "location": "File > Import > Quake II/Anachronox (.BSP)",
    "warning": "",
    # "github_url": "https://github.com/GeneralProtectionFault/blender-anachronox-md2-importer",
    "doc_url": ""
}


from bpy_extras.io_utils import ImportHelper
from bpy.props import BoolProperty, StringProperty
import bpy

from .idtech2_bsp import load_idtech2_bsp


class ImportBSP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_idtech2.bsp"
    bl_label = "Import idtech 2 BSP"

    filter_glob: StringProperty(
        default="*.bsp", # only shows bsp files in opening screen
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    
    def execute(self, context):
        try:
            return load_idtech2_bsp(self.filepath)
        except Exception as argument:
            self.report({'ERROR'}, str(argument))


def menu_func_import(self, context):
    self.layout.operator(ImportBSP.bl_idname, text="Quake II/Anachronox BSP Import (.bsp)")


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