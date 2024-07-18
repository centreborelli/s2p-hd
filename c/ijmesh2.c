// basic behavior: build a mesh from a dsm
// 	ijmesh2 dsm.tif > ply
//
// option: set a resolution (in gsm units)
// 	ijmesh2 dsm.tif -r 0.37 > ply
//
// option: colorize using corresponding colors (of same size as the dsm)
// 	ijmesh2 dsm.tif -k msi.png > ply
//
// option: colorize using georeferencing data and sat image (with rpc)
// 	ijmesh2 dsm.tif -c msi.tif -l msi.rpc > ply
//
// option: filter "long" triangles
// 	ijmesh2 dsm.tif -f 20 > ply
//
// option: filter by connected component size
// 	ijmesh2 dsm.tif -s 100 > ply
//
// option: change orientation of the second axis
// 	ijmes dsm.tif -i > ply

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "iio.h"
#include "pickopt.c"
int main(int c, char *v[])
{
	// extract named arguments
	float resolution = atof(pick_option(&c, &v, "r", "1"));
	float filterlong = atof(pick_option(&c, &v, "f", "inf"));
	float filterwide = atof(pick_option(&c, &v, "s", "inf"));
	char *fname_kolors = pick_option(&c, &v, "k", "");
	char *fname_colors = pick_option(&c, &v, "c", "");
	char *fname_rpc = pick_option(&c, &v, "l", "");
	_Bool option_i = pick_option(&c, &v, "i", NULL);

	// prositional arguments
	if (c != 2)
		return fprintf(stderr, "usage:\n\t%s heights > ply\n", *v);
		//                          0 1
	char *fname_heights = v[1];

	// read input dsm
	int w, h;
	float *heights = iio_read_image_float(fname_heights, &w, &h);

	// if requested, read registered colors
	float *kolors = NULL;
	int ww, hh, pd = 0;
	if (0 == strcmp(fname_colors, "WHITE")) {
		pd = 1;
		ww = w; hh = h;
		kolors = malloc(w * h * sizeof*kolors);
		for (int i = 0; i < w*h; i++)
			kolors[i] = 255;
	} else if (*fname_kolors) {
		kolors = iio_read_image_float_vec(fname_colors, &w, &h, &pd);
		if (w != ww || h != hh)
			exit(fprintf(stderr,"colors and dsm size mismatch"));
		if (pd != 1 && pd != 3)
			exit(fprintf(stderr,"expecting a gray or color image"));
	}

	// not implemented, colors from localized sat image
	// ...
	void *colors = NULL;

	// assign comfortable pointers
	uint8_t (*kolor)[w][pd] = (void*)kolors;  // projected color image
	float (*height)[w] = (void*)heights;      // height image
	int (*vid)[w] = malloc(w*h*sizeof(int));  // vertex indices

	// count number of valid vertices
	int nvertices = 0;
	for (int j = 0; j < h; j++)
	for (int i = 0; i < w; i++)
		if (isfinite(height[j][i]))
			vid[j][i] = nvertices++;
		else
			vid[j][i] = -1;

	// count number of valid faces (may decrease later when whe filter it
	int nfaces = 0;
	for (int j = 0; j < h-1; j++)
	for (int i = 0; i < w-1; i++)
	{
		int q[4] = {vid[j][i], vid[j+1][i], vid[j+1][i+1], vid[j][i+1]};
		if (q[0] >= 0 && q[1] >= 0 && q[2] >= 0 && q[3] >= 0)
			nfaces += 1;
	}

	// print ply header
	printf("ply\n");
	printf("format ascii 1.0\n");
	//printf("format binary_little_endian 1.0\n");
	printf("comment created by ijmesh2\n");
	printf("element vertex %d\n", nvertices);
	printf("property float x\n");
	printf("property float y\n");
	printf("property float z\n");
	if (kolors || colors) {
		printf("property uchar red\n");
		printf("property uchar green\n");
		printf("property uchar blue\n");
	}
	printf("element face %d\n", nfaces);
	printf("property list uchar int vertex_index\n");
	printf("end_header\n");


	int cx;

	// output vertices
	cx = 0;
	for (int j = 0; j < h; j++)
	for (int i = 0; i < w; i++)
	{
		if (!isfinite(height[j][i])) continue;
		uint8_t rgb[3] = {255, 0, 255};
		if (kolors)
		{
			for (int k = 0; k < pd; k++) rgb[k] = kolor[j][i][k];
			for (int k = pd; k < 3; k++) rgb[k] = rgb[k-1];
		}
		double xyz[3] = {i/resolution, j/resolution, height[j][i]};
		//if (option_i) xyz[1] *= -1;
		printf("%.16lf %.16lf %.16lf", xyz[1], -xyz[0], xyz[2]);
		if (kolors)
			printf("%d %d %d\n", rgb[0], rgb[1], rgb[2]);
		printf("\n");
		cx += 1;
	}
	assert(cx == nvertices);

	// output faces
	cx = 0;
	for (int j = 0; j < h-1; j++)
	for (int i = 0; i < w-1; i++)
	{
		int q[4] = {vid[j][i], vid[j][i+1], vid[j+1][i+1], vid[j+1][i]};
		if (q[0] >= 0 && q[1] >= 0 && q[2] >= 0 && q[3] >= 0)
		{
			printf("4 %d %d %d %d\n", q[0], q[1], q[2], q[3]);
			cx += 1;
		}
	}
	assert(cx == nfaces);

	return 0;
}
