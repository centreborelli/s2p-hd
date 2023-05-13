typedef struct sgm_handle sgm_handle;

sgm_handle *make_sgm_gpu(int disp_size, int P1, int P2, float uniqueness,
                         int num_paths, int min_disp, int LR_max_diff,
                         bool subpixel);

void exec_sgm_gpu(sgm_handle *handle, int h, int w, uint16_t *im1,
                  uint16_t *im2, float *disp);
void free_sgm_gpu(sgm_handle *handle);
