import bpy
from dataclasses import dataclass, fields
import struct
import os
import math
import numpy as np
from collections import defaultdict
from pathlib import Path

from .custom_types import *
from .utils import *
from .wal import *
from .entities import populate_entities

import PIL
from PIL import Image, ImagePath


SAMPLE_STEP = 16.0  # world units per lightmap sample
pad = 0
atlas_max_width = 4096
use_closest_for_debug = False
flip_v = True

def build_all_face_lightmaps_in_memory(file_bytes):
    BSP_OBJECT.lightmap_images = []  # list of dicts: {'fi': int, 'img': PIL.Image, 'w':int, 'h':int}
    lm_base_offset = getattr(BSP_OBJECT.header, "lightmaps_offset", 0)
    total_bytes = len(file_bytes)

    def get_vertex_pos(vidx):
        v = BSP_OBJECT.vertices[vidx]
        return (v.x, v.y, v.z)

    def dot3(a, b):
        return a[0]*b.x + a[1]*b.y + a[2]*b.z

    for fi, face in enumerate(BSP_OBJECT.faces):
        vert_indices = BSP_OBJECT.face_verts_list[fi]
        if not vert_indices:
            continue

        texinfo = BSP_OBJECT.textures[face.texture_info]

        s_vals = []
        t_vals = []
        for vidx in vert_indices:
            vx, vy, vz = get_vertex_pos(vidx)
            v = (vx, vy, vz)
            s_real = dot3(v, bsp_vertex(*texinfo.u_axis)) - texinfo.u_offset
            t_real = dot3(v, bsp_vertex(*texinfo.v_axis)) - texinfo.v_offset
            s_vals.append(s_real / SAMPLE_STEP)
            t_vals.append(t_real / SAMPLE_STEP)

        min_s = math.floor(min(s_vals))
        max_s = math.ceil(max(s_vals))
        min_t = math.floor(min(t_vals))
        max_t = math.ceil(max(t_vals))

        width = int(max_s - min_s)
        height = int(max_t - min_t)

        if width <= 0 or height <= 0:
            print(f"Skipping face {fi}: degenerate lightmap size {width}x{height}")
            continue

        byte_offset = lm_base_offset + face.lightmap_offset
        expected_bytes = width * height * 3
        if byte_offset < 0 or byte_offset + expected_bytes > total_bytes:
            print(f"Face {fi}: invalid lightmap offset/size (offset={byte_offset}, bytes_needed={expected_bytes}), skipping")
            continue

        rgb_bytes = file_bytes[byte_offset: byte_offset + expected_bytes]

        img = Image.frombytes('RGB', (width, height), rgb_bytes)

        # optionally flip vertically to match Quake rows
        if flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        BSP_OBJECT.lightmap_images.append({'fi': fi, 'img': img, 'w': img.width, 'h': img.height})

    print(f"Built {len(BSP_OBJECT.lightmap_images)} in-memory face lightmaps")
    # return BSP_OBJECT.lightmap_images



