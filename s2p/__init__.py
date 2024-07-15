#!/usr/bin/env python

# s2p - Satellite Stereo Pipeline
# Copyright (C) 2015, Carlo de Franchis <carlo.de-franchis@polytechnique.org>
# Copyright (C) 2015, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
# Copyright (C) 2015, Enric Meinhardt <enric.meinhardt@cmla.ens-cachan.fr>
# Copyright (C) 2015, Julien Michel <julien.michel@cnes.fr>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os.path
import json
import multiprocessing
import tempfile
import logging
from typing import List
import multiprocessing

import numpy as np
import rasterio
import rasterio.merge
from plyflatten import plyflatten_from_plyfiles_list


from s2p import common
from s2p import parallel
from s2p import geographiclib
from s2p import initialization
from s2p import pointing_accuracy
from s2p import rectification
from s2p import block_matching
from s2p import masking
from s2p import ply
from s2p import triangulation
from s2p import fusion
from s2p import visualisation
from s2p import config
from s2p.tile import Tile
from .gpu_memory_manager import GPUMemoryManager


logger = logging.getLogger(__name__)


def pointing_correction(cfg, tile: Tile, i) -> bool:
    """
    Compute the translation that corrects the pointing error on a pair of tiles.

    Args:
        tile: Tile containing the information needed to process the tile
        i: index of the processed pair
    """
    x, y, w, h = tile.coordinates
    out_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    img1 = cfg['images'][0]['img']
    rpc1 = cfg['images'][0]['rpcm']
    img2 = cfg['images'][i]['img']
    rpc2 = cfg['images'][i]['rpcm']

    # correct pointing error
    logger.info('correcting pointing on tile {} {} pair {}...'.format(x, y, i))
    method = 'relative' if cfg['relative_sift_match_thresh'] is True else 'absolute'
    try:
        A, m = pointing_accuracy.compute_correction(
            cfg, img1, img2, rpc1, rpc2, x, y, w, h, method,
            cfg['sift_match_thresh'], cfg['max_pointing_error'],
            cfg['n_gcp_per_axis']
        )
        if A is not None:  # A is the correction matrix
            np.savetxt(os.path.join(out_dir, 'pointing.txt'), A, fmt='%6.3f')
        if m is not None:  # m is the list of sift matches
            np.savetxt(os.path.join(out_dir, 'sift_matches.txt'), m, fmt='%9.3f')
            np.savetxt(os.path.join(out_dir, 'center_keypts_sec.txt'),
                       np.mean(m[:, 2:], 0), fmt='%9.3f')
            if cfg['debug']:
                visualisation.plot_matches(cfg, img1, img2, rpc1, rpc2, m,
                                           os.path.join(out_dir,
                                                        'sift_matches_pointing.png'),
                                           x, y, w, h)
        return True  ## success
    except Exception:
        # pointing accuracy can fail because one of the images is empty
        # in this case, we return success = False and the tile will be removed 
        # from the pipeline 
        logger.error('pointing_accuracy.compute_correction has failed: tile: {} {}'.format(*tile.coordinates[0:2]))

        return False ## not success


def global_pointing_correction(cfg, tiles: List[Tile]) -> None:
    """
    Compute the global pointing corrections for each pair of images.

    Args:
        tiles: list of tiles
    """
    for i in range(1, len(cfg['images'])):
        out = os.path.join(cfg['out_dir'], 'global_pointing_pair_%d.txt' % i)
        l = [os.path.join(t.dir, 'pair_%d' % i) for t in tiles]
        np.savetxt(out, pointing_accuracy.global_from_local(l),
                   fmt='%12.6f')
        if cfg['clean_intermediate']:
            for d in l:
                common.remove(os.path.join(d, 'center_keypts_sec.txt'))


