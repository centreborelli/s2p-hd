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
        pkgs = nixpkgs.legacyPackages.${system};
        utm =
          pkgs.python3Packages.buildPythonPackage
          rec {
            pname = "utm";
            version = "0.7.0";
            src = pkgs.python3Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-PJo2UOmLtu7OxTVBjQ39Tbj4jIzqyhEqD/B4fhFlZuI=";
            };
            pythonImportsCheck = ["utm"];
          };
        plyflatten =
          pkgs.python3Packages.buildPythonPackage
          rec {
            pname = "plyflatten";
            version = "0.2.0";
            src = pkgs.python3Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-3ei0Hl6q9bB+x3Fa3bRGowTXMVy9m1AOtKDTZ6u4+oc=";
            };
            propagatedBuildInputs = with pkgs; [
              (python3.withPackages (ps:
                with ps; [
                  numpy
                  rasterio
                  plyfile
                  affine
                  pyproj
                ]))
            ];
            pythonImportsCheck = ["plyflatten"];
          };
        srtm4 =
          pkgs.python3Packages.buildPythonPackage
          rec {
            pname = "srtm4";
            version = "1.2.4";
            src = pkgs.python3Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-+eMjUsiSBkEMYTwZXuVyRTMG7FnB/Pb52X7OwqUnLQo=";
            };
            propagatedBuildInputs = with pkgs; [
              libtiff
              (python3.withPackages (ps:
                with ps; [
                  numpy
                  requests
                  filelock
                  affine
                  pyproj
                  rasterio
                ]))
            ];
            pythonImportsCheck = ["srtm4"];
          };
        rpcm =
          pkgs.python3Packages.buildPythonPackage
          {
            pname = "rpcm";
            version = "1.4.8";
            src = pkgs.fetchFromGitHub {
              owner = "centreborelli";
              repo = "rpcm";
              rev = "3d1cd2005ca508fbdcfcb738df3a71c35d60a84b";
              sha256 = "sha256-j2yh3NUpezSc3HZ/qRv15K34eSBSFRL8lqDiEFZNcms=";
            };
            propagatedBuildInputs = with pkgs; [
              (python3.withPackages (ps:
                with ps; [
                  numpy
                  rasterio
                  geojson
                  pyproj
                  boto3
                  requests
                  filelock # because of srtm4?

                  srtm4
                ]))
            ];
            pythonImportsCheck = ["rpcm"];
          };
        ransac =
          pkgs.python3Packages.buildPythonPackage
          rec {
            pname = "ransac";
            version = "1.0.4";
            src = pkgs.python3Packages.fetchPypi {
              inherit pname version;
              sha256 = "sha256-YlVV+UOWLtc06hl3wkHwAT1uS7LiQIABmm4dKDjZCao=";
            };
            propagatedBuildInputs = with pkgs; [
              (python3.withPackages (ps:
                with ps; [
                  numpy
                ]))
            ];
            pythonImportsCheck = ["ransac"];
          };
      in {
        packages = rec {
          default = s2p;
          sgm_gpu = pkgs.stdenv.mkDerivation {
            name = "sgm_gpu";
            version = "1.0.0";
            src = pkgs.lib.cleanSource ./3rdparty/sgm_gpu-develop-for-s2p;
            nativeBuildInputs = with pkgs; [cudatoolkit cmake opencv3];
          };
          s2p-cuda = s2p.overrideAttrs (oldAttrs: {
            name = "s2p-hd-cuda";
            postInstall = ''
              cp ${sgm_gpu}/lib/libsgmgpu.h $out/lib/python3.10/site-packages/lib/
              cp ${sgm_gpu}/lib/libstereosgm.so $out/lib/python3.10/site-packages/lib/
            '';
          });
          s2p-cuda-fix = pkgs.writeShellScriptBin "s2p-cuda-fix" ''
            ${nixgl.packages.${system}.nixGLNvidia}/bin/nixGLNvidia* ${s2p-cuda}/bin/s2p $@
          '';
          s2p = pkgs.python3Packages.buildPythonApplication {
            pname = "s2p-hd";
            version = "1.0b26.dev0";
            src = pkgs.lib.cleanSource ./.;
            meta.mainProgram = "s2p";
            nativeBuildInputs = with pkgs; [
              pkg-config
              gdal
            ];
            propagatedBuildInputs = with pkgs; [
              libpng
              libjpeg
              libtiff
              fftw
              (python3.withPackages (ps:
                with ps; [
                  numpy
                  scipy
                  beautifulsoup4
                  fire
                  numba
                  rasterio
                  utm
                  pyproj
                  plyfile
                  opencv3
                  requests
                  cffi
                  boto3
                  geojson
                  filelock # because of srtm4?

                  plyflatten
                  rpcm
                  srtm4
                  ransac
                ]))
            ];
            postPatch = ''
              # provided as 'opencv3' in propagatedBuildInputs
              substituteInPlace setup.py --replace "opencv-python-headless" ""
              # provided as 'rpcm' in propagatedBuildInputs
              substituteInPlace setup.py --replace "'rpcm @ git+https://github.com/centreborelli/rpcm'," ""
            '';
            pythonImportsCheck = ["s2p"];
            doCheck = false;
          };
        };
      }
    );
}
