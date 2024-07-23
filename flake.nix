{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    nixgl.url = "github:guibou/nixGL";
    nixgl.inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = {
    self,
    nixpkgs,
    flake-utils,
    nixgl,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = (import nixpkgs) {
          inherit system;
          # NOTE: patching pyproj, because with nix, it was always picking the {pkgs.proj}/share/proj
          # folder, and not considering PROJ_DATA.
          overlays = [
            (final: prev: {
              python311 = prev.python311.override {
                packageOverrides = python-self: python-super: {
                  pyproj = python-super.pyproj.overrideAttrs (attrs: {
                    patches = [
                      (pkgs.substituteAll {
                        src = pkgs.writeText "pyproj-patch" ''
                          diff --git a/pyproj/datadir.py b/pyproj/datadir.py
                          index df625fee..85357f74 100644
                          --- a/pyproj/datadir.py
                          +++ b/pyproj/datadir.py
                          @@ -70,7 +70,7 @@ def get_data_dir() -> str:
                               global _VALIDATED_PROJ_DATA
                               if _VALIDATED_PROJ_DATA is not None:
                                   return _VALIDATED_PROJ_DATA
                          -    internal_datadir = Path(__file__).absolute().parent / "proj_dir" / "share" / "proj"
                          +    internal_datadir = Path("@proj@/share/proj")
                               proj_lib_dirs = os.environ.get("PROJ_DATA", os.environ.get("PROJ_LIB", ""))
                               prefix_datadir = Path(sys.prefix, "share", "proj")
                               conda_windows_prefix_datadir = Path(sys.prefix, "Library", "share", "proj")
                          @@ -93,10 +93,10 @@ def get_data_dir() -> str:

                               if valid_data_dirs(_USER_PROJ_DATA):
                                   _VALIDATED_PROJ_DATA = _USER_PROJ_DATA
                          -    elif valid_data_dir(internal_datadir):
                          -        _VALIDATED_PROJ_DATA = str(internal_datadir)
                               elif valid_data_dirs(proj_lib_dirs):
                                   _VALIDATED_PROJ_DATA = proj_lib_dirs
                          +    elif valid_data_dir(internal_datadir):
                          +        _VALIDATED_PROJ_DATA = str(internal_datadir)
                               elif valid_data_dir(prefix_datadir):
                                   _VALIDATED_PROJ_DATA = str(prefix_datadir)
                               elif valid_data_dir(conda_windows_prefix_datadir):
                          diff --git a/setup.py b/setup.py
                          index 86ff1ff6..eb9eab2d 100644
                          --- a/setup.py
                          +++ b/setup.py
                          @@ -12,7 +12,7 @@ from setuptools import Extension, setup
                           PROJ_MIN_VERSION = (9, 0, 0)
                           CURRENT_FILE_PATH = Path(__file__).absolute().parent
                           BASE_INTERNAL_PROJ_DIR = Path("proj_dir")
                          -INTERNAL_PROJ_DIR = CURRENT_FILE_PATH / "pyproj" / BASE_INTERNAL_PROJ_DIR
                          +INTERNAL_PROJ_DIR = Path("@proj@")
                           PROJ_VERSION_SEARCH = re.compile(r".*Rel\.\s+(?P<version>\d+\.\d+\.\d+).*")
                           VERSION_SEARCH = re.compile(r".*(?P<version>\d+\.\d+\.\d+).*")

                          @@ -184,7 +184,7 @@ def get_extension_modules():
                               # By default we'll try to get options PROJ_DIR or the local version of proj
                               proj_dir = get_proj_dir()
                               library_dirs = get_proj_libdirs(proj_dir)
                          -    include_dirs = get_proj_incdirs(proj_dir)
                          +    include_dirs = get_proj_incdirs(Path("@projdev@"))

                               proj_version = get_proj_version(proj_dir)
                               check_proj_version(proj_version)
                          diff --git a/test/test_cli.py b/test/test_cli.py
                          index 7a696de7..1b9b777b 100644
                          --- a/test/test_cli.py
                          +++ b/test/test_cli.py
                          @@ -14,7 +14,7 @@ from pyproj.sync import _load_grid_geojson
                           from test.conftest import grids_available, proj_env, tmp_chdir

                           PYPROJ_CLI_ENDPONTS = pytest.mark.parametrize(
                          -    "input_command", [["pyproj"], [sys.executable, "-m", "pyproj"]]
                          +    "input_command", [[sys.executable, "-m", "pyproj"]]
                           )
                        '';
                        proj = pkgs.proj;
                        projdev = pkgs.proj.dev;
                      })
                      # from nixpkgs upstream:
                      (pkgs.fetchpatch {
                        url = "https://github.com/pyproj4/pyproj/commit/3f7c7e5bcec33d9b2f37ceb03c484ea318dff3ce.patch";
                        hash = "sha256-0J8AlInuhFDAYIBJAJ00XbqIanJY/D8xPVwlOapmLDE=";
                      })
                    ];
                  });
                };
              };
            })
          ];
        };
        utm =
          pkgs.python311Packages.buildPythonPackage
          rec {
            pname = "utm";
            version = "0.7.0";
            src = pkgs.python311Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-PJo2UOmLtu7OxTVBjQ39Tbj4jIzqyhEqD/B4fhFlZuI=";
            };
            pythonImportsCheck = ["utm"];
          };
        plyflatten =
          pkgs.python311Packages.buildPythonPackage
          rec {
            pname = "plyflatten";
            version = "0.2.2dev";
            pyproject = true;
            src = pkgs.fetchFromGitHub {
              owner = "centreborelli";
              repo = "plyflatten";
              rev = "e083160f42be9120c47ed1b3c7a4c5b9fc8537c3";
              sha256 = "sha256-PX+tToPjMjVJhlqbqW9SByr4LD/RJg/iSaNDTBCVdSE=";
            };
            propagatedBuildInputs = with pkgs.python311Packages; [
              numpy
              rasterio
              plyfile
              affine
              pyproj
              setuptools
            ];
            pythonImportsCheck = ["plyflatten"];
          };
        srtm4 =
          pkgs.python311Packages.buildPythonPackage
          {
            pname = "srtm4";
            version = "1.2.4-dontlock";
            pyproject = true;
            src = pkgs.fetchFromGitHub {
              owner = "centreborelli";
              repo = "srtm4";
              rev = "458e4015225a7eac76eb36ddae748617df291b24";
              sha256 = "sha256-qp/bQqkGLJ4snb/hT+ozUvM5yML7iqhsIDyVw5S8S5g=";
            };
            propagatedBuildInputs = with pkgs; [
              libtiff
              (
                with python311Packages; [
                  numpy
                  requests
                  filelock
                  affine
                  pyproj
                  rasterio
                  setuptools
                ]
              )
            ];
            pythonImportsCheck = ["srtm4"];
          };
        rpcm =
          pkgs.python311Packages.buildPythonPackage
          {
            pname = "rpcm";
            version = "1.4.8";
            pyproject = true;
            src = pkgs.fetchFromGitHub {
              owner = "centreborelli";
              repo = "rpcm";
              rev = "3d1cd2005ca508fbdcfcb738df3a71c35d60a84b";
              sha256 = "sha256-j2yh3NUpezSc3HZ/qRv15K34eSBSFRL8lqDiEFZNcms=";
            };
            propagatedBuildInputs = with pkgs.python311Packages; [
              numpy
              rasterio
              geojson
              pyproj
              srtm4
            ];
            pythonImportsCheck = ["rpcm"];
          };
        ransac =
          pkgs.python311Packages.buildPythonPackage
          rec {
            pname = "ransac";
            version = "1.0.4";
            src = pkgs.python311Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-YlVV+UOWLtc06hl3wkHwAT1uS7LiQIABmm4dKDjZCao=";
            };
            propagatedBuildInputs = with pkgs.python311Packages; [
              numpy
            ];
            pythonImportsCheck = ["ransac"];
          };
        cudapackages = pkgs.cudaPackages_11_4;
        proj_data = pkgs.stdenv.mkDerivation {
          name = "proj_data";
          dontUnpack = true;
          installPhase = ''
            mkdir $out
            cp ${pkgs.fetchurl {
              url = "https://github.com/OSGeo/PROJ-data/raw/a810a6d00ef4e16186e5db9abebb05ca14f2155d/us_nga/us_nga_egm96_15.tif";
              hash = "sha256-20kwJ1YsmwBNciD6iB9WA62tpOHFApuTP6feRUew540=";
            }} $out/us_nga_egm96_15.tif
            cp -ra ${pkgs.proj}/share/proj/* $out
          '';
          outputHashAlgo = "sha256";
          outputHashMode = "recursive";
          # NOTE: update this hash when bumping nixpkgs/proj version
          outputHash = "sha256-wIwdjOz80BHv0I0E83szpIcgzkw6stVMPOSkTBnaACc=";
        };
        srtm4_cache_for_tests = pkgs.fetchzip {
          # tile required to run s2p tests
          url = "https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/srtm_48_17.zip";
          hash = "sha256-bNGQ78uonydHXgNkoMkR/sb7RsiwMf1J1dzzXBvmZ48=";
          stripRoot = false;
        };
      in {
        packages = rec {
          default = s2p;
          sgm_gpu = pkgs.stdenv.mkDerivation {
            name = "sgm_gpu";
            version = "1.0.0";
            src = pkgs.lib.cleanSource ./3rdparty/sgm_gpu-develop-for-s2p;
            nativeBuildInputs = with pkgs; [
              cmake
              libtiff
              libjpeg
              libpng
              cudapackages.cuda_nvcc
              cudapackages.cuda_cudart
              # use the python version to deduplicate with s2p
              (with python311Packages; [
                opencv4
              ])
            ];
            # build the target during install
            # otherwise it gets built twice, I don't know why
            dontBuild = true;
            makeFlags = ["stereosgm"];
          };
          s2p-cuda = s2p.overrideAttrs (oldAttrs: {
            name = "s2p-hd-cuda";
            postInstall = ''
              cp ${sgm_gpu}/lib/libsgmgpu.h $out/lib/python3.11/site-packages/lib/
              cp ${sgm_gpu}/lib/libstereosgm.so $out/lib/python3.11/site-packages/lib/
            '';
          });
          s2p-cuda-fix = pkgs.writeShellScriptBin "s2p" ''
            ${nixgl.packages.${system}.nixGLNvidia}/bin/nixGLNvidia* ${s2p-cuda}/bin/s2p $@
          '';
          s2p = pkgs.python311Packages.buildPythonApplication {
            pname = "s2p-hd";
            version = "1.0b26.dev0";
            src = pkgs.lib.cleanSource ./.;
            meta.mainProgram = "s2p";
            pyproject = true;
            nativeBuildInputs = with pkgs; [
              pkg-config
              gdal
            ];
            propagatedBuildInputs = with pkgs; [
              libpng
              libjpeg
              libtiff
              fftw
              geographiclib
              (with python311Packages; [
                numpy
                scipy
                beautifulsoup4
                fire
                numba
                rasterio
                utm
                pyproj
                plyfile
                opencv4
                requests
                cffi
                geojson

                plyflatten
                rpcm
                srtm4
                ransac
              ])
            ];
            postPatch = ''
              # provided as 'opencv4' in propagatedBuildInputs
              substituteInPlace setup.py --replace "opencv-python-headless" ""
              # provided as 'rpcm' in propagatedBuildInputs
              substituteInPlace setup.py --replace "'rpcm @ git+https://github.com/centreborelli/rpcm'," ""
              # provided as 'plyflatten' in propagatedBuildInputs
              substituteInPlace setup.py --replace "'plyflatten @ git+https://github.com/centreborelli/plyflatten'," ""
            '';
            dontUseSetuptoolsCheck = true;
            nativeCheckInputs = with pkgs.python311Packages; [
              pytest
              pytest-cov
              psutil
            ];
            checkPhase = ''
              runHook preCheck
              SRTM4_CACHE=${srtm4_cache_for_tests} PROJ_DATA=${proj_data} pytest -v tests/
              runHook postCheck
            '';
          };
          dockerImage = pkgs.dockerTools.streamLayeredImage {
            # build with: nix build --impure .#dockerImage
            # and then: ./result | docker load
            name = "s2p-hd-cuda";
            tag = "latest";
            created = "now";
            contents = with pkgs; [s2p-cuda busybox fish gdal];
            config = {
              Cmd = ["${s2p-cuda}/bin/s2p"];
              Env = [
                # /usr/lib64 because the --gpus=all docker options puts things there
                "LD_LIBRARY_PATH=/usr/lib64:${cudapackages.cuda_cudart}/lib"
                "PROJ_DATA=${proj_data}"
              ];
            };
          };
        };
      }
    );
}