def rectification_pair(cfg, tile: Tile, i: int) -> bool:
    """
    Rectify a pair of images on a given tile.

    Args:
        tile: Tile containing the information needed to process a tile.
        i: index of the processed pair
    """
    out_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    x, y, w, h = tile.coordinates
    img1 = cfg['images'][0]['img']
    rpc1 = cfg['images'][0]['rpcm']
    img2 = cfg['images'][i]['img']
    rpc2 = cfg['images'][i]['rpcm']
    pointing = os.path.join(cfg['out_dir'],
                            'global_pointing_pair_{}.txt'.format(i))

    logger.info('rectifying tile {} {} pair {}...'.format(x, y, i))
    try:
        A = np.loadtxt(os.path.join(out_dir, 'pointing.txt'))
    except IOError:
        A = np.loadtxt(pointing)
    try:
        m = np.loadtxt(os.path.join(out_dir, 'sift_matches.txt'))
    except IOError:
        m = None

    cur_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    for n in tile.neighborhood_dirs:
        nei_dir = os.path.join(tile.dir, n, 'pair_{}'.format(i))
        if os.path.exists(nei_dir) and not os.path.samefile(cur_dir, nei_dir):
            sift_from_neighborhood = os.path.join(nei_dir, 'sift_matches.txt')
            try:
                m_n = np.loadtxt(sift_from_neighborhood)
                # added sifts in the ellipse of semi axes : (3*w/4, 3*h/4)
                m_n = m_n[np.where(np.linalg.norm([(m_n[:, 0] - (x + w/2)) / w,
                                                   (m_n[:, 1] - (y + h/2)) / h],
                                                  axis=0) < 3/4)]
                if m is None:
                    m = m_n
                else:
                    m = np.concatenate((m, m_n))
            except IOError:
                logger.warning('%s does not exist' % sift_from_neighborhood)

    rect1 = os.path.join(out_dir, 'rectified_ref.tif')
    rect2 = os.path.join(out_dir, 'rectified_sec.tif')
    H1, H2, disp_min, disp_max, success = rectification.rectify_pair(cfg, img1, img2,
                                                                     rpc1, rpc2,
                                                                     x, y, w, h,
                                                                     rect1, rect2, A, m,
                                                                     method=cfg['rectification_method'],
                                                                     hmargin=cfg['horizontal_margin'],
                                                                     vmargin=cfg['vertical_margin'])

    if success:
        np.savetxt(os.path.join(out_dir, 'H_ref.txt'), H1, fmt='%12.6f')
        np.savetxt(os.path.join(out_dir, 'H_sec.txt'), H2, fmt='%12.6f')
        np.savetxt(os.path.join(out_dir, 'disp_min_max.txt'), [disp_min, disp_max],
                   fmt='%3.1f')

    return success


def disparity_range_check(cfg, tile: Tile, i: int):
    """
    Reason about the estimated disparity ranges for all the tiles and update them if needed

    Args:
        tile: dictionary containing the information needed to process a tile.
        i: index of the processed pair
    Returns:
        True if the tile passes the test False otherwise
    """
    out_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    x, y, w, h = tile.coordinates
    img1 = cfg['images'][0]['img']
    rpc1 = cfg['images'][0]['rpcm']
    img2 = cfg['images'][i]['img']
    rpc2 = cfg['images'][i]['rpcm']
    pointing = os.path.join(cfg['out_dir'],
                            'global_pointing_pair_{}.txt'.format(i))

    disp_min, disp_max =  np.loadtxt (os.path.join(out_dir, 'disp_min_max.txt'))

    try:
        A = np.loadtxt(os.path.join(out_dir, 'pointing.txt'))
    except IOError:
        A = np.loadtxt(pointing)
    try:
        m = np.loadtxt(os.path.join(out_dir, 'sift_matches.txt'))
    except IOError:
        m = None

    # TODO: reason about the disparity range of the current tile based on the range of neighboring tiles
    if disp_max - disp_min > 100:
        logger.info('checking tile {} {} pair {}... {} {}'.format(x, y, i, disp_min, disp_max))


    for n in tile.neighborhood_dirs:
        nei_dir = os.path.join(tile.dir, n, 'pair_{}'.format(i))
        if os.path.exists(nei_dir) and not os.path.samefile(out_dir, nei_dir):
            sift_from_neighborhood = os.path.join(nei_dir, 'sift_matches.txt')
            dmin_dmax_from_neighborhood = os.path.join(nei_dir, 'disp_min_max.txt')
            # TODO continue this

    # This is a very simple heuristic test. If the disparity range is > 512 something is wrong with the tile
    if disp_max-disp_min > w/2:
        return False
    else:
        return True


