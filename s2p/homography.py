import os
from typing import Any

import cffi
import numpy as np


ROOT = os.path.dirname(os.path.abspath(__file__))
LIB_FOLDER = os.path.join(ROOT, "..", "lib")

ffi = cffi.FFI()
ffi.cdef(open(os.path.join(LIB_FOLDER, "libhomography.h")).read())

homography: Any = ffi.dlopen(os.path.join(LIB_FOLDER, "libhomography.so"))
homography.init()


def wrap(array):
    if array.dtype == np.float32:
        typestr = "float*"
    elif array.dtype == np.float64:
        typestr = "double*"
    elif array.dtype == bool:
        typestr = "bool*"
    elif array.dtype == np.int32:
        typestr = "int*"
    elif array.dtype == np.uint16:
        typestr = "uint16_t*"
    else:
        assert False
    return ffi.from_buffer(typestr, array, require_writable=True)


def image_apply_homography(
    out: str,
    im: str,
    H,
    w: int,
    h: int,
    antialiasing: bool = True,
    verbose: bool = False,
):
    """
    Applies an homography to an image.

    Args:
        out: path to the output image file
        im: path to the input image file
        H: numpy array containing the 3x3 homography matrix
        w, h: dimensions (width and height) of the output image

    The output image is defined on the domain [0, w] x [0, h]. Its pixels
    intensities are defined by out(x) = im(H^{-1}(x)).
    """
    homography.run(
        im.encode("utf-8"),
        wrap(H.flatten()),
        out.encode("utf-8"),
        int(w),
        int(h),
        antialiasing,
        verbose,
    )


def points_apply_homography(H, pts):
    """
    Applies an homography to a list of 2D points.

    Args:
        H: numpy array containing the 3x3 homography matrix
        pts: numpy array containing the list of 2D points, one per line

    Returns:
        a numpy array containing the list of transformed points, one per line
    """
    # if the list of points is not a numpy array, convert it
    if type(pts) == list:
        pts = np.array(pts)

    # convert the input points to homogeneous coordinates
    if len(pts[0]) < 2:
        raise ValueError(
            "The input must be a numpy array" "of 2D points, one point per line"
        )
    pts = np.hstack((pts[:, 0:2], pts[:, 0:1] * 0 + 1))

    # apply the transformation
    Hpts = (np.dot(H, pts.T)).T

    # normalize the homogeneous result and trim the extra dimension
    Hpts = Hpts * (1.0 / np.tile(Hpts[:, 2], (3, 1))).T
    return Hpts[:, 0:2]