def create_and_assign_atlas_lightmap(influence_pct):
    print("Creating atlas lightmap (in-memory only)...")
    face_images = getattr(BSP_OBJECT, 'lightmap_images', None)
    if not face_images:
        print("No in-memory lightmaps found on BSP_OBJECT.lightmap_images; aborting.")
        return

    # Ensure Pillow RGBA and w/h present
    face_images = [{'fi': r['fi'], 'img': r['img'].convert('RGBA'), 'w': r.get('w', r['img'].width), 'h': r.get('h', r['img'].height)} for r in face_images]

    # packer prep
    face_images.sort(key=lambda r: r['h'], reverse=True)
    def next_pow2(x): return 1 << (x - 1).bit_length()
    max_w = max(r['w'] for r in face_images)
    atlas_w = min(atlas_max_width, next_pow2(max_w))
    atlas_w = max(atlas_w, 64)

    placements = []
    cur_x = 0
    cur_y = 0
    row_h = 0

    # pack rects into rows; do NOT assume atlas_h yet
    print("Packing atlas rectangles...")
    for r in face_images:
        w = r['w'] + 2 * pad
        h = r['h'] + 2 * pad
        # if rect (including pad) wider than atlas, try to expand atlas_w (within max)
        if w > atlas_w:
            if w <= atlas_max_width:
                atlas_w = min(atlas_max_width, next_pow2(w))
            else:
                print(f"Face {r['fi']} too wide for atlas_max_width; skipping")
                continue
        if cur_x + w > atlas_w:
            cur_y += row_h
            cur_x = 0
            row_h = 0
        placements.append({'fi': r['fi'], 'img': r['img'], 'x': cur_x, 'y': cur_y, 'w': r['w'], 'h': r['h']})
        cur_x += w
        row_h = max(row_h, h)

    atlas_h = cur_y + row_h
    if atlas_h <= 0:
        print("Atlas height computed zero; aborting.")
        return

    # Create atlas image in Pillow and paste using pad offset
    print("Creating & saving actual image...")
    atlas_img_pil = Image.new('RGBA', (atlas_w, atlas_h), (255, 255, 255, 255))
    for p in placements:
        paste_x = p['x'] + pad
        paste_y = p['y'] + pad
        atlas_img_pil.paste(p['img'], (paste_x, paste_y), p['img'])

    # Save single atlas to disk (allowed) and load into Blender
    atlas_name = f"{BSP_OBJECT.name}_atlas"
    BSP_OBJECT.lightmap_folder = BSP_OBJECT.lightmap_folder or (Path(BSP_OBJECT.folder_path) / Path(f'{BSP_OBJECT.name}_bsp_lightmaps'))
    BSP_OBJECT.lightmap_folder.mkdir(parents=True, exist_ok=True)
    atlas_path = Path(BSP_OBJECT.lightmap_folder) / f"{atlas_name}.png"

    print(f"SAVING: {atlas_path}")
    atlas_img_pil.save(str(atlas_path), format='PNG')

    atlas_bpy = None
    try:
        atlas_bpy = bpy.data.images.load(str(atlas_path), check_existing=True)
        atlas_bpy.name = atlas_name
    except Exception as e:
        print(f"Failed to load atlas image into Blender: {e}")
        return

    atlas_bpy.colorspace_settings.name = 'sRGB'
    if use_closest_for_debug:
        try:
            atlas_bpy.use_alpha = True
        except:
            pass

    # Create LightmapUV
    mesh = BSP_OBJECT.mesh
    lm_uv_name = "LightmapUV"
    if lm_uv_name in mesh.uv_layers:
        lm_uv = mesh.uv_layers[lm_uv_name]
    else:
        lm_uv = mesh.uv_layers.new(name=lm_uv_name)
    mesh.uv_layers.active = lm_uv

    atlas_w_real, atlas_h_real = atlas_img_pil.size
    rect_map = {}
    for p in placements:
        x = p['x'] + pad
        y = p['y'] + pad
        w = p['w']
        h = p['h']
        u0 = x / atlas_w_real
        v0 = y / atlas_h_real
        u1 = (x + w) / atlas_w_real
        v1 = (y + h) / atlas_h_real
        rect_map[p['fi']] = (u0, v0, u1, v1, w, h)

    uv_data = lm_uv.data
    for poly in mesh.polygons:
        fi = poly.index
        rect = rect_map.get(fi)
        if not rect:
            continue
        u0, v0, u1, v1, pw, ph = rect
        loops_start = poly.loop_start
        loops_total = poly.loop_total
        if loops_total == 3:
            local_uvs = [(0.0,0.0),(1.0,0.0),(0.0,1.0)]
        elif loops_total == 4:
            local_uvs = [(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0)]
        else:
            local_uvs = []
            for i in range(loops_total):
                frac = i / max(1, loops_total-1)
                local_uvs.append((frac, frac))
        for li in range(loops_total):
            lu, lv = local_uvs[li]
            u = u0 + lu * (u1 - u0)
            v = v0 + lv * (v1 - v0)
            if flip_v:
                v = 1.0 - v
            uv_data[loops_start + li].uv = (u, v)

    mesh.update()

    # Augment each existing base material node tree to multiply by atlas sample into Principled Base Color
    print("Adding lightmap material nodes...")
    for mat in BSP_OBJECT.obj.data.materials:
        if mat is None:
            continue
        if not mat.use_nodes:
            mat.use_nodes = True
        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links

        # Detect if we've already applied the patch
        if nodes.get("LM_ATLAS_Marker"):
            continue

        # Find Principled BSDF
        principled = None
        for n in nodes:
            if n.type == 'BSDF_PRINCIPLED':
                principled = n
                break
        if not principled:
            continue

        # Create nodes (idempotent by name marker)
        uv_map_node = nodes.new('ShaderNodeUVMap')
        uv_map_node.name = "LM_UVMap"
        uv_map_node.uv_map = lm_uv_name

        atlas_tex = nodes.new('ShaderNodeTexImage')
        atlas_tex.name = "LM_Atlas_Tex"
        atlas_tex.image = atlas_bpy
        atlas_tex.extension = 'CLIP'
        if use_closest_for_debug:
            try:
                atlas_tex.interpolation = 'Closest'
            except:
                pass

        mix_node = nodes.new('ShaderNodeMixRGB')
        mix_node.name = "LM_Multiply"
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs['Fac'].default_value = 1.0

        marker = nodes.new('ShaderNodeValue')
        marker.name = "Lightmap_Infuence"
        marker.label = "Lightmap Influence"
        marker.outputs[0].default_value = 1.0 * influence_pct

        links.new(marker.outputs[0], mix_node.inputs['Fac'])

        # find current incoming link to Principled Base Color, if any
        base_color_input = principled.inputs.get('Base Color')
        incoming_link = None
        for l in list(tree.links):
            if l.to_node == principled and l.to_socket == base_color_input:
                incoming_link = l
                break

        # Connect UV -> atlas_tex, atlas -> mix color2
        links.new(uv_map_node.outputs['UV'], atlas_tex.inputs['Vector'])
        links.new(atlas_tex.outputs['Color'], mix_node.inputs['Color2'])

        if incoming_link:
            src_socket = incoming_link.from_socket
            try:
                links.remove(incoming_link)
            except:
                pass
            links.new(src_socket, mix_node.inputs['Color1'])
        else:
            rgb = nodes.new('ShaderNodeRGB')
            rgb.outputs[0].default_value = (1.0,1.0,1.0,1.0)
            links.new(rgb.outputs[0], mix_node.inputs['Color1'])

        links.new(mix_node.outputs['Color'], base_color_input)

    print(f"Built lightmap atlas ({atlas_w_real}x{atlas_h_real}), applied LightmapUV and patched materials. Atlas image: {atlas_bpy.name}")


