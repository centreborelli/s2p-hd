# zoom in 4x the rgb image
gdal_translate -a_ullr 0 0 45056 -45056 qrgbnice.tif tmp.tif
gdalwarp -r bilinear -co "BIGTIFF=IF_NEEDED" -co "TILED=YES" -wm 2047 -ts 45056 45056 tmp.tif rgbnice4x.tif

## align the rgb on top of the panchro: hard coded translation (52, -6)
gdal_translate -co "TILED=YES" -co "BIGTIFF=IF_NEEDED" -srcwin 52 -6 43008 44032 rgbnice4x.tif rrgbnice4x.tif

# pansharpen
flambda pan.tif rrgbnice4x.tif "dup vavg 10 + / * 3 /" -o pxs.tif

# clean
#rm -f rgb.tif rgbnice.tif rgbnice4x.tif rrgbnice4x.tif tmp.tif pxs.tif