def stereo_matching(cfg, tile: Tile, i: int, gpu_mem_manager: GPUMemoryManager) -> None:
    """
    Compute the disparity of a pair of images on a given tile.

    Args:
        tile: Tile containing the information needed to process a tile.
        i: index of the processed pair
    """
    out_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    x, y = tile.coordinates[:2]

    logger.info('estimating disparity on tile {} {} pair {}...'.format(x, y, i))
    rect1 = os.path.join(out_dir, 'rectified_ref.tif')
    rect2 = os.path.join(out_dir, 'rectified_sec.tif')
    disp = os.path.join(out_dir, 'rectified_disp.tif')
    mask = os.path.join(out_dir, 'rectified_mask.png')
    disp_min, disp_max = np.loadtxt(os.path.join(out_dir, 'disp_min_max.txt'))

    try:
        # block_matching might fail (due to timeout)
        block_matching.compute_disparity_map(cfg, rect1, rect2, disp, mask,
                                             cfg['matching_algorithm'], disp_min,
                                             disp_max, timeout=cfg['mgm_timeout'],
                                             max_disp_range=cfg['max_disp_range'],
                                             gpu_mem_manager=gpu_mem_manager)

        # add margin around masked pixels
        masking.erosion(mask, mask, cfg['msk_erosion'])
    except Exception:
        # in case of timeout we should take note
        # TODO: take note of the failed block matching
        logger.exception('block_matching.compute_disparity_map has failed:')

    if cfg['clean_intermediate']:
        if len(cfg['images']) > 2:
            common.remove(rect1)
        common.remove(rect2)
#        common.remove(os.path.join(out_dir, 'disp_min_max.txt'))


def disparity_to_height(cfg, tile: Tile, i: int) -> None:
    """
    Compute a height map from the disparity map of a pair of image tiles.

    Args:
        tile: Tile containing the information needed to process a tile.
        i: index of the processed pair.
    """
    out_dir = os.path.join(tile.dir, 'pair_{}'.format(i))
    x, y, w, h = tile.coordinates

    logger.info('triangulating tile {} {} pair {}...'.format(x, y, i))
    rpc1 = cfg['images'][0]['rpcm']
    rpc2 = cfg['images'][i]['rpcm']
    H_ref = np.loadtxt(os.path.join(out_dir, 'H_ref.txt'))
    H_sec = np.loadtxt(os.path.join(out_dir, 'H_sec.txt'))
    disp = os.path.join(out_dir, 'rectified_disp.tif')
    mask = os.path.join(out_dir, 'rectified_mask.png')
    mask_orig = os.path.join(tile.dir, 'mask.tif')
    pointing = os.path.join(cfg['out_dir'],
                            'global_pointing_pair_{}.txt'.format(i))

    with rasterio.open(disp, 'r') as f:
        disp_img = f.read().squeeze()
    with rasterio.open(mask, 'r') as f:
        mask_rect_img = f.read().squeeze()
    with rasterio.open(mask_orig, 'r') as f:
        mask_orig_img = f.read().squeeze()
    height_map = triangulation.height_map(x, y, w, h, rpc1, rpc2, H_ref, H_sec,
                                          disp_img, mask_rect_img,
                                          mask_orig_img,
                                          A=np.loadtxt(pointing))

    # write height map to a file
    common.rasterio_write(os.path.join(out_dir, 'height_map.tif'), height_map)

    if cfg['clean_intermediate']:
        common.remove(H_ref)
        common.remove(H_sec)
        common.remove(disp)
        common.remove(mask)