def apply_face_lightmaps_to_mesh():
    # Determine folder where face lightmaps were saved
    # if bpy.data.filepath:
    #     base_dir = Path(bpy.path.abspath("//"))
    # else:
    #     base_dir = Path(bpy.app.tempdir)

    lm_folder = BSP_OBJECT.lightmap_folder

    obj = BSP_OBJECT.obj
    mesh = obj.data

    # Ensure a UV map for lightmaps exists; we'll create per-face UVs that span 0..1
    lm_uv_name = "LightmapUV"
    if lm_uv_name in mesh.uv_layers:
        lm_uv = mesh.uv_layers[lm_uv_name]
    else:
        lm_uv = mesh.uv_layers.new(name=lm_uv_name)

    # For convenience, ensure we have an active UV map (not strictly required)
    mesh.uv_layers.active = lm_uv

    # Load all per-face images into Blender.images with predictable names
    # Map: face_index -> bpy.data.images image
    face_image_map = {}
    for poly in mesh.polygons:
        fi = poly.index
        img_path = lm_folder / f"face_{fi:04d}_lightmap.png"
        if img_path.exists():
            try:
                img = bpy.data.images.load(str(img_path), check_existing=True)
                face_image_map[fi] = img
            except Exception as e:
                print(f"Failed loading image for face {fi}: {e}")

    # For each polygon that has a lightmap image, set its UVs to cover 0..1 and create a material that uses that image
    # We'll create a material per polygon that has an image (to keep it simple)
    for poly in mesh.polygons:
        fi = poly.index
        img = face_image_map.get(fi)
        if not img:
            continue

        # set UVs for this polygon to full-quad (0..1) according to polygon loop order
        # polygon.loop_start..loop_start+loop_total are indices into mesh.loops and uv layer data
        loops_start = poly.loop_start
        loops_total = poly.loop_total
        # compute uv coords for each loop (we'll map the polygon's bounds to 0..1)
        # simplest: map each loop vertex to a trivial UV layout covering [0,1] using barycentric-ish mapping:
        # assign UVs cyclically so triangles/quads map reasonably
        uv_layer = lm_uv.data
        if loops_total == 3:
            uvs = [(0.0,0.0),(1.0,0.0),(0.0,1.0)]
        elif loops_total == 4:
            uvs = [(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0)]
        else:
            # For n-gons, distribute around unit square perimeter (approx)
            uvs = []
            for i in range(loops_total):
                frac = i / max(1, loops_total-1)
                uvs.append((frac, frac))  # approximate; arbitrary but consistent
        for li in range(loops_total):
            uv_layer[loops_start + li].uv = uvs[li]

        # Create material for this face that combines base material with this lightmap as multiply
        base_texinfo_idx = BSP_OBJECT.faces[fi].texture_info
        base_texture_name = BSP_OBJECT.textures[base_texinfo_idx].texture_name
        base_mat_index = BSP_OBJECT.texture_material_index_dict.get(base_texture_name)

        # Get the base material (created earlier) by index
        if base_mat_index is None or base_mat_index >= len(BSP_OBJECT.obj.data.materials):
            # fallback: create a basic material
            base_mat = bpy.data.materials.new(name=f"M_{base_texture_name}_fallback")
            base_mat.use_nodes = True
        else:
            base_mat = BSP_OBJECT.obj.data.materials[base_mat_index]

        # Duplicate the base material so we can assign this face a unique lightmap image without affecting others
        new_mat = base_mat.copy()
        new_mat.name = f"{base_mat.name}_face_{fi:04d}"
        new_mat.use_nodes = True
        node_tree = new_mat.node_tree
        nodes = node_tree.nodes
        links = node_tree.links

        # Ensure Principled BSDF exists
        principled = None
        for n in nodes:
            if n.type == 'BSDF_PRINCIPLED':
                principled = n
                break
        if not principled:
            principled = nodes.new('ShaderNodeBsdfPrincipled')
            output = None
            for n in nodes:
                if n.type == 'OUTPUT_MATERIAL':
                    output = n
                    break
            if output:
                links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        # Create Image Texture node for the lightmap
        lm_tex_node = nodes.new('ShaderNodeTexImage')
        lm_tex_node.image = img
        # set the UV map to our LightmapUV
        lm_tex_node.extension = 'CLIP'
        # Create UV Map node to select LightmapUV
        uv_map_node = nodes.new('ShaderNodeUVMap')
        uv_map_node.uv_map = lm_uv_name
        links.new(uv_map_node.outputs['UV'], lm_tex_node.inputs['Vector'])

        # Create Mix node to multiply base color by lightmap (use Multiply = MixRGB with Fac=1 and blend type MULTIPLY)
        mix_node = nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs['Fac'].default_value = 1.0

        # Find existing base texture node in the node tree (if present) to connect into mix
        base_color_node = None
        for n in nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.filepath == getattr(base_mat.node_tree.nodes.get('Image Texture'), 'image', None):
                base_color_node = n
                break
        # Simpler: create a new Image Texture node for the base texture if none found, using BSP_OBJECT.texture_path_dict
        base_img = None
        texture_path = BSP_OBJECT.texture_path_dict.get(base_texture_name)
        if texture_path:
            try:
                base_img = bpy.data.images.load(texture_path, check_existing=True)
            except:
                base_img = None
        if base_img:
            base_tex_node = nodes.new('ShaderNodeTexImage')
            base_tex_node.image = base_img
            # connect base_tex_node color to mix color1
            links.new(base_tex_node.outputs['Color'], mix_node.inputs['Color1'])
        else:
            # fallback: use a white color
            rgb_node = nodes.new('ShaderNodeRGB')
            rgb_node.outputs[0].default_value = (1.0,1.0,1.0,1.0)
            links.new(rgb_node.outputs[0], mix_node.inputs['Color1'])

        # connect lightmap into Color2 of mix
        links.new(lm_tex_node.outputs['Color'], mix_node.inputs['Color2'])

        # connect mix output to Principled Base Color
        links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])

        # Append new material to object and assign to polygon
        BSP_OBJECT.obj.data.materials.append(new_mat)
        new_index = len(BSP_OBJECT.obj.data.materials) - 1
        poly.material_index = new_index

    print("Applied per-face lightmaps (one material per face with lightmap).")


