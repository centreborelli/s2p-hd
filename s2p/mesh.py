import numpy as np
import rpcm
import utm
from numpy.linalg import norm

def get_nearby_pixels(xyz, i, j, vertices_index):
    p = []
    nvp = 0 # nb of valid pixels in the 4 pixels of interest
    for k in range(2):
        for l in range(2):
            if np.isnan(xyz[j+l, i+k, 2]):
                p.append(np.nan * np.zeros(4))
            else:
                p.append(np.concatenate((xyz[j+l, i+k].flatten(), vertices_index[j+l, i+k].flatten())))
                nvp += 1
    assert(nvp <= 4)
    return np.array(p), nvp

def list_and_index_vertices(xyz, c=None):
    '''
    List and index vertices from an image containing 3d coordinates

    Input:
        - image with 3d coordinates associated with each pixel when available
        - original image (with colour information)

    Outputs:
        - list of vertices (3d coordinates)
        - index of the vertex associated to each pixel when it exists
        - list of vertices colour
   '''
    h, w, _ = xyz.shape
    vertices_index = np.nan * np.zeros((h,w))
    vertices = []
    vc = []
    nv = 0
    for i in range(w):
        for j in range(h):
            if np.isnan(xyz[j,i,0]):
                continue
            vertices_index[j,i] = nv
            vertices.append(xyz[j,i,:])
            if c is not None:
                vc.append(c[:,j,i].flatten())
            nv += 1
    if len(vc) < 1:
        vc = None
    return vertices, vertices_index, vc

def get_vertices_and_faces_lists(xyz, c=None):
    '''
    Create a triangular mesh from an image containing 3d coordinates

    Inputs:
        - xyz: image containing 3d coordinates
        - c: same image but with colour information instead

    Outputs:
        - vertices: list of vertices
        - faces: list of triangular faces
        - colours: list of vertices colour
    '''
    h, w, _ = xyz.shape
    vertices, vertices_index, colours = list_and_index_vertices(xyz, c=c)
    faces = []
    for i in range(w-1):
        for j in range(h-1):
            if np.isnan(xyz[j, i,2]):
                continue

            # We look at 4 pixels (i,j) (i,j+1) (i+1,j) (i+1,j+1) and recover:
            # - their associated vertex index if they are valid pixels
            # - how many are valid
            p, nvp = get_nearby_pixels(xyz, i, j, vertices_index)
            # We need at least 3 valid pixels to add a face to the mesh
            if nvp < 3:
                continue
            # If there are only 3 valid pixels, we add the corresponding face.
            # N.B.: the vertices must be given in counterclockwise order
            # (right-hand rule)
            if nvp == 3:
                if np.isnan(p[1,0]):
                    faces.append(np.array([int(p[0,3]), int(p[3,3]), int(p[2,3])]))
                elif np.isnan(p[2,0]):
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[3,3])]))
                else:
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[2,3])]))
            # If there are 4 valid pixels, we choose the shortest diagonal to
            # divide the square in two triangles
            if nvp == 4:
                if norm(p[0,:3]-p[3,:3]) < norm(p[1,:3]-p[2,:3]):
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[3,3])]))
                    faces.append(np.array([int(p[0,3]), int(p[3,3]), int(p[2,3])]))
                else:
                    faces.append(np.array([int(p[2,3]), int(p[1,3]), int(p[3,3])]))
                    faces.append(np.array([int(p[2,3]), int(p[0,3]), int(p[1,3])]))
    return vertices, faces, colours

