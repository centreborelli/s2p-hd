# the following two options are used to control all C and C++ compilations
CFLAGS   ?= -march=native -O3
CXXFLAGS ?= -march=native -O3
export CFLAGS
export CXXFLAGS

# these options are only used for the programs directly inside "./c/"
IIOLIBS     = -lz -ltiff -lpng -ljpeg -lm


# test for cuda
NVCC_RESULT := $(shell which nvcc 2>/dev/null)
NVCC_TEST := $(notdir $(NVCC_RESULT))


# default rule builds only the programs necessary for the test skip sgm_gpu is cuda is not presetn
ifeq ($(NVCC_TEST),nvcc)
default: libhomography sift mgm_multi tvl1 executables libraries sgm_gpu
else
default: libhomography sift mgm_multi tvl1 executables libraries
endif


# the "all" rule builds three further correlators
all: default msmw3 sgbm

# test for the default configuration
test: default
	env PYTHONPATH=. pytest tests

#
# four standard "modules": homography, sift, mgm, and mgm_multi
#


libhomography:
	$(MAKE) -j -C 3rdparty/homography libhomography.so
	cp 3rdparty/homography/libhomography.h lib
	cp 3rdparty/homography/libhomography.so lib

sift:
	$(MAKE) -j -C 3rdparty/sift/simd libsift4ctypes.so
	cp 3rdparty/sift/simd/libsift4ctypes.so lib

mgm_multi:
	$(MAKE) -j -C 3rdparty/mgm_multi
	cp 3rdparty/mgm_multi/mgm       bin
	cp 3rdparty/mgm_multi/mgm_multi bin

tvl1:
	$(MAKE) -j -C 3rdparty/tvl1flow
	cp 3rdparty/tvl1flow/tvl1flow bin
	cp 3rdparty/tvl1flow/callTVL1.sh bin

# compiled but not used (plain mgm is already included from multi_mgm)
mgm:
	$(MAKE) -j -C 3rdparty/mgm
	#cp 3rdparty/mgm/mgm bin


#
# rules for optional "modules": sgbm, tvl1, etc
#

msmw3:
	make -C 3rdparty/msmw3
	cp 3rdparty/msmw3/msmw bin

sgbm:
	$(MAKE) -j -C 3rdparty/sgbm
	cp 3rdparty/sgbm/sgbm bin

sgbm_opencv:
	mkdir -p bin/build_sgbm
	cd bin/build_sgbm; cmake -D CMAKE_BUILD_TYPE=Release -D CMAKE_PREFIX_PATH=~/local ../../3rdparty/stereo_hirschmuller_2008; $(MAKE) -j
	cp bin/build_sgbm/sgbm2 bin
	cp bin/build_sgbm/SGBM bin
	cp 3rdparty/stereo_hirschmuller_2008/callSGBM.sh bin
	cp 3rdparty/stereo_hirschmuller_2008/callSGBM_lap.sh bin
	cp 3rdparty/stereo_hirschmuller_2008/callSGBM_cauchy.sh bin

msmw2:
	mkdir -p bin/build_msmw2
	cd bin/build_msmw2; cmake -D CMAKE_BUILD_TYPE=Release ../../3rdparty/msmw2; $(MAKE) -j
	cp bin/build_msmw2/libstereo_newversion/iip_stereo_correlation_multi_win2_newversion bin


sgm_gpu:
	mkdir -p bin/build_sgm_gpu
	cd bin/build_sgm_gpu; cmake -D CMAKE_BUILD_TYPE=Release ../../3rdparty/sgm_gpu-develop-for-s2p; $(MAKE) stereosgm
	cp bin/build_sgm_gpu/libstereosgm.so lib
	cp 3rdparty/sgm_gpu-develop-for-s2p/src/libsgmgpu.h lib




#
# rules to build the programs under the source directory
#

SRCIIO   = morsi cldmask remove_small_cc colormeshgeo ijmesh2

PROGRAMS = $(addprefix bin/,$(SRCIIO))

executables: $(PROGRAMS)


# generic rule for building binary objects from C sources
c/%.o : c/%.c
	$(CC) -fpic $(CFLAGS) -c $< -o $@

# generic rule for building binary objects from C++ sources
c/%.o: c/%.cc
	$(CXX) -fpic $(CXXFLAGS) -c $^ -o $@

# generic rule to build most imscript binaries
bin/% : c/%.o c/iio.o
	$(CC) $^ -o $@ $(IIOLIBS)

# this particular program combines different objects in a non-standard way
bin/colormeshgeo: c/colormeshgeo.o c/iio.o c/rpc.o c/geographiclib_wrapper.o
	$(CC) $^ $(IIOLIBS) -lstdc++ -lGeographic -o $@


#
# rules to build the dynamic objects that are used via ctypes
#

libraries: lib/disp_to_h.so

lib/disp_to_h.so: c/disp_to_h.o c/iio.o c/rpc.o
	$(CC) -shared $^ $(IIOLIBS) -o $@



# automatic dependency generation
-include .deps.mk
.PHONY:
depend:
	$(CC) -MM `ls c/*.c c/*.cpp` | sed '/^[^ ]/s/^/c\//' > .deps.mk


# rules for cleaning, nothing interesting below this point
clean: clean_homography clean_sift clean_imscript \
       clean_msmw2 clean_msmw3 clean_tvl1 clean_sgbm clean_mgm clean_mgm_multi\
       clean_s2p
	$(RM) -r bin/build_sgm_gpu
	$(RM) c/*.o bin/* lib/*
	$(RM) -r s2p_tmp

distclean: clean ; $(RM) .deps.mk


# clean targets that use recursive makefiles
clean_homography: ; $(MAKE) clean -C 3rdparty/homography
clean_sift:       ; $(MAKE) clean -C 3rdparty/sift/simd
clean_tvl1:       ; $(MAKE) clean -C 3rdparty/tvl1flow
clean_sgbm:       ; $(MAKE) clean -C 3rdparty/sgbm
clean_mgm:        ; $(MAKE) clean -C 3rdparty/mgm
clean_mgm_multi:  ; $(MAKE) clean -C 3rdparty/mgm_multi
clean_msmw3:      ; $(MAKE) clean -C 3rdparty/msmw3

# clean targets that use a build dir
clean_msmw2:      ; $(RM) -r bin/build_msmw2


.PHONY: default all sift sgbm sgbm_opencv msmw tvl1 imscript clean clean_sift\
	clean_imscript clean_msmw2 clean_tvl1 clean_sgbm clean_mgm\
	clean_mgm_multi clean_s2p test distclean


# The following conditional statement appends "-std=gnu99" to CFLAGS when the
# compiler does not define __STDC_VERSION__.  The idea is that many older
# compilers are able to compile standard C when given that option.
# This hack seems to work for all versions of gcc, clang and icc.
CVERSION = $(shell $(CC) -dM -E - < /dev/null | grep __STDC_VERSION__)
ifeq ($(CVERSION),)
CFLAGS := $(CFLAGS) -std=gnu99
endif