def load_header(bytes):
    arguments = struct.unpack(f"<{'i'*40}", bytes[:160])
    return bsp_header(*arguments)


def load_file(path):
    with open(path, "rb") as f:
        bytes = f.read()
    BSP_OBJECT.header = load_header(bytes)

    print("--------------- HEADER VALUES -------------------")
    for field in fields(BSP_OBJECT.header):
        print(f"{field.name} - ", getattr(BSP_OBJECT.header, field.name))
    print("--------------------------------------------------")
    return bytes


def load_verts(bytes, model_scale):
    num_verts = len(bytes) / 12
    all_verts = list()
    for i in range(int(num_verts)):
        vertex = bsp_vertex(*list(struct.unpack("<fff", bytes[12*i : 12*i+12])))
        # Scale the vertex
        # scaled_vertex = bsp_vertex(
        #     x=vertex.x * model_scale,
        #     y=vertex.y * model_scale,
        #     z=vertex.z * model_scale
        # )
        all_verts.append(vertex)
    return all_verts


def load_edges(bytes):
    num_edges = len(bytes) / 4
    all_edges = list()
    for i in range(int(num_edges)):
        edge = bsp_edge(*list(struct.unpack("<HH", bytes[4*i : 4*i+4])))
        all_edges.append(edge)
    return all_edges


