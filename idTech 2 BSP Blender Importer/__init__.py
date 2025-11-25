from bpy_extras.io_utils import ImportHelper
from bpy.props import BoolProperty, StringProperty, IntProperty
import bpy
import os
import sys
import platform
import stat

from .idtech2_bsp import load_idtech2_bsp


def draw_hr(layout, height=0.05, px=3):
    box = layout.box()
    row = box.row()
    row.scale_y = max(height, px * height)  # scale fallback for small px
    row.alignment = 'EXPAND'
    row.label(text="")


class ImportBSP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_idtech2.bsp"
    bl_label = "Import idtech 2 BSP"

    filter_glob: StringProperty(
        default="*.bsp", # only shows bsp files in opening screen
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def draw(self, context):
        layout = self.layout
        layout.separator()

        layout.prop(self, "model_scale", text="Model Scale")
        layout.prop(self, "apply_transforms", text="Apply Transforms")

        draw_hr(layout)

        layout.prop(self, "apply_lightmaps")
        layout.prop(self, "lightmap_influence", text="Lightmap Influence (%)")

        draw_hr(layout)

        layout.label(text="(Quake II) Search parent folders for textures")
        layout.prop(self, "search_from_parent", text="Parent Levels")

        draw_hr(layout)

        layout.label(text="Create Empties to show BSP Entities")
        layout.prop(self, "show_entities", text="Show Entities")



    model_scale: bpy.props.FloatProperty(name="New Model Scale",
                                    description='Desired scale for the model.\nDefault is 1%, as idTech 2 did not consider vertex coordinates "meters" :)',
                                    precision=4, default=.0254)

    apply_transforms: BoolProperty(name="Apply transforms",
                                        description="Applies the previous transforms.",
                                        default=True)

    search_from_parent: IntProperty(name="Search for textures from parent folder",
                                        description="""In a typical Quake game folder, a .BSP file may refer to textures in a textures folder not within itself.
                                        In this case, all files under the PARENT folder from the .BSP will be searched.""",
                                        min=0, max=2, default=0)

    apply_lightmaps: BoolProperty(name="Apply Lightmaps", default=False)

    lightmap_influence: IntProperty(name="Lightmap Influence", description="""Depending on the game and the lighting, the lightmaps can sometimes make a map very
                                        dark.  If so, this allows controlling the influence of the lightmaps.  The materials have a "Lightmap Influence value
                                        node which can be adjusted between 0 and 1 at any time.""",
                                        min=0, max=100, default=100)

    show_entities: BoolProperty(name="Show Entity Info", description="""If an entity has an origin/location, an empty object will be created, along with text 
                                        for the properties""", default=False)

    def execute(self, context):
        try:
            return load_idtech2_bsp(self.filepath, self.model_scale, self.apply_transforms, self.search_from_parent, self.apply_lightmaps, self.lightmap_influence, self.show_entities)
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