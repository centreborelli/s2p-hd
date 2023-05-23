#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>

#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include "libsgm.h"

#define ASSERT_MSG(expr, msg)                                                  \
  if (!(expr)) {                                                               \
    std::cerr << msg << std::endl;                                             \
    std::exit(EXIT_FAILURE);                                                   \
  }

extern "C" {
#include "libsgmgpu.h"
}

struct sgm_handle {
  const sgm::StereoSGM::Parameters params;
  int disp_size;

  sgm_handle(const sgm::StereoSGM::Parameters params, int disp_size)
      : params(params), disp_size(disp_size) {}
};

extern "C" sgm_handle *make_sgm_gpu(int disp_size, int P1, int P2, float uniqueness,
                         int num_paths, int min_disp, int LR_max_diff,
                         bool subpixel, bool verbose) {
  ASSERT_MSG(disp_size == 64 || disp_size == 128 || disp_size == 256,
             "disparity size must be 64, 128 or 256.");
  ASSERT_MSG(num_paths == 4 || num_paths == 8,
             "number of scanlines must be 4 or 8.");

  const sgm::PathType path_type =
      num_paths == 8 ? sgm::PathType::SCAN_8PATH : sgm::PathType::SCAN_4PATH;

  const sgm::StereoSGM::Parameters params(
      P1, P2, uniqueness, subpixel, path_type, min_disp, LR_max_diff, verbose);

  return new sgm_handle(params, disp_size);
}

extern "C" void exec_sgm_gpu(sgm_handle *handle, int h, int w,
                             uint16_t *left_data, uint16_t *right_data,
                             float *disp) {
  auto &params = handle->params;
  const int input_depth = 16;
  const int output_depth = 16;

  if (params.verbose)
    std::cout << "sgm initialization begin:" << std::endl;
  std::chrono::steady_clock::time_point begin_sgm_ini =
      std::chrono::steady_clock::now();
  sgm::StereoSGM ssgm(w, h, handle->disp_size, input_depth, output_depth,
                      sgm::EXECUTE_INOUT_HOST2HOST, params);
  std::chrono::steady_clock::time_point end_sgm_ini =
      std::chrono::steady_clock::now();
  if (params.verbose)
    std::cout << "\tsgm all initialization time = "
              << std::chrono::duration_cast<std::chrono::milliseconds>(
                     end_sgm_ini - begin_sgm_ini)
                     .count()
              << "[ms]" << std::endl;

  cv::Mat disparity(h, w, CV_16S);

  if (params.verbose)
    std::cout << "sgm processing begin:" << std::endl;
  std::chrono::steady_clock::time_point begin_sgm_proc =
      std::chrono::steady_clock::now();
  ssgm.execute(left_data, right_data, disparity.data);
  std::chrono::steady_clock::time_point end_sgm_proc =
      std::chrono::steady_clock::now();
  if (params.verbose)
    std::cout << "\tsgm processing time = "
              << std::chrono::duration_cast<std::chrono::milliseconds>(
                     end_sgm_proc - begin_sgm_proc)
                     .count()
              << "[ms]" << std::endl;

  // create mask for invalid disp
  cv::Mat mask = disparity == ssgm.get_invalid_disparity();

  // show image
  cv::Mat disparity_8u; //, disparity_color;
  disparity.convertTo(disparity_8u, CV_32FC1);

  // disparity conventions
  disparity_8u *= -1;
  disparity_8u.setTo(NAN, mask);

  if (params.subpixel) {
    // std::cout << sgm::StereoSGM::SUBPIXEL_SCALE;
    disparity_8u /= sgm::StereoSGM::SUBPIXEL_SCALE;
  }

  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      disp[y * w + x] = disparity_8u.at<float>(y, x);
    }
  }
}

extern "C" void free_sgm_gpu(sgm_handle *handle) { delete handle; }
