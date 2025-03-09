import bpy
from dataclasses import dataclass, fields
import struct
import platform
import os
import sys
import subprocess
import stat
from .types import *
from .utils import *
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


def load_verts(bytes):
    num_verts = len(bytes) / 12
    all_verts = list()
    for i in range(int(num_verts)):
        vertex = bsp_vertex(*list(struct.unpack("<fff", bytes[12*i : 12*i+12])))
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
    This method will accomplish both of these goals because the work to associate the edges/verts for mesh.from_pydata
    is essentially halfway to getting the texture associated as well.
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

        # Adds vertex indices to a list corresponding to the particular face
        # Used for creating mesh from pydata
        faces_by_verts.append(face_vert_list)
        BSP_OBJECT.face_vert_dict[idx] = tuple(face_vert_list)

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

    # for material_idx, material in enumerate(BSP_OBJECT.obj.data.materials):
    #     bpy.context.object.active_material_index = material_idx

    #     bpy.ops.object.mode_set(mode = 'EDIT')
    #     bpy.ops.mesh.select_all(action = 'DESELECT')

    #     bpy.ops.object.mode_set(mode = 'OBJECT')
    #     for face_idx, face in enumerate(BSP_OBJECT.mesh.polygons):      # MAYBE NOT THE SAME ORDER AFTER ALL, POOP #
    #         texture_idx = BSP_OBJECT.faces[face_idx].texture_info
    #         texture_name = BSP_OBJECT.textures[texture_idx].texture_name
    #         # material_idx = BSP_OBJECT.texture_material_index_dict[texture_name]
    #         found_material_idx = bpy.data.materials.find(f"M_{texture_name}")
    #         # print(f"M_{texture_name} returned material index {found_material_idx}")

    #         if material_idx == found_material_idx:
    #             face.material_index = bpy.context.object.active_material_index

    # bpy.ops.object.mode_set(mode = 'OBJECT')
    # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

    for material in BSP_OBJECT.obj.data.materials:
        for face in BSP_OBJECT.mesh.polygons:
            texture_idx = BSP_OBJECT.faces[face.index].texture_info
            texture_name = BSP_OBJECT.textures[texture_idx].texture_name
            found_material_idx = BSP_OBJECT.texture_material_index_dict[texture_name]
            
            face.material_index = found_material_idx



def create_uvs():
    uv_layer = BSP_OBJECT.mesh.uv_layers.new()
    BSP_OBJECT.mesh.uv_layers.active = uv_layer

    min_u = 999999
    max_u = 0
    min_v = 999999
    max_v = 0

    # Hopefully only non-image files that match the name of supposed textures...
    skipped_textures = list()

    for face in BSP_OBJECT.mesh.polygons:
        # for idx, (vert_idx, loop_idx) in enumerate(zip(face.vertices, face.loop_indices)):
        #     for vert_idx in BSP_OBJECT.face_vert_dict[face.index]:
        for loop_idx in face.loop_indices:
                vert_idx = BSP_OBJECT.obj.data.loops[loop_idx].vertex_index
                texture = BSP_OBJECT.vert_texture_dict[vert_idx]
                # Normalize
                vert_vector = BSP_OBJECT.vertices[vert_idx]

                x = vert_vector.x
                y = vert_vector.y
                z = vert_vector.z

                n_vector = normalize_vector([vert_vector.x, vert_vector.y, vert_vector.z])
                # print(f"Normalized Vector: {n_vector}")
                # print(f"u_axis: {texture.u_axis}, v_axis: {texture.v_axis}")
                # x = n_vector[0]
                # y = n_vector[1]
                # z = n_vector[2]

                bsp_u = x * texture.u_axis[0] + y * texture.u_axis[1] + z * texture.u_axis[2] + texture.u_offset
                bsp_v = x * texture.v_axis[0] + y * texture.v_axis[1] + z * texture.v_axis[2] + texture.v_offset

                # print(f"X: {x}, Y: {y}, Z: {z}")
                # print(f"u_axis.x: {texture.u_axis[0]}, u_axis.y: {texture.u_axis[1]}, u_axis.z: {texture.u_axis[2]}")
                # print(f"v_axis.x: {texture.v_axis[0]}, v_axis.y: {texture.v_axis[1]}, v_axis.z: {texture.v_axis[2]}")

                try:
                    texture_res = BSP_OBJECT.texture_resolution_dict[texture.texture_name]
                    
                    u = bsp_u / texture_res[0]
                    v = (1- bsp_v / texture_res[1])

                    # u = bsp_u
                    # v = 1 - bsp_v
                    # print([u, v])
                    # Logging/debugging
                    min_u = min(min_u, u)
                    max_u = max(max_u, u)
                    min_v = min(min_v, v)
                    max_v = max(max_v, v)

                    # print([u,v])
                    uv_layer.data[loop_idx].uv = [u,v]
                except Exception as e:
                    # print(f"Skipping {texture.texture_name} (may be .atd file or non-image)")
                    if texture.texture_name not in skipped_textures:
                        skipped_textures.append(texture.texture_name)
                    continue

    print(f"Min. U: {min_u}")
    print(f"Max. U: {max_u}")
    print(f"Min V: {min_v}")
    print(f"Max V: {max_v}")
    
    for t in skipped_textures:
        print(f'Skipped "texture": {t}')