def write_mesh_to_coloured_ply(filename_mesh, vertices, faces, c=None, offset=[0., 0., 0.]):
    '''
    Write the mesh to a ply file.

    Inputs:
        - filename_mesh: output file
        - vertices: list of vertices
        - faces: list of faces
        - c: list of vertices colour (grayscale or rgb)

    TODO: add optional property fields
    '''
    if c is not None:
        if len(c[0]) == 1:
            c = [[col[0], col[0], col[0]] for col in c]
        elif len(c[0]) == 2:
            'Invalid number of colour channels for mesh creation. Expected 1, 3 or 4 instead of 2.'
    vertices = [ v - offset for v in vertices]
    with open(filename_mesh, 'w') as file:
        file.write(f'ply\n')
        file.write(f'format ascii 1.0\n')
        file.write(f'comment bare triangulated surface\n')
        file.write(f'element vertex {len(vertices)}\n')
        file.write(f'property float x\n')
        file.write(f'property float y\n')
        file.write(f'property float z\n')
        if c is not None:
            file.write(f'property uchar red\n')
            file.write(f'property uchar green\n')
            file.write(f'property uchar blue\n')
        file.write(f'element face {len(faces)}\n')
        file.write(f'property list uchar int vertex_indices\n')
        file.write(f'end_header\n')
        for i, v in enumerate(vertices):
            if c is None:
                file.write(f'{v[0]} {v[1]} {v[2]}\n')
            else:
                file.write(f'{v[0]} {v[1]} {v[2]} {c[i][0]} {c[i][1]} {c[i][2]}\n')
        for f in faces:
            file.write(f'3 {f[0]} {f[1]} {f[2]}\n')
    return


def filter_faces_using_view_angle(faces, vertices, n, t=0.15):
    '''
    Removes faces unseen by the satellite

    Inputs:
        - faces: list of faces
        - vertices: list of vertices
        - n: satellite direction (orientation: earth to satellite)
        - t: minimum value accepted for the scalar product between face unit
          normal vector and n

    Outputs:
        - list of valid faces
    '''

    faces = [f for f in faces if compute_face_normal(f, vertices)@n > t]
    return faces

def compute_face_normal(f, v):
    '''
    Compute face unit normal vector

    Inputs:
        - f: indices of the three vertices of the face
        - v: list of all vertices

    Outputs:
        - n: face unit normal vector
    '''
    a = v[f[0]]
    b = v[f[1]]
    c = v[f[2]]
    n = np.cross(b-a, c-a)
    n /= norm(n)
    return n

def compute_satellite_direction(filename_rpc, xyz):
    '''
    Compute the direction of the satellite

    Inputs:
        - filename_rpc: satellite image with rpc
        - xyz: associated image with 3d coordinates

    Outputs:
        - n: unit normal vector (orientation: from earth to camera)

    TODO: check if xyz is useful
    '''
    lonlat0 = rpcm.localization(filename_rpc, 0, 0, np.nanmin(xyz[:,:,2]))
    lonlat1 = rpcm.localization(filename_rpc, 0, 0, np.nanmin(xyz[:,:,2] + 1))
    e0, n0, _, _ = utm.from_latlon(lonlat0[1], lonlat0[0])
    e1, n1, _, _ = utm.from_latlon(lonlat1[1], lonlat1[0])
    n = np.array((e1-e0, n1-n0, 1))
    n /= norm(n)
    return n

def main(filename_mesh, xyz, colours=None, offset=[0., 0., 0.], filename_rpc=None, t=0.15):
    vertices, faces, colours = get_vertices_and_faces_lists(xyz, c=colours)
    if filename_rpc:
        n = compute_satellite_direction(filename_rpc, xyz)
        faces = filter_faces_using_view_angle(faces, vertices, n, t=t)
    write_mesh_to_coloured_ply(filename_mesh, vertices, faces, c=colours, offset=offset)
    return


if __name__ == "__main__":
    from sys import argv
    if len(argv) != 4:
        print(f"usage: {argv[0]} xyz colours outmesh")
        exit(1)
    filename_xyz = argv[1]
    filename_colours = argv[2]
    filename_mesh = argv[3]
    xyz = np.load(filename_xyz)
    colours = np.load(filename_colours)
    # TODO: use filtering step (new args: filename_rpc and threshold)
    # TODO: use offset when writing the mesh (use offset=vertices[0] ?)
    # TODO: accept other input formats (tiff for colours in particular)
    main(filename_mesh, xyz, colours)