def load_faces(bytes):
    num_faces = len(bytes) / 20
    all_faces = list()
    for i in range(int(num_faces)):
        unpacked_bytes = list(struct.unpack("<HHIHHBBBBI", bytes[20*i : 20*i+20]))
        face = bsp_face(
            plane = unpacked_bytes[0],
            plane_side = unpacked_bytes[1],
            first_edge = unpacked_bytes[2],
            num_edges = unpacked_bytes[3],
            texture_info = unpacked_bytes[4],
            lightmap_styles = unpacked_bytes[5:9],          # This is an array/list, the reason for handling the properties individually
            lightmap_offset = unpacked_bytes[9]
        )
        all_faces.append(face)
    return all_faces


def get_face_and_texture_vertices(bytes):
    """
    mesh.from_pydata needs the vertex indices of the faces, which will be returned from this.
    The UVs need to be calculated per vertex, using the coordinates.
    """
    faces_by_verts = list()
    for idx, f in enumerate(BSP_OBJECT.faces):

        face_vert_list = list()
        # vert_texture_list = list()
        edges = list()
        for i in range(f.first_edge, f.first_edge + f.num_edges):
            # Get actual edge index from face-edge array
            edge_idx = struct.unpack("<i", bytes[BSP_OBJECT.header.face_edge_table_offset + (i*4) : BSP_OBJECT.header.face_edge_table_offset + (i*4) + 4])[0]
            if edge_idx < 0:
                negative_flag = True

            # Bear in mind this gets the INDICES of the vertices of the edge, not the coordinates (this is what the mesh from pydata function takes in)
            this_edge = BSP_OBJECT.edges[abs(edge_idx)]
            edges.append(this_edge)

            # Negative number indicates drawing the edge from the 2nd point instead of the 1st
            if edge_idx < 0:
                face_vert_list.extend(list(reversed(this_edge)))    
            else:
                face_vert_list.extend(this_edge)

        face_vert_list = remove_duplicates(face_vert_list)
        # Adds vertex indices to a list corresponding to the particular face
        # Used for creating mesh from pydata
        BSP_OBJECT.face_verts_list.append(face_vert_list) 

        # Now that we have vertices associated with faces, while we're here, get the texture_info from the face,
        # and associate the vertices with that texture as well, for assigning UVs later
        face_texture = BSP_OBJECT.textures[f.texture_info]
        for vert_idx in face_vert_list:
            BSP_OBJECT.vert_texture_dict[vert_idx] = face_texture

    # return faces_by_verts