def disparity_to_ply(cfg, tile: Tile) -> None:
    """
    Compute a point cloud from the disparity map of a pair of image tiles.

    This function is called by s2p.main only if there are two input images (not
    three).

    Args:
        tile: Tile containing the information needed to process a tile.
    """
    out_dir = tile.dir
    ply_file = os.path.join(out_dir, 'cloud.ply')
    x, y, w, h = tile.coordinates
    rpc1 = cfg['images'][0]['rpcm']
    rpc2 = cfg['images'][1]['rpcm']

    logger.info('triangulating tile {} {}...'.format(x, y))
    H_ref = os.path.join(out_dir, 'pair_1', 'H_ref.txt')
    H_sec = os.path.join(out_dir, 'pair_1', 'H_sec.txt')
    pointing = os.path.join(cfg['out_dir'], 'global_pointing_pair_1.txt')
    disp = os.path.join(out_dir, 'pair_1', 'rectified_disp.tif')
    extra = os.path.join(out_dir, 'pair_1', 'rectified_disp_confidence.tif')
    if not os.path.exists(extra):    # confidence file not always generated
        extra = ''
    mask_rect = os.path.join(out_dir, 'pair_1', 'rectified_mask.png')
    mask_orig = os.path.join(out_dir, 'mask.tif')

    # first check if disp exists for this tile
    if os.path.exists(disp) is False:
        #TODO: take note of the missing tile and move to the next
        logger.error(f'input file: {disp}')
        return

    # prepare the image needed to colorize point cloud
    if cfg['images'][0]['clr']:
        # we want colors image and rectified_ref.tif to have the same size
        with rasterio.open(os.path.join(out_dir, 'pair_1', 'rectified_ref.tif')) as f:
            ww, hh = f.width, f.height

        colors_path = tempfile.NamedTemporaryFile()
        common.image_apply_homography(colors_path.name, cfg['images'][0]['clr'],
                                      np.loadtxt(H_ref), ww, hh)
        with rasterio.open(colors_path.name, "r") as f:
            colors = f.read()
        colors_path.close()

    else:
        with rasterio.open(os.path.join(out_dir, 'pair_1', 'rectified_ref.tif')) as f:
            img = f.read()
        colors = common.linear_stretching_and_quantization_8bit(img)

    # compute the point cloud
    with rasterio.open(disp, 'r') as f:
        disp_img = f.read().squeeze()
    with rasterio.open(mask_rect, 'r') as f:
        mask_rect_img = f.read().squeeze()
    with rasterio.open(mask_orig, 'r') as f:
        mask_orig_img = f.read().squeeze()

    out_crs = geographiclib.pyproj_crs(cfg['out_crs'])
    xyz_array, err = triangulation.disp_to_xyz(rpc1, rpc2,
                                               np.loadtxt(H_ref), np.loadtxt(H_sec),
                                               disp_img, mask_rect_img,
                                               img_bbx=(x, x+w, y, y+h),
                                               mask_orig=mask_orig_img,
                                               A=np.loadtxt(pointing),
                                               out_crs=out_crs)

    # 3D filtering
    gsd_radius = cfg['3d_filtering_radius_gsd']
    fillfactor = cfg['3d_filtering_fill_factor']
    valid_in = np.sum(np.all(np.isfinite(xyz_array.reshape(-1, 3)), axis=1))
    if gsd_radius  and  fillfactor:
        r = gsd_radius * cfg['gsd']    # compute radius in meters
        n = int(fillfactor * 2*3.14*gsd_radius**2)  # fraction of the disk 
        triangulation.filter_xyz(xyz_array, r, n, cfg['gsd'])

    # check result
    valid_out = np.sum(np.all(np.isfinite(xyz_array.reshape(-1, 3)), axis=1))
    if valid_out < valid_in//10:
        logger.warning("triangulation.filter_xyz with params {} has conserved only {} out of {}".format((r, n, cfg['gsd']), valid_out, valid_in))

    proj_com = "CRS {}".format(cfg['out_crs'])
    try:
        triangulation.write_to_ply(ply_file, xyz_array, colors, proj_com, confidence=extra)
    except Exception:
        logger.error('triangulation.write_to_ply has failed: tile: {} {}'.format(*tile.coordinates[0:2]))


    if cfg['clean_intermediate']:
        common.remove(H_ref)
        common.remove(H_sec)
        common.remove(disp)
        common.remove(mask_rect)
        common.remove(mask_orig)
        common.remove(os.path.join(out_dir, 'pair_1', 'rectified_ref.tif'))


def mean_heights(cfg, tile: Tile) -> None:
    w, h = tile.coordinates[2:]
    n = len(cfg['images']) - 1
    maps = np.empty((h, w, n))
    for i in range(n):
        try:
            with rasterio.open(os.path.join(tile.dir, 'pair_{}'.format(i + 1),
                                            'height_map.tif'), 'r') as f:
                maps[:, :, i] = f.read(1)
        except RuntimeError:  # the file is not there
            maps[:, :, i] *= np.nan

    validity_mask = maps.sum(axis=2)  # sum to propagate nan values
    validity_mask += 1 - validity_mask  # 1 on valid pixels, and nan on invalid

    # save the n mean height values to a txt file in the tile directory
    np.savetxt(os.path.join(tile.dir, 'local_mean_heights.txt'),
               [np.nanmean(validity_mask * maps[:, :, i]) for i in range(n)])