def get_texture_images():
    # TODO: Add .WAL support
    valid_extensions = ['.tga','.png','.bmp','.jpg']
    file_paths = []
    for root, dirs, files in os.walk(BSP_OBJECT.folder_path):
        for file in files:
            if any(file.endswith(ext.casefold()) for ext in valid_extensions):
                file_paths.append(os.path.join(root, file))

    file_paths_map = {file_path.casefold(): file_path for file_path in file_paths}

    for i, t in enumerate(BSP_OBJECT.textures):
        texture_base_path = os.path.join(BSP_OBJECT.folder_path, *t.texture_name.split('/'))
        # potential_texture_paths = [f"{texture_base_path}{ext}" for ext in valid_extensions]
        # actual_texture_path = getfile_insensitive_from_list(potential_texture_paths)

        texture_name_casefold = t.texture_name.casefold()
        for casefolded_path, original_path in file_paths_map.items():
            if texture_name_casefold in casefolded_path:
                actual_texture_path = original_path
                break  # Stop checking other paths for this texture

        if actual_texture_path:
            BSP_OBJECT.texture_path_dict[t.texture_name] = actual_texture_path
            # Get resolution of texture
            try:
                with PIL.Image.open(actual_texture_path) as img:
                    BSP_OBJECT.texture_resolution_dict[t.texture_name] = img.size # x, y
            except Exception as e:
                print(f"Unable to open texture file (may be .atd, etc...): {t.texture_name}")
                print(f"Attempted path: {actual_texture_path}")
                print(f'Exception: {e}')
        else:
            print(f"ERROR: {t.texture_name}, index {i} not found at path:\n{texture_base_path}")



def load_idtech2_bsp(bsp_path):
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

        BSP_OBJECT.vertices = load_verts(file_bytes[BSP_OBJECT.header.vertices_offset : BSP_OBJECT.header.vertices_offset+BSP_OBJECT.header.vertices_length])
        BSP_OBJECT.edges = load_edges(file_bytes[BSP_OBJECT.header.edge_offset : BSP_OBJECT.header.edge_offset+BSP_OBJECT.header.edge_length])
        BSP_OBJECT.textures = load_textures(file_bytes[BSP_OBJECT.header.texture_info_offset : BSP_OBJECT.header.texture_info_offset+BSP_OBJECT.header.texture_info_length])
        BSP_OBJECT.faces = load_faces(file_bytes[BSP_OBJECT.header.faces_offset : BSP_OBJECT.header.faces_offset+BSP_OBJECT.header.faces_length])

        get_texture_images()

        faces_by_verts = get_face_and_texture_vertices(file_bytes)
        BSP_OBJECT.mesh.from_pydata(BSP_OBJECT.vertices, BSP_OBJECT.edges, faces_by_verts)
        create_materials()
        create_uvs()
        
        BSP_OBJECT.mesh.update()
        
        main_collection = bpy.data.collections[0]
        main_collection.objects.link(BSP_OBJECT.obj)
        bpy.context.view_layer.objects.active = BSP_OBJECT.obj

        assign_materials()



    except Exception as e:
        print(f"ERROR loading .BSP file: {e}")
        print(e.__traceback__.tb_frame.f_code.co_filename)
        print(f"LINE: {e.__traceback__.tb_lineno}")
        
    return {'FINISHED'}




    