def load_textures(bytes):
    num_textures = len(bytes) / 76
    all_textures = list()
    for i in range(int(num_textures)):
        unpacked_bytes = list(struct.unpack(f"<{'f'*8}II{'c'*32}i", bytes[76*i : 76*i+76]))
        texture_info = bsp_texture_info(
            u_axis = unpacked_bytes[0:3],
            u_offset = unpacked_bytes[3],
            v_axis = unpacked_bytes[4:7],
            v_offset = unpacked_bytes[7],
            flags = unpacked_bytes[8],
            value = unpacked_bytes[9],
            texture_name = b''.join([byte for byte in unpacked_bytes[10:42] if byte != b'\x00']).decode('utf-8'),
            next_texinfo = unpacked_bytes[42]
        )

        all_textures.append(texture_info)

    # Note animation textures
    for t in all_textures:
        if t.next_texinfo != -1:
            BSP_OBJECT.animation_textures.append(t.next_texinfo)
            print(f"Adding animation texture to list: {t.next_texinfo}")
    return all_textures


def create_materials():
    distinct_texture_names = {tex.texture_name for tex in BSP_OBJECT.textures}
    for i, t in enumerate(distinct_texture_names):
        try:
            material_name = f"M_{t}"

            # Create the material
            mat = bpy.data.materials.new(name = material_name)

            mat.use_nodes = True
            # Create the shader node
            bsdf = mat.node_tree.nodes['Principled BSDF']

            if (bpy.app.version < (4,0,0)):
                bsdf.inputs['Specular'].default_value = 0
            else:
                bsdf.inputs['Specular IOR Level'].default_value = 0

            # Create the texture image node
            tex_image = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex_image.image = bpy.data.images.load(BSP_OBJECT.texture_path_dict[t])
            mat.node_tree.links.new(tex_image.outputs['Color'], bsdf.inputs['Base Color'])

            # Add the new material to the mesh/object
            BSP_OBJECT.obj.data.materials.append(mat)

            # Keep track of the material index for this texture name
            # Later, it will be used to associate w/ the faces
            # BSP_OBJECT.texture_material_index_dict[t] = bpy.data.materials.find(mat.name)
            BSP_OBJECT.texture_material_index_dict[t] = i
        except Exception as e:
            print(f"ERROR creating material for texture: {t}")


def assign_materials():
    bpy.context.tool_settings.mesh_select_mode = [False, False, True]

    for material in BSP_OBJECT.obj.data.materials:
        for face in BSP_OBJECT.mesh.polygons:
            texture_idx = BSP_OBJECT.faces[face.index].texture_info
            texture_name = BSP_OBJECT.textures[texture_idx].texture_name
            found_material_idx = BSP_OBJECT.texture_material_index_dict[texture_name]

            face.material_index = found_material_idx