def global_mean_heights(cfg, tiles: List[Tile]) -> None:
    local_mean_heights = [np.loadtxt(os.path.join(t.dir, 'local_mean_heights.txt'))
                          for t in tiles]
    global_mean_heights = np.nanmean(local_mean_heights, axis=0)
    for i in range(len(cfg['images']) - 1):
        np.savetxt(os.path.join(cfg['out_dir'],
                                'global_mean_height_pair_{}.txt'.format(i+1)),
                   [global_mean_heights[i]])


def heights_fusion(cfg, tile: Tile) -> None:
    """
    Merge the height maps computed for each image pair and generate a ply cloud.

    Args:
        tile: Tile that provides all you need to process a tile
    """
    tile_dir = tile.dir
    height_maps = [os.path.join(tile_dir, 'pair_%d' % (i + 1), 'height_map.tif')
                   for i in range(len(cfg['images']) - 1)]

    # remove spurious matches
    if cfg['cargarse_basura']:
        for img in height_maps:
            common.cargarse_basura(img, img)

    # load global mean heights
    global_mean_heights = []
    for i in range(len(cfg['images']) - 1):
        x = np.loadtxt(os.path.join(cfg['out_dir'],
                                    'global_mean_height_pair_{}.txt'.format(i+1)))
        global_mean_heights.append(x)

    # merge the height maps (applying mean offset to register)
    fusion.merge_n(os.path.join(tile_dir, 'height_map.tif'), height_maps,
                   global_mean_heights, averaging=cfg['fusion_operator'],
                   threshold=cfg['fusion_thresh'], debug=cfg['debug'])

    if cfg['clean_intermediate']:
        for f in height_maps:
            common.remove(f)


def heights_to_ply(cfg, tile: Tile) -> None:
    """
    Generate a ply cloud.

    Args:
        tile: a Tile that provides all you need to process a tile
    """
    # merge the n-1 height maps of the tile (n = nb of images)
    heights_fusion(cfg, tile)

    # compute a ply from the merged height map
    out_dir = tile.dir
    x, y, w, h = tile.coordinates
    plyfile = os.path.join(out_dir, 'cloud.ply')
    height_map = os.path.join(out_dir, 'height_map.tif')

    if cfg['images'][0]['clr']:
        with rasterio.open(cfg['images'][0]['clr'], "r") as f:
            colors = f.read(window=((y, y + h), (x, x + w)))
    else:
        with rasterio.open(cfg['images'][0]['img'], "r") as f:
            colors = f.read(window=((y, y + h), (x, x + w)))

        colors = common.linear_stretching_and_quantization_8bit(colors)

    out_crs = geographiclib.pyproj_crs(cfg['out_crs'])
    xyz_array = triangulation.height_map_to_xyz(height_map,
                                                cfg['images'][0]['rpcm'], x, y,
                                                out_crs)

    # 3D filtering
    gsd_radius = cfg['3d_filtering_radius_gsd']
    fillfactor = cfg['3d_filtering_fill_factor']
    if gsd_radius  and  fillfactor:
        r = gsd_radius * cfg['gsd']    # compute radius in meters
        n = int(fillfactor * 2*3.14*gsd_radius**2)  # fraction of the disk 
        triangulation.filter_xyz(xyz_array, r, n, cfg['gsd'])


    proj_com = "CRS {}".format(cfg['out_crs'])
    triangulation.write_to_ply(plyfile, xyz_array, colors, proj_com)

    if cfg['clean_intermediate']:
        common.remove(height_map)
        common.remove(os.path.join(out_dir, 'mask.tif'))


