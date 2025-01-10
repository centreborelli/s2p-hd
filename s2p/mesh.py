import numpy as np
import rpcm
import utm
from numpy.linalg import norm

#xyz = np.load('/Users/mariedautume/Documents/borelli/mesh/data/xyz.npy')
#c = np.load('/Users/mariedautume/Documents/borelli/mesh/data/colors.npy')
xyzfile = '/Users/mariedautume/Documents/borelli/mesh/data/xyz.npy'
cfile = '/Users/mariedautume/Documents/borelli/mesh/data/colors.npy'


def get_nearby_pixels(xyz, i, j, vertices_index):
    p = []
    nvp = 0
    for k in range(2):
        for l in range(2):
            if np.isnan(xyz[j+l, i+k, 2]):
                p.append(np.nan * np.zeros(4))
            else:
                p.append(np.concatenate((xyz[j+l, i+k].flatten(), vertices_index[j+l, i+k].flatten())))
                nvp += 1
    assert(nvp <= 4)
    return np.array(p), nvp

def list_valid_vertices(xyz, c=None):
    '''
    List and index vertices

    Input:
        - image with 
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
    h, w, _ = xyz.shape
    vertices, vertices_index, colours = list_valid_vertices(xyz, c=c)
    faces = []
    for i in range(w-1):
        for j in range(h-1):
            if np.isnan(xyz[j, i,2]):
                continue
            p, nvp = get_nearby_pixels(xyz, i, j, vertices_index)
            if nvp < 3:
                continue
            if nvp == 3:
                if np.isnan(p[1,0]):
                    faces.append(np.array([int(p[0,3]), int(p[3,3]), int(p[2,3])]))
                elif np.isnan(p[2,0]):                             
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[3,3])]))
                else:                                              
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[2,3])]))
            if nvp == 4:
                if norm(p[0,:3]-p[3,:3]) < norm(p[1,:3]-p[2,:3]):
                    faces.append(np.array([int(p[0,3]), int(p[1,3]), int(p[3,3])]))
                    faces.append(np.array([int(p[0,3]), int(p[3,3]), int(p[2,3])]))
                else:                                              
                    faces.append(np.array([int(p[2,3]), int(p[1,3]), int(p[3,3])]))
                    faces.append(np.array([int(p[2,3]), int(p[0,3]), int(p[1,3])]))
    return vertices, faces, colours

def filter_faces(faces, vertices, n):
    faces = [f for f in faces if compute_face_normal(f, vertices)@n > 0.2]
    return faces

        
    return faces

def write_mesh_to_coloured_ply(vertices, faces, c):
    if len(c[0]) == 1:
        c = [[col[0], col[0], col[0]] for col in c]
    with open('/tmp/mesh.ply', 'w') as file:
        file.write(f'ply\n')
        file.write(f'format ascii 1.0\n')
        file.write(f'comment bare triangulated surface\n')
        file.write(f'element vertex {len(vertices)}\n')
        file.write(f'property float x\n')
        file.write(f'property float y\n')
        file.write(f'property float z\n')
        file.write(f'property uchar red\n')
        file.write(f'property uchar green\n')
        file.write(f'property uchar blue\n')
        file.write(f'element face {len(faces)}\n')
        file.write(f'property list uchar int vertex_indices\n')
        file.write(f'end_header\n')
        for i, v in enumerate(vertices):
            file.write(f'{v[0]} {v[1]} {v[2]} {c[i][0]} {c[i][1]} {c[i][2]}\n')
        for f in faces:
            file.write(f'3 {f[0]} {f[1]} {f[2]}\n') 
    return

def compute_face_normal(f, v):
    a = v[f[0]]
    b = v[f[1]]
    c = v[f[2]]
    n = np.cross(b-a, c-a)
    n /= norm(n)
    return n

def compute_satellite_direction(imfile, xyz):
    lonlat0 = rpcm.localization(imfile, 0, 0, np.nanmin(xyz[:,:,2]))
    lonlat1 = rpcm.localization(imfile, 0, 0, np.nanmin(xyz[:,:,2] + 1))
    e0, n0, _, _ = utm.from_latlon(lonlat0[1], lonlat0[0])
    e1, n1, _, _ = utm.from_latlon(lonlat1[1], lonlat1[0])
    n = np.array((e1-e0, n1-n0, 1))
    n /= norm(n)
    return n










