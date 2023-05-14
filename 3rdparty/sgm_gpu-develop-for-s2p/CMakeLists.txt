cmake_minimum_required(VERSION 3.1)

project(libSGM_debug)

set(CMAKE_FIND_PACKAGE_SORT_ORDER NATURAL)

if (CMAKE_COMPILER_IS_GNUCXX)
	set(CMAKE_CXX_FLAGS "-O3 -Wall")
endif()

find_package(CUDA REQUIRED)

find_package(OpenCV REQUIRED)
if (OpenCV_VERSION VERSION_LESS 3.0)
	message(FATAL_ERROR "Error: OpenCV version requires at least 3.0")
endif()

include_directories(${OpenCV_INCLUDE_DIRS})
find_package( OpenCV REQUIRED )

file(GLOB stereosgm_SRC
     "src/*.cu"
     "src/*.h"
     "src/*.c"
     "src/*.hpp"
)

cuda_add_library(stereosgm src/libsgmgpu.cpp src/stereo_sgm.cpp ${stereosgm_SRC} SHARED)
target_link_libraries(stereosgm ${CUDA_LIBRARIES} ${OpenCV_LIBS})
install(TARGETS stereosgm DESTINATION lib)
install(FILES ./src/libsgmgpu.h DESTINATION lib)