def plys_to_dsm(cfg, tile: Tile) -> None:
    """
    Generates DSM from plyfiles (cloud.ply)

    Args:
        tile: a dictionary that provides all you need to process a tile
    """
    out_dsm = os.path.join(tile.dir, 'dsm.tif')
    out_conf = os.path.join(tile.dir, 'confidence.tif')
    out_dsm_filtered = os.path.join(tile.dir, 'dsm-filtered.tif')
    r = cfg['dsm_resolution']

    in_ply = os.path.join(tile.dir, 'cloud.ply')
    # first check if ply exists (it might not exist because of a failed blockmatching)
    if not os.path.exists(in_ply):
        # TODO: take note of the missing part of the DSM
        logger.error(f'missing input file: {in_ply}')
        return

    # compute the point cloud x, y bounds
    points, _ = ply.read_3d_point_cloud_from_ply(in_ply)
    if len(points) == 0:
        # TODO: take note of the missing part of the DSM
        logger.error(f'plys_to_dsm no points in file: {in_ply}')
        return

    xmin, ymin, *_ = np.min(points, axis=0)
    xmax, ymax, *_ = np.max(points, axis=0)

    # compute xoff, yoff, xsize, ysize on a grid of unit r
    xoff = np.floor(xmin / r) * r
    xsize = int(1 + np.floor((xmax - xoff) / r))

    yoff = np.ceil(ymax / r) * r
    ysize = int(1 - np.floor((ymin - yoff) / r))

    roi = xoff, yoff, xsize, ysize

    # since some tiles might have failed we test for the neighborhood tiles before feeding them to merge
    clouds = []
    for n_dir in tile.neighborhood_dirs:
        nply = os.path.join(tile.dir, n_dir, 'cloud.ply')
        if os.path.exists(nply):
            clouds.append(nply)

    # this option controls the type of aggregation
    # TODO: this interface is VERY VERY ugly AND FRAGILE and will be reworked within a new plyflatten
    use_max_aggregation = cfg['dsm_aggregation_with_max']
    raster, profile = plyflatten_from_plyfiles_list(clouds,
                                                    resolution=r,
                                                    roi=roi,
                                                    radius=cfg['dsm_radius'],
                                                    sigma=cfg['dsm_sigma'],
                                                    amax=use_max_aggregation
                                                    )

    # save output image with utm georeferencing
    if use_max_aggregation:
        # the raster channel where the max is stored is #5 or #4 depending on the presence of the confidence
        if (raster.shape[-1] % 5) == 0:
            dsm = raster[:, :, 5]
        else: 
            dsm = raster[:, :, 4]
    else:
        # the average raster is stored in #0
        dsm = raster[:, :, 0]

    common.rasterio_write(out_dsm, dsm, profile=profile)

    # export confidence (optional)
    # note that the plys are assumed to contain the fields:
    # [x(float32), y(float32), z(float32), r(uint8), g(uint8), b(uint8), confidence(optional, float32)]
    # so the raster has 4 or 5 columns: [z, r, g, b, confidence (optional)]
    if raster.shape[-1] == 5:
        common.rasterio_write(out_conf, raster[:, :, 4], profile=profile)



    # fill the small gaps in the dsm
    if maxsize := cfg['fill_dsm_holes_smaller_than']:
        import s2p.demtk
        from s2p.specklefilter import specklefilter

        # compute the mask where the interpolation will not be applied
        # (masked_nans is a mask of large connected components)
        z = np.isnan(dsm).astype(np.float32)
        z[z == 0] = np.nan
        masked_nans = specklefilter(z, maxsize, 0) == 1

        # apply the interpolation after removing the masked areas
        dsm[masked_nans] = -1000
        filtered = s2p.demtk.descending_neumann_interpolation(dsm).astype(np.float32)
        filtered[masked_nans] = np.nan

        common.rasterio_write(out_dsm_filtered, filtered, profile=profile)


def global_dsm(cfg, tiles: List[Tile]) -> None:
    """
    Merge tilewise DSMs and confidence maps in a global DSM and confidence map.
    """
    bounds = None
    if "roi_geojson" in cfg:
        ll_poly = geographiclib.read_lon_lat_poly_from_geojson(cfg["roi_geojson"])
        pyproj_crs = geographiclib.pyproj_crs(cfg["out_crs"])
        bounds = geographiclib.crs_bbx(ll_poly, pyproj_crs,
                                       align=cfg["dsm_resolution"])

    creation_options = {"tiled": True,
                        "blockxsize": 256,
                        "blockysize": 256,
                        "compress": "deflate",
                        "BIGTIFF": "IF_SAFER",
                        "COPY_SRC_OVERVIEWS": "YES",
                        "predictor": 2}

    dsms = []
    dsms_filtered = []
    confidence_maps = []

    for t in tiles:
        d = os.path.join(t.dir, "dsm.tif")
        if os.path.exists(d):
            dsms.append(d)

        f = os.path.join(t.dir, "dsm-filtered.tif")
        if os.path.exists(f):
            dsms_filtered.append(f)

        c = os.path.join(t.dir, "confidence.tif")
        if os.path.exists(c):
            confidence_maps.append(c)

    if dsms:
        rasterio.merge.merge(dsms,
                             bounds=bounds,
                             res=cfg["dsm_resolution"],
                             nodata=np.nan,
                             indexes=[1],
                             dst_path=os.path.join(cfg["out_dir"], "dsm.tif"),
                             dst_kwds=creation_options)

    if dsms_filtered:
        rasterio.merge.merge(dsms_filtered,
                             bounds=bounds,
                             res=cfg["dsm_resolution"],
                             nodata=np.nan,
                             indexes=[1],
                             dst_path=os.path.join(cfg["out_dir"], "dsm-filtered.tif"),
                             dst_kwds=creation_options)

    if confidence_maps:
        rasterio.merge.merge(confidence_maps,
                             bounds=bounds,
                             res=cfg["dsm_resolution"],
                             nodata=np.nan,
                             indexes=[1],
                             dst_path=os.path.join(cfg["out_dir"], "confidence.tif"),
                             dst_kwds=creation_options)


