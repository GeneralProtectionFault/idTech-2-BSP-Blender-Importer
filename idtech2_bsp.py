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


def get_face_vertices(bytes):
    faces_by_verts = list()
    for idx, f in enumerate(BSP_OBJECT.faces):
        
        face_vert_list = list()
        for i in range(f.first_edge, f.first_edge + f.num_edges):
            # Get actual edge index from face-edge array
            edge_idx = struct.unpack("<i", bytes[BSP_OBJECT.header.face_edge_table_offset + (i*4) : BSP_OBJECT.header.face_edge_table_offset + (i*4) + 4])[0]
            if edge_idx < 0:
                negative_flag = True
            
            this_edge = BSP_OBJECT.edges[abs(edge_idx)]
            
            # Negative number indicates drawing the edge from the 2nd point instead of the 1st
            if edge_idx < 0:
                face_vert_list.extend(list(reversed(this_edge)))
            else:
                face_vert_list.extend(this_edge)

        faces_by_verts.append(face_vert_list)
    return faces_by_verts



def load_textures(bytes):
    num_textures = len(bytes) / 76
    all_textures = list()
    for i in range(int(num_textures)):
        unpacked_bytes = list(struct.unpack(f"<{'f'*8}II{'c'*32}i", bytes[76*i : 76*i+76]))
        texture_info = bsp_texture_info(
            u_axis = unpacked_bytes[0:2],
            u_offset = unpacked_bytes[3],
            v_axis = unpacked_bytes[4:6],
            v_offset = unpacked_bytes[7],
            flags = unpacked_bytes[8],
            value = unpacked_bytes[9],
            texture_name = b''.join([byte for byte in unpacked_bytes[10:41] if byte != b'\x00']).decode('utf-8'),
            next_texinfo = unpacked_bytes[42]
        )
        all_textures.append(texture_info)
    return all_textures



def get_textures():
    for i, t in enumerate(BSP_OBJECT.textures):
        valid_extensions = ['.tga','.png','.bmp']
        texture_base_path = os.path.join(BSP_OBJECT.folder_path, *t.texture_name.split('/'))
        potential_texture_paths = [f"{texture_base_path}{ext}" for ext in valid_extensions]
        
        actual_texture_path = getfile_insensitive_from_list(potential_texture_paths)
        if actual_texture_path:
            BSP_OBJECT.texture_path_dict[t.texture_name] = actual_texture_path
        else:
            print(f"ERROR: {t.texture_name}, index {i} not found at path:\n{texture_base_path}")

def map_texture_and_uv():
    # Texture coordinates....
    # Probably create a dictionary of faces to texture, or just use the face objects that have texture_info anyway...



    uv_layer = BSP_OBJECT.mesh.uv_layers.new()
    BSP_OBJECT.uv_layers.active = uv_layer
    

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
        BSP_OBJECT.faces = load_faces(file_bytes[BSP_OBJECT.header.faces_offset : BSP_OBJECT.header.faces_offset+BSP_OBJECT.header.faces_length])

        BSP_OBJECT.textures = load_textures(file_bytes[BSP_OBJECT.header.texture_info_offset : BSP_OBJECT.header.texture_info_offset+BSP_OBJECT.header.texture_info_length])
        get_textures()

        faces_by_verts = get_face_vertices(file_bytes)
        BSP_OBJECT.mesh.from_pydata(BSP_OBJECT.vertices, BSP_OBJECT.edges, faces_by_verts)
        BSP_OBJECT.mesh.update()

        main_collection = bpy.data.collections[0]
        main_collection.objects.link(BSP_OBJECT.obj)
        bpy.context.view_layer.objects.active = BSP_OBJECT.obj




    except Exception as e:
        print(f"ERROR loading .BSP file: {e}")
        print(e.__traceback__.tb_frame.f_code.co_filename)
        print(f"LINE: {e.__traceback__.tb_lineno}")
        
    return {'FINISHED'}




    