def create_uvs(model_scale):
    print("Creating UVs...")
    BSP_OBJECT.obj.select_set(True)
    print(f"Existing UV layers: {BSP_OBJECT.mesh.uv_layers}")

    uv_layer = BSP_OBJECT.mesh.uv_layers.new()
    BSP_OBJECT.mesh.uv_layers.active = uv_layer

    print(f"UV Layer: {uv_layer}")

    # Hopefully only non-image files that match the name of supposed textures...
    skipped_textures = dict()
    bpy.ops.object.mode_set(mode='OBJECT')

    for face in BSP_OBJECT.mesh.polygons:
        for (vert_idx, loop_idx) in zip(face.vertices, face.loop_indices):
            # vert_idx = BSP_OBJECT.obj.data.loops[loop_idx].vertex_index
            # texture = BSP_OBJECT.vert_texture_dict[vert_idx]
            texture_info = BSP_OBJECT.faces[face.index].texture_info
            texture = BSP_OBJECT.textures[texture_info]

            # Could omit animation textures, but probably pointless...
            vert_vector = BSP_OBJECT.vertices[vert_idx]

            x = vert_vector.x
            y = vert_vector.y
            z = vert_vector.z

            bsp_u = x * texture.u_axis[0] + y * texture.u_axis[1] + z * texture.u_axis[2] + texture.u_offset
            bsp_v = x * texture.v_axis[0] + y * texture.v_axis[1] + z * texture.v_axis[2] + texture.v_offset

            # bsp_u = (x * model_scale) * texture.u_axis[0] + (y * model_scale) * texture.u_axis[1] + (z * model_scale) * texture.u_axis[2] + texture.u_offset
            # bsp_v = (x * model_scale) * texture.v_axis[0] + (y * model_scale) * texture.v_axis[1] + (z * model_scale) * texture.v_axis[2] + texture.v_offset

            try:
                texture_res = BSP_OBJECT.texture_resolution_dict[texture.texture_name]

                if not texture_res:
                    print(f"ERROR:  No resolution found for {texture.texture_name}")

                u = bsp_u / texture_res[0]
                v = (1 - bsp_v / texture_res[1])    # Invert y-axis for Blender

                uv_layer.data[loop_idx].uv = [u,v]
            except Exception as e:
                print(f"Skipping {texture.texture_name} (may be .atd file or non-image)\n{e}")
                if texture.texture_name not in skipped_textures.keys():
                    skipped_textures[texture.texture_name] = f"{e}\n{e.__traceback__.tb_frame.f_code.co_filename}\n{e.__traceback__.tb_lineno}" + f"\nUV1: {u1,v1}"
                continue


def get_texture_images(search_from_parent):
    valid_extensions = ['.tga','.png','.bmp','.jpg','.wal']
    file_paths = []

    # For Quake/Quake II, the default folder layout often places the .BSP files in a folder adjacent the textures,
    # instead of in a subfolder.  This option allows searching from the parent folder to find those textures.
    texture_search_folder = BSP_OBJECT.folder_path
    if search_from_parent:
        texture_search_folder = Path(BSP_OBJECT.folder_path).parent

    print(f"Searching for appropriate texture image files in: {texture_search_folder}")
    actual_texture_path = ""

    for root, dirs, files in os.walk(texture_search_folder):
        for file in files:
            if any(file.endswith(ext.casefold()) for ext in valid_extensions):
                file_paths.append(os.path.join(root, file))

    file_paths_map = {file_path.casefold(): file_path for file_path in file_paths}

    for i, t in enumerate(BSP_OBJECT.textures):
        # texture_base_path = os.path.join(BSP_OBJECT.folder_path, *t.texture_name.split('/'))
        # potential_texture_paths = [f"{texture_base_path}{ext}" for ext in valid_extensions]
        # actual_texture_path = getfile_insensitive_from_list(potential_texture_paths)

        texture_name_casefold = t.texture_name.casefold()
        for casefolded_path, original_path in file_paths_map.items():
            if texture_name_casefold.replace('\\','/') in casefolded_path.replace('\\','/'):
                actual_texture_path = original_path
                break  # Stop checking other paths for this texture

        if not actual_texture_path == "":
            # Get resolution of texture
            try:
                final_texture_path = ''
                # if actual_texture_path.endswith('.pcx'):
                #     print(f".PCX image: {actual_texture_path}")
                if actual_texture_path.endswith('.wal'):
                    wal_object = wal_image(actual_texture_path)
                    with wal_object.image as img:
                        if not t.texture_name in BSP_OBJECT.texture_resolution_dict:
                            BSP_OBJECT.texture_resolution_dict[t.texture_name] = (wal_object.width, wal_object.height)

                        # Need to write a normal image because even if we can parse it, blender won't load a .wal as a texture
                        base_texture_path, _ = os.path.splitext(actual_texture_path)
                        new_texture_path = base_texture_path + ".png"

                        # if not os.path.exists(new_texture_path):
                        print(f".WAL image, writing .PNG copy for Blender: {new_texture_path}")
                        img.save(new_texture_path)
                        final_texture_path = new_texture_path

                else:
                    final_texture_path = actual_texture_path
                    with PIL.Image.open(final_texture_path) as img:
                        if not t.texture_name in BSP_OBJECT.texture_resolution_dict:
                            BSP_OBJECT.texture_resolution_dict[t.texture_name] = img.size # x, y
            except Exception as e:
                # print(f"Unable to open texture file (may be .atd, etc...): {t.texture_name}")
                print(f"ERROR getting {t.texture_name}, attempted path: {final_texture_path}")
                print(f'Exception: {e}')

            BSP_OBJECT.texture_path_dict[t.texture_name] = final_texture_path
            # print(f"Actual path: {actual_texture_path} ----- Final path: {final_texture_path}")
        else:
            print(f"ERROR: {t.texture_name}, index {i} not found (actual_texture_path blank)")