def main(user_cfg, start_from=0):
    """
    Launch the s2p pipeline with the parameters given in a json file.

    Args:
        user_cfg: user config dictionary
        start_from: the step to start from (default: 0)
    """
    common.reset_elapsed_time()

    # setup logger to stderr
    # (loggers per tiles are set in parallel.py)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    f = logging.Formatter('%(message)s')
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(f)
    root.addHandler(h)

    # s2p is already using (processed-based) parallelism when needed
    os.environ['GDAL_NUM_THREADS'] = "1"
    os.environ['OMP_NUM_THREADS'] = "1"

    cfg = config.get_default_config()
    initialization.build_cfg(cfg, user_cfg)
    initialization.make_dirs(cfg)

    # multiprocessing setup
    nb_workers = cfg['max_processes'] or multiprocessing.cpu_count()  # nb of available cores

    tw, th = initialization.adjust_tile_size(cfg)
    tiles_txt = os.path.join(cfg['out_dir'], 'tiles.txt')
    if start_from <= 1:
        tiles = initialization.tiles_full_info(cfg, tw, th, tiles_txt, create_masks=True)
    else: # skip mask creation if already done
        tiles = initialization.tiles_full_info(cfg, tw, th, tiles_txt, create_masks=False)
    if not tiles:
        logger.error('the ROI is not seen in two images or is totally masked.')
        sys.exit(1)

    if start_from > 0:
        assert os.path.exists(tiles_txt), "start_from set to {} but tiles.txt is not found in '{}'. Make sure this is" \
                                          " the output directory of a previous run.".format(start_from, cfg['out_dir'])
    else:
        # initialisation: write the list of tilewise json files to outdir/tiles.txt
        with open(tiles_txt, 'w') as f:
            for t in tiles:
                f.write(t.json)
                f.write('\n')

    n = len(cfg['images'])
    tiles_pairs = [(cfg, t, i) for i in range(1, n) for t in tiles]
    tiles_with_cfg = [(cfg, t) for t in tiles]
    timeout = cfg['timeout']

    # local-pointing step:
    if start_from <= 1:
        logger.info('1) correcting pointing locally...')
        successes = parallel.launch_calls(cfg, pointing_correction, tiles_pairs, nb_workers,
                              timeout=timeout)

        # update the tiles removing the discarded tiles
        tiles_pairs = [x for x, b in zip(tiles_pairs, successes) if b]

    # global-pointing step:
    if start_from <= 2:
        logger.info('2) correcting pointing globally...')
        global_pointing_correction(cfg, tiles)
        common.print_elapsed_time()

    # rectification step:
    if start_from <= 3:
        logger.info('3) rectifying tiles...')
        successes = parallel.launch_calls(cfg, rectification_pair, tiles_pairs, nb_workers,
                              timeout=timeout)

        # update the tiles removing the discarded tiles
        tiles_pairs = [x for x, b in zip(tiles_pairs, successes) if b]

    # disparity range reasoning step: (WIP)
    if start_from <= 4:
        logger.info('4) reason about the disparity ranges... (WIP)')
        # extra step checking the disparity range
        # verity if the disparity range of a tile is not too different from its neighbors
        tiles_usefulnesses = parallel.launch_calls(cfg, disparity_range_check, tiles_pairs, nb_workers,
                              timeout=timeout)
        # some feedback
        for x, b in zip(tiles_pairs, tiles_usefulnesses):
            if not b: logger.info('  removed tile: %s', x[1].dir)

        # update the tiles removing the discarded tiles
        tiles_pairs = [x for x, b in zip(tiles_pairs, tiles_usefulnesses) if b]


    # matching step:
    if start_from <= 4:
        logger.info('4) running stereo matching...')
        if cfg['max_processes_stereo_matching'] is not None:
            nb_workers_stereo = cfg['max_processes_stereo_matching']
        else:
            nb_workers_stereo = nb_workers

        if cfg["gpu_total_memory"] is not None:
            gpu_total_memory = cfg["gpu_total_memory"]
            # keep some space for the CUDA contexts
            gpu_total_memory -= nb_workers_stereo * 120
            gpu_mem_manager = GPUMemoryManager.make_bounded(
                max_memory_in_megabytes=gpu_total_memory,
                mp_context=parallel.get_mp_context(),
            )
        else:
            gpu_mem_manager = GPUMemoryManager.make_unbounded()

        parallel.launch_calls(cfg, stereo_matching, tiles_pairs,
                              nb_workers_stereo,
                              gpu_mem_manager,
                              timeout=timeout)

    ### UPATE TILES_WITH_CFG FROM CURRENT TILES_PAIRS
    tilesdict = dict( [(t.json,t) for _,t,_ in tiles_pairs] )
    tiles_with_cfg = [(cfg,t) for t in tilesdict.values()]

    if start_from <= 5:
        if n > 2:
            # disparity-to-height step:
            logger.info('5a) computing height maps...')
            parallel.launch_calls(cfg, disparity_to_height, tiles_pairs, nb_workers,
                                  timeout=timeout)

            logger.info('5b) computing local pairwise height offsets...')
            parallel.launch_calls(cfg, mean_heights, tiles_with_cfg, nb_workers, timeout=timeout)

            # global-mean-heights step:
            logger.info('5c) computing global pairwise height offsets...')
            global_mean_heights(cfg, tiles)

            # heights-to-ply step:
            logger.info('5d) merging height maps and computing point clouds...')
            parallel.launch_calls(cfg, heights_to_ply, tiles_with_cfg, nb_workers,
                                  timeout=timeout)
        else:
            # triangulation step:
            logger.info('5) triangulating tiles...')
            parallel.launch_calls(cfg, disparity_to_ply, tiles_with_cfg, nb_workers,
                                  timeout=timeout)

    # local-dsm-rasterization step:
    if start_from <= 6:
        logger.info('6) computing DSM by tile...')
        parallel.launch_calls(cfg, plys_to_dsm, tiles_with_cfg, nb_workers, timeout=timeout)

    # global-dsm-rasterization step:
    if start_from <= 7:
        logger.info('7) computing global DSM...')
        global_dsm(cfg, tiles)
    common.print_elapsed_time()
    common.print_elapsed_time(since_first_call=True)


