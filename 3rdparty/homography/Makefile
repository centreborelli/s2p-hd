CXXFLAGS ?= -march=native -O3
override CXXFLAGS := $(CXXFLAGS) `gdal-config --cflags` -fPIC
override LDLIBS  := $(LDLIBS) `gdal-config --libs`

OBJ = LibImages/LibImages.o \
      Utilities/Utilities.o \
      Utilities/Memory.o \
      Utilities/Parameters.o \
      Utilities/Time.o \
      LibHomography/Homography.o \
      LibHomography/Splines.o

homography: main.o $(OBJ)
	$(CXX) $(LDFLAGS) $^ $(LDLIBS) -o $@

libhomography.so: libhomography.o $(OBJ)
	$(CXX) $(LDFLAGS) $^ $(LDLIBS) -o $@ -shared -fPIC

clean:
	rm -f homography libhomography.so $(OBJ)


# hack (compatibility flags for badly configured OSX clang)
#
# The following conditional statement appends "-std=c++11" to CXXFLAGS when the
# macro __APPLE__ is defined.  This is useful to circumvent a bug that arises
# when compiling gdal with clang-9 on modern OSX.
ifeq (1,$(shell $(CXX) -x c++ $(CXXFLAGS) -dM -E -</dev/null|grep __APPLE__|cut -c19-))
override CXXFLAGS := $(CXXFLAGS) -std=c++11
endif

