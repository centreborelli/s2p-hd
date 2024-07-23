# preparation: create names for local files
#
# NOTE: this first line of the script depends on the particular form of the
# "files.txt" file, that contains the paths to the input dsm to visualize.
# The rest of the lines are more general.
cat dsms_to_display.txt | cut -c49- | tr / _  | sed 's/^/i_/' > local_files.txt

# copy files
paste dmss_to_display.txt local_files.txt | while read x y; do
	cp $x $y
done


# 0. clean rubbish and interpolate into watertight models
for i in i_*; do
	remove_small_cc $i - 100 5 | bdint5pc -p 40 - ${i/i_/y_}
done

# 1. apply geographic palettes
# NOTE: palette ranges are set by hand according to the span of each scene
for i in y_fusio*; do palette 13 57 dem $i c${i/tif/png}; done
for i in y_site1*; do palette 15 40 dem $i c${i/tif/png}; done
for i in y_site2*; do palette 13 45 dem $i c${i/tif/png}; done
for i in y_site3*; do palette 0 110 dem $i c${i/tif/png}; done

# 2. compute ssao
for i in y_*; do
	cat $i | simpois | plambda - 'x,l -1 *' | blur i 0.25 |\
	plambda - '0 fmin -0.002 0 qe' -o s${i/tif/png}
done

# 3. combine ssao and palette
for i in y_*; do
	f=${i/tif/png}
	plambda {c,s}$f '255 - +' -o k$f
done

# 4. create the output ply files with ijmesh
# NOTE: 7 is a "magic" height factor, it should really be a computed from the
# ground sample distance, plus a slight vertical exxageration factor.
for i in y_*; do
	plambda $i '7 *' | ijmesh k${i/tif/png} - > o${i/tif/ply}
done
