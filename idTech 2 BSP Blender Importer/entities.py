import bpy
import re
import mathutils
from .custom_types import BSP_OBJECT


_HANDLER_NAME = "entity_viewbillboard_handler"

def _get_active_view_region3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if getattr(space, "region_3d", None):
                        return space.region_3d, area, window
    return None, None, None

def _ensure_handler_registered():
    # avoid duplicate handlers
    for h in bpy.app.handlers.depsgraph_update_post:
        if getattr(h, "__name__", "") == _HANDLER_NAME:
            return
    def _handler(scene, depsgraph):
        # update tracked objects each depsgraph update
        region3d, area, window = _get_active_view_region3d()
        if not region3d:
            return
        # view matrix rows -> camera forward is -Z in view space
        view_matrix = region3d.view_matrix
        view_dir = -mathutils.Vector((view_matrix[2][0], view_matrix[2][1], view_matrix[2][2])).normalized()
        # compute quaternion that points object's -Z toward view_dir with Y up
        quat = view_dir.to_track_quat('-Z', 'Y')
        # apply to all objects that have the custom prop we set
        for obj in [o for o in bpy.data.objects if o.get("billboard_viewport")]:
            # maintain object rotation mode and set
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = quat
    _handler.__name__ = _HANDLER_NAME
    bpy.app.handlers.depsgraph_update_post.append(_handler)


def get_or_create_collection(name):
    # remove existing collection if present
    col = bpy.data.collections.get(name)
    if col:
        bpy.data.collections.remove(col)
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def move_to_collection(obj, target_col):
    # Unlink from every other collection
    for col in list(obj.users_collection):
        if col is not target_col:
            col.objects.unlink(obj)

    # Link to target collection (if not already)
    if obj.name not in target_col.objects:
        target_col.objects.link(obj)



def create_empty(location, text_string, name_empty, name_text, collection, text_size = 0.3, text_extrude = 0.015, text_align = 'CENTER'):
    # Remove existing objects with the same names (optional, avoids duplicates)
    for obj in [bpy.data.objects.get(name_empty), bpy.data.objects.get(name_text)]:
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Create an Empty object
    empty = bpy.data.objects.new(name_empty, None)
    empty.empty_display_type = 'PLAIN_AXES'
    empty.location = location
    empty.show_in_front = True

    bpy.context.collection.objects.link(empty)

    # Create Text object (Font curve)
    font_curve = bpy.data.curves.new(name=name_text + "_Curve", type='FONT')
    font_curve.body = text_string
    font_curve.size = text_size
    font_curve.extrude = text_extrude
    font_curve.align_x = text_align

    text_obj = bpy.data.objects.new(name_text, font_curve)
    text_obj.show_in_front = True
    if hasattr(text_obj.data, "show_in_front"):
        text_obj.data.show_in_front = True

    bpy.context.collection.objects.link(text_obj)

    # Mark this object to be updated by the viewport billboard handler
    text_obj["billboard_viewport"] = True

    # Ensure the handler is registered to update rotation each depsgraph tick
    _ensure_handler_registered()

    # Optionally select and focus on the created objects
    bpy.ops.object.select_all(action='DESELECT')
    empty.select_set(True)
    bpy.context.view_layer.objects.active = empty

    move_to_collection(empty, collection)
    move_to_collection(text_obj, collection)

    # Parent the text to the empty and keep world transform
    text_obj.parent = empty
    text_obj.location = (1,1,1)     # This location will be relative to the empty since it is a child!
    # text_obj.matrix_parent_inverse = empty.matrix_world.inverted()

    # print(f"Created Empty '{name_empty}' at {location} and Text '{name_text}' with content: {text_string}")


def get_entity_text(bytes):
    return bytes[BSP_OBJECT.header.entity_offset : BSP_OBJECT.header.entity_offset + BSP_OBJECT.header.entity_length].decode('ascii')


def parse_bsp_entities(text):
    print("Parsing entity text into objects...")
    entities = []
    # Split text into blocks using curly braces
    blocks = re.findall(r'\{([^}]*)\}', text)
    for block in blocks:
        entity = {}
        # Parse each line in the block
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            # Split on first space to get key and value
            parts = line.split(None, 1)
            if len(parts) == 2:
                key, value = parts
                # Remove surrounding quotes if present
                key = key.strip('"')
                value = value.strip('"')
                entity[key] = value
        if entity:
            entities.append(entity)
            # print(entity)
    return entities


def populate_entities(bytes, scale):
    """
    "Main" method called from importer
    """
    entity_text = get_entity_text(bytes)
    entities = parse_bsp_entities(entity_text)

    coll = get_or_create_collection(f"{BSP_OBJECT.name}_Entities")

    for idx, entity in enumerate(entities):
        if "origin" in entity.keys():      # Only create entityes when we have a location to do so
            this_empty_text = ""
            for i, (key, value) in enumerate(entity.items()):
                # print(f"{key}: {value}")
                this_empty_text += f"{key}: {value}\n"
                if key == "origin":
                    x, y, z = [coord * scale for coord in map(float, value.split())]
                    # print(f"X, Y, Z: {x,y,z}")
            if x and y and z:
                create_empty((x,y,z), this_empty_text, f"Empty_{i}", f"Text_{i}", coll)
        # If there's no origin (location) to place it at, add a custom property to the object
        else:
            string_custom_property = ""
            for i, (key, value) in enumerate(entity.items()):
                string_custom_property += f"{key}: {value}\n"

            BSP_OBJECT.obj.data[f"ENTITY_{idx}"] = string_custom_property