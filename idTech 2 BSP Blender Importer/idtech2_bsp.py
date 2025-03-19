import bpy
from dataclasses import dataclass, fields
import struct
import os
import numpy as np
from collections import defaultdict
from .custom_types import *
from .utils import *
from .wal import *

import PIL
from PIL import Image, ImagePath



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
        for i in range(f.first_edge, f.first_edge + f.num_edges):
            # Get actual edge index from face-edge array
            edge_idx = struct.unpack("<i", bytes[BSP_OBJECT.header.face_edge_table_offset + (i*4) : BSP_OBJECT.header.face_edge_table_offset + (i*4) + 4])[0]
            if edge_idx < 0:
                negative_flag = True
            
            # Bear in mind this gets the INDICES of the vertices of the edge, not the coordinates (this is what the mesh from pydata function takes in)
            this_edge = BSP_OBJECT.edges[abs(edge_idx)]

            # Negative number indicates drawing the edge from the 2nd point instead of the 1st
            if edge_idx < 0:
                face_vert_list.extend(list(reversed(this_edge)))
            else:
                face_vert_list.extend(this_edge)


        face_vert_list = remove_duplicates(face_vert_list)
        # Adds vertex indices to a list corresponding to the particular face
        # Used for creating mesh from pydata
        faces_by_verts.append(face_vert_list)

        # Now that we have vertices associated with faces, while we're here, get the texture_info from the face,
        # and associate the vertices with that texture as well, for assigning UVs later
        face_texture = BSP_OBJECT.textures[f.texture_info]
        for vert_idx in face_vert_list:
            BSP_OBJECT.vert_texture_dict[vert_idx] = face_texture

    return faces_by_verts



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
    BSP_OBJECT.obj.select_set(True)
    uv_layer = BSP_OBJECT.mesh.uv_layers.new()
    BSP_OBJECT.mesh.uv_layers.active = uv_layer

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
                v = (1 - bsp_v / texture_res[1])


                uv_layer.data[loop_idx].uv = [u,v]
            except Exception as e:
                # print(f"Skipping {texture.texture_name} (may be .atd file or non-image)")
                if texture.texture_name not in skipped_textures.keys():
                    skipped_textures[texture.texture_name] = f"{e}\n{e.__traceback__.tb_frame.f_code.co_filename}\n{e.__traceback__.tb_lineno}" + \
                        f"\nUV1: {u1,v1}"
                continue



def get_texture_images(search_from_parent):
    valid_extensions = ['.tga','.png','.bmp','.jpg','.wal','pcx']
    file_paths = []

    # For Quake/Quake II, the default folder layout often places the .BSP files in a folder adjacent the textures,
    # instead of in a subfolder.  This option allows searching from the parent folder to find those textures.
    texture_search_folder = BSP_OBJECT.folder_path
    if search_from_parent:
        texture_search_folder = os.path.dirname(BSP_OBJECT.folder_path)

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

        if actual_texture_path:
            # Get resolution of texture
            try:
                
                final_texture_path = ''
                if actual_texture_path.endswith('.pcx'):
                    print(f".PCX image: {actual_texture_path}")
                if actual_texture_path.endswith('.wal'):
                    wal_object = wal_image(actual_texture_path)
                    with wal_object.image as img:
                        if not t.texture_name in BSP_OBJECT.texture_resolution_dict:
                            BSP_OBJECT.texture_resolution_dict[t.texture_name] = (wal_object.width, wal_object.height)

                        # Need to write a normal image because even if we can parse it, blender won't load a .wal as a texture
                        base_texture_path, _ = os.path.splitext(actual_texture_path)
                        new_texture_path = base_texture_path + ".png"
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
            print(f"ERROR: {t.texture_name}, index {i} not found at path:\n{texture_base_path}")



def load_idtech2_bsp(bsp_path, model_scale, apply_transforms, search_from_parent):
    if not os.path.isfile(bsp_path):
        bpy.context.window_manager.popup_menu(missing_file, title="Error", icon='ERROR')
        return {'FINISHED'} 

    print("Loading idtech2 .bsp...")
    try:
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

        faces_by_verts = get_face_and_texture_vertices(file_bytes)
        BSP_OBJECT.mesh.from_pydata(BSP_OBJECT.vertices, [], faces_by_verts)
        create_materials()
        
        main_collection = bpy.data.collections[0]
        main_collection.objects.link(BSP_OBJECT.obj)
        bpy.context.view_layer.objects.active = BSP_OBJECT.obj

        create_uvs(model_scale)
        assign_materials()

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




    