def make_path_relative_to_file(path, f):
    return os.path.join(os.path.abspath(os.path.dirname(f)), path)


def read_tiles(tiles_file):
    outdir = os.path.dirname(tiles_file)

    with open(tiles_file) as f:
        tiles = f.readlines()

    # Strip trailing \n
    tiles = list(map(str.strip, tiles))
    tiles = [os.path.join(outdir, t) for t in tiles]

    return tiles


def read_config_file(config_file):
    """
    Read a json configuration file and interpret relative paths.

    If any input or output path is a relative path, it is interpreted as
    relative to the config_file location (and not relative to the current
    working directory). Absolute paths are left unchanged.
    """
    with open(config_file, 'r') as f:
        user_cfg = json.load(f)

    # output paths
    if not os.path.isabs(user_cfg['out_dir']):
        user_cfg['out_dir'] = make_path_relative_to_file(user_cfg['out_dir'],
                                                         config_file)

    # ROI path
    k = "roi_geojson"
    if k in user_cfg and isinstance(user_cfg[k], str) and not os.path.isabs(user_cfg[k]):
        user_cfg[k] = make_path_relative_to_file(user_cfg[k], config_file)

    if 'exogenous_dem' in user_cfg and user_cfg['exogenous_dem'] is not None:
        if not os.path.isabs(user_cfg['exogenous_dem']):
            user_cfg['exogenous_dem'] = make_path_relative_to_file(user_cfg['exogenous_dem'], config_file)

    # input paths
    for img in user_cfg['images']:
        for d in ['img', 'rpc', 'clr', 'cld', 'roi', 'wat']:
            if d in img and isinstance(img[d], str) and not os.path.isabs(img[d]):
                img[d] = make_path_relative_to_file(img[d], config_file)

    return user_cfg