def load_idtech2_bsp(bsp_path, model_scale, apply_transforms, search_from_parent, apply_lightmaps, lightmap_influence, show_entities):
    if not os.path.isfile(bsp_path):
        bpy.context.window_manager.popup_menu(missing_file, title="Error", icon='ERROR')
        return {'FINISHED'} 

    print("Loading idtech2 .bsp...")
    try:
        BSP_OBJECT.face_verts_list = list()

        file_bytes = load_file(bsp_path)
        BSP_OBJECT.folder_path = os.path.dirname(bsp_path)

        # Create the mesh
        filename = os.path.basename(bsp_path)
        object_name = filename.split('.')[0]        # trim off the .bsp extension

        print(f"Creating mesh: {object_name}")
        BSP_OBJECT.name = object_name

        BSP_OBJECT.mesh = bpy.data.meshes.new(object_name)
        BSP_OBJECT.obj = bpy.data.objects.new(object_name, BSP_OBJECT.mesh)

        BSP_OBJECT.vertices = load_verts(file_bytes[BSP_OBJECT.header.vertices_offset : BSP_OBJECT.header.vertices_offset+BSP_OBJECT.header.vertices_length], model_scale)
        BSP_OBJECT.edges = load_edges(file_bytes[BSP_OBJECT.header.edge_offset : BSP_OBJECT.header.edge_offset+BSP_OBJECT.header.edge_length])
        BSP_OBJECT.textures = load_textures(file_bytes[BSP_OBJECT.header.texture_info_offset : BSP_OBJECT.header.texture_info_offset+BSP_OBJECT.header.texture_info_length])
        BSP_OBJECT.faces = load_faces(file_bytes[BSP_OBJECT.header.faces_offset : BSP_OBJECT.header.faces_offset+BSP_OBJECT.header.faces_length])

        get_texture_images(search_from_parent)

        # faces_by_verts = get_face_and_texture_vertices(file_bytes)
        get_face_and_texture_vertices(file_bytes)

        print("Creating mesh...")
        BSP_OBJECT.mesh.from_pydata(BSP_OBJECT.vertices, [], BSP_OBJECT.face_verts_list)
        create_materials()

        main_collection = bpy.data.collections[0]
        main_collection.objects.link(BSP_OBJECT.obj)
        bpy.context.view_layer.objects.active = BSP_OBJECT.obj

        create_uvs(model_scale)
        assign_materials()

        if apply_lightmaps:
            # save_all_face_lightmaps(file_bytes, float(lightmap_influence / 100))
            build_all_face_lightmaps_in_memory(file_bytes)
            create_and_assign_atlas_lightmap(float(lightmap_influence / 100))

        if show_entities:
            populate_entities(file_bytes, model_scale)


        print("Applying scale...")
        BSP_OBJECT.obj.scale = (model_scale, model_scale, model_scale)


        if apply_transforms:
            print("Applying transforms...")
            context = bpy.context
            ob = context.object
            mb = ob.matrix_basis
            if hasattr(ob.data, "transform"):
                ob.data.transform(mb)
            for c in ob.children:
                c.matrix_local = mb @ c.matrix_local

            ob.matrix_basis.identity()

        BSP_OBJECT.mesh.update()


    except Exception as e:
        print(f"ERROR loading .BSP file: {e}")
        print(e.__traceback__.tb_frame.f_code.co_filename)
        print(f"LINE: {e.__traceback__.tb_lineno}")

    return {'FINISHED'}




