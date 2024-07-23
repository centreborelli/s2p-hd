# compute transformation parameters from spectral curves
#octave composite.m > C.plambda

# convert MS to RGB
COLOR="`cat ../C.plambda`"
flambda msi.tif "$COLOR" -o rgb.tif

# add some near-infrared into the green, for brighter vegetation
SPICE='x[0] x[1] 0.95 * y[6] 0.05 * + x[2] join3'
flambda rgb.tif msi.tif "$SPICE"  -o rgbnice.tif

# logarithm, scaling, saturation and quatization to [0, 255]
QUANT='log 4.28 4.67 4.7 join3 - 1.6 1.27 0.82 join3 / 0 1 qe'
flambda rgbnice.tif "$QUANT" -o qrgbnice.tif
