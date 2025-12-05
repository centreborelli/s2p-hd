
Configuration file config.json 
==============================

The json that controls the execution of s2p-hd, should be set up for each 3D reconstruction.
This document collects the main pipeline parameters. 
Additional information about the parameters can be found as comments in the file  s2p/config.py

This is the base content for s2p-hd. 
-----------------------------------------------------------
```json
{
  "out_dir" : "output_pair",
  "images" : [
      {"img" : "img_01.tif", "rpc" : "rpc_01.rpc"},
      {"img" : "img_02.tif", "rpc" : "rpc_02.rpc"}
  ],
  "roi" : {
      "x" : 1000,
      "y" : 1000,
      "w" : 10000,
      "h" : 10000
  },
  "full_img": false,
  "horizontal_margin": 20,
  "vertical_margin": 20,
  "tile_size" : 700,
  "disp_range_method" : "sift",
  "sift_use_opencv_implementation" : true,
  "matching_algorithm" : "stereosgm_gpu",
  "postprocess_stereosgm_gpu" : true,
  "census_ncc_win" : 7, 
  "gpu_total_memory" : 8000,
  "max_processes_stereo_matching" : 8,
  "stereo_speckle_filter" : 50,
  "fill_dsm_holes_smaller_than" : 10000,
  "msk_erosion": 0,
  "dsm_resolution": 0.5,
  "dsm_aggregation_with_max": true,
  "3d_filtering_radius_gsd": 5,
  "3d_filtering_fill_factor": 0.25
}
```
-----------------------------------------------------------



Detailed description of the main configuration parameters and recommended values

| Parameters                                    | Description                            |
|-----------------------------------------------|----------------------------------------|
| "out_dir" : "output_pair",                    | relative path to the output directory  | 
|-----------------------------------------------|----------------------------------------|
| “gpu_total_memory” : 8000,                    | the available GPU memory (megas), and  |
| “max_processes_stereo_matching” : 8,          | the maximum number of GPU correlator   |
|                                               | processes (about one per giga)         |
|-----------------------------------------------|----------------------------------------|
| “max_processes” : 32,                         | maximum number of parallel processes   |
|                                               | (set as the number of cores)           |
|-----------------------------------------------|----------------------------------------|
| "images" : [                                  | relative paths to the images generated |
|  {"img" : "img_01.tif", “rpc” : “rpc_01.rpc”},| by the convert-to-tif script, and      |
|  {"img" : "img_02.tif", “rpc” : “rpc_02.rpc”} | optionally the RPC files if not coded  |
| ],                                            | in the image                           |
|-----------------------------------------------|----------------------------------------|
| "roi" : {                                     | specification of the area to be        |
|      "x" : 1000,                              | produced: a roi in first image         |
|      "y" : 1000,                              | coordinates or the full image.         |
|      "w" : 10000,                             | Also specifies the resolution of the   | 
|      "h" : 10000                              | output dsm (usually set proportional   |
| },                                            | to the image GSD).                     |
| "full_img": false,                            |                                        |
| "dsm_resolution": 0.5,                        |                                        |
|-----------------------------------------------|----------------------------------------|
| "horizontal_margin": 50,                      | definition of the tiles: size and      |
| "vertical_margin": 50,                        | overlap margins (horizontal and        |
| "tile_size" : 800,                            | vertical)                              |
|-----------------------------------------------|----------------------------------------|
| "disp_range_method" : "sift",                 | Rectify tiles using SIFT keypoints,    |
| “sift_use_opencv_implementation” : true,      | using the fast opencv implementation   |
|-----------------------------------------------|----------------------------------------|
| “matching_algorithm” : “stereosgm_gpu”,       | Parameters of the stereo correlator.   |
| “census_ncc_win” : 7,                         | stereosgm_gpu is the fast gpu-based one|
|                                               | census_ncc_win sets the side of the    |
|                                               | matching window (here 7x7)             |
|-----------------------------------------------|----------------------------------------|
| “stereo_speckle_filter” : 50,                 |                                        |
| “fill_dsm_holes_smaller_than” : 10000,        |                                        |
| "msk_erosion": 0,                             |                                        |
| "3d_filtering_radius_gsd": 5,                 |                                        |
| "3d_filtering_fill_factor": 0.25              |                                        |



