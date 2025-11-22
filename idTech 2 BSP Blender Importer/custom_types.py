from dataclasses import dataclass, fields
from typing import List, Any
from pathlib import Path


################# Data types are not always the "C" types, since shorts, etc... are meaningless in Python
########## Physical objects ############
@dataclass
class bsp_face:
    plane: int                  # Index of the plane the face is parallel to
    plane_side: int             # Set if the normal is parallel to the plane normal

    first_edge: int             # Index of the first edge (in the face edge array)
    num_edges: int              # Number of consecutive edges (in the face edge array)

    texture_info: int           # Index of the texture info structure

    lightmap_styles: List[int]  # Styles (bit flags) for the lightmaps
    lightmap_offset: int        # Offset of the lightmap (in bytes) in the lightmap lump

    def __iter__(self):
        return (getattr(self, field.name) for field in fields(self))


@dataclass
class bsp_edge:
    vert_idx_1: int
    vert_idx_2: int

    def __iter__(self):
        return (getattr(self, field.name) for field in fields(self))

    def __reversed__(self):
        # self.vert_idx_1, self.vert_idx_2 = self.vert_idx_2, self.vert_idx_1
        return reversed([self.vert_idx_1, self.vert_idx_2])



@dataclass
class bsp_vertex:
    x: float
    y: float
    z: float

    def __iter__(self):
        return (getattr(self, field.name) for field in fields(self))

    def __hash__(self):
        return hash((self.x, self.y, self.z))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, bsp_vertex):
            return False
        return (self.x == other.x and
                self.y == other.y and
                self.z == other.z)

    def __getitem__(self, key):
        return getattr(self, key)


@dataclass
class bsp_texture_info:
    u_axis: bsp_vertex
    u_offset: float
    v_axis: bsp_vertex
    v_offset: float

    flags: int
    value: int

    texture_name: str
    next_texinfo: int

    def __iter__(self):
        return (getattr(self, field.name) for field in fields(self))

    def __hash__(self):
        return hash((self.u_axis, self.u_offset, self.v_axis, self.v_offset, self.flags, self.value, self.texture_name, self.next_texinfo))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, bsp_texture_info):
            return False
        return (self.u_axis == other.u_axis and
                self.u_offset == other.u_offset and
                self.v_axis == other.v_axis and
                self.v_offset == other.v_offset and
                self.flags == other.flags and
                self.value == other.value and
                self.texture_name == other.texture_name and
                self.next_texinfo == other.next_texinfo)



########## "Logical"/BSP tree objects ############
@dataclass
class bsp_node:
    plane: int                  # Index of the plane that splits this node
    front_child: int            # Index of the front child Node or Leaf (NEGATIVE value indicates Leaf)
    back_child: int             # Index of the back child Node or Leaf (NEGATIVE value indicates Leaf)

    # Bounding box defined by 2 points, the diagonal of a cube
    bbox_min: bsp_vertex
    bbox_max: bsp_vertex

    first_face: int             # Index of the first face (in the face array)
    num_faces: int              # Number of consecutive edges (in the face array)


@dataclass
class bsp_plane:
    normal: bsp_vertex          # A, B, C components of the plane equation
    distance: float             # D component of the plane equation
    type: int                   # PLANe_ANYX, Y, Z - Quake II source comment - not necessary because easily reproduced?


@dataclass
class bsp_leaf:
    brush_or: int

    cluster: int                # -1 for cluster indicates no visibility information
    area: int

    bbox_min: bsp_vertex        # Bounding box minimum
    bbox_max: bsp_vertex        # Bounding box maximum

    first_leaf_face: int        # Index of the first face (in the face leaf array)
    num_leaf_faces: int         # Number of consecutive edges (in the face leaf array)

    first_leaf_brush: int       # Brushes are the objects in the QBSP2 level editor
    num_leaf_brushes: int



@dataclass
class bsp_header:
    magic_number: int           # Must be "IBSP" or 1347633737
    version: int                # Should be 38

    entity_offset: int
    entity_length: int

    planes_offset: int
    planes_length: int

    vertices_offset: int
    vertices_length: int

    visibility_offset: int
    visibility_length: int

    nodes_offset: int
    nodes_length: int

    texture_info_offset: int
    texture_info_length: int

    faces_offset: int
    faces_length: int

    lightmaps_offset: int
    lightmaps_length: int

    leaf_offset: int
    leaf_length: int

    leaf_face_table_offset: int
    leaf_face_table_length: int

    leaf_brush_table_offset: int
    leaf_brush_table_length: int

    edge_offset: int
    edge_length: int

    face_edge_table_offset: int
    face_edge_table_length: int

    models_offset: int
    models_length: int

    brushes_offset: int
    brushes_length: int

    brush_sides_offset: int
    brush_sides_length: int

    pop_offset: int
    pop_length: int

    areas_offset: int
    areas_length: int

    area_portals_offset: int
    area_portals_length: int



class BSP_OBJECT(object):
    folder_path = ""
    name = ""
    obj = {}
    mesh = {}
    header = {}
    vertices = list()
    edges = list()
    faces = list()
    textures = list()

    face_verts_list = list()
    bsp_face_indices = list()

    texture_obj_dict = dict()
    material_texture_dict = dict()
    texture_material_index_dict = dict()
    texture_resolution_dict = dict()

    animation_textures = list()
    lightmap_folder = Path()
    lightmap_images = list()

    @classmethod
    def reset(cls):
        cls.folder_path = ""
        cls.name = ""
        cls.obj = {}
        cls.mesh = {}
        cls.header = {}
        cls.vertices = []
        cls.edges = []
        cls.faces = []
        cls.textures = []
        cls.face_verts_list = []
        cls.bsp_face_indices = []
        cls.texture_obj_dict = {}
        cls.material_texture_dict = {}
        cls.texture_material_index_dict = {}
        cls.texture_resolution_dict = {}
        cls.animation_textures = []
        cls.lightmap_folder = Path()
        cls.lightmap_images = []