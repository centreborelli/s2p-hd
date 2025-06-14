# Copyright (C) 2015, Carlo de Franchis <carlo.de-franchis@cmla.ens-cachan.fr>
# Copyright (C) 2015, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
# Copyright (C) 2015, Enric Meinhardt <enric.meinhardt@cmla.ens-cachan.fr>
# Copyright (C) 2015, Julien Michel <julien.michel@cnes.fr>

import subprocess
import tempfile
import numpy as np
import warnings
import rasterio

from s2p import common

# silent rasterio NotGeoreferencedWarning
warnings.filterwarnings("ignore",
                        category=rasterio.errors.NotGeoreferencedWarning)


def image_tile_mask(x, y, w, h, roi_gml=None, cld_gml=None, raster_mask=None,
                    img_shape=None, border_margin=10):
    """
    Compute a validity mask for an image tile from vector/raster image masks.

    Args:
        x, y, w, h (ints): top-left pixel coordinates and size of the tile
        roi_gml (str): path to a gml file containing a mask defining the valid
            area in the input reference image
        cld_gml (str): path to a gml file containing a mask defining the cloudy
            areas in the input reference image
        raster_mask (str): path to a raster mask file
        img_shape (tuple): height and width of the reference input (full) image
        border_margin (int): width, in pixels, of a stripe of pixels to discard
            along the reference input image borders

    Returns:
        2D array containing the output binary mask. 0 indicate masked pixels, 1
        visible pixels.
    """
    x, y, w, h = map(int, (x, y, w, h))

    # coefficients of the transformation associated to the crop
    H = common.matrix_translation(-x, -y)
    hij = ' '.join([str(el) for el in H.flatten()])

    mask = np.ones((h, w), dtype=bool)

    if roi_gml is not None:  # image domain mask (polygons)
        tmp = tempfile.NamedTemporaryFile()
        subprocess.check_call('cldmask %d %d -h "%s" %s %s' % (w, h, hij,
                                                               roi_gml, tmp.name),
                              shell=True)
        with rasterio.open(tmp.name, 'r') as f:
            mask = np.logical_and(mask, f.read().squeeze().astype(bool))
        tmp.close()

        if not mask.any():
            return mask

    if cld_gml is not None:  # cloud mask (polygons)
        tmp = tempfile.NamedTemporaryFile()
        subprocess.check_call('cldmask %d %d -h "%s" %s %s' % (w, h, hij,
                                                               cld_gml, tmp.name),
                              shell=True)
        with rasterio.open(tmp.name, 'r') as f:
            mask = np.logical_and(mask, ~f.read().squeeze().astype(bool))
        tmp.close()

        if not mask.any():
            return mask

    if raster_mask is not None:
        with rasterio.open(raster_mask, 'r') as f:
            mask = np.logical_and(mask, f.read(window=((y, y+h), (x, x+w)),
                                               boundless=True).squeeze())
        if not mask.any():
            return mask

    # image borders mask
    if img_shape is not None and border_margin != 0:
        mask[:max(0, border_margin - y), :] = 0
        mask[:, :max(0, border_margin - x)] = 0
        mask[max(0, img_shape[0] - border_margin - y):, :] = 0
        mask[:, max(0, img_shape[1] - border_margin - x):] = 0

    return mask


def erosion(out, msk, radius):
    """
    Erodes the accepted regions (ie eliminates more pixels)

    Args:
        out: path to the ouput mask image file
        msk: path to the input mask image file
        radius (in pixels): size of the disk used for the erosion
    """
    if radius >= 2:
        common.run('morsi disk%d erosion %s %s' % (int(radius), msk, out))