{ pkgs }: {
  deps = [
    pkgs.bash
    pkgs.curl
    pkgs.openssl
    pkgs.libffi
    pkgs.zlib
    pkgs.stdenv.cc.cc.lib
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.nodejs-20_x
    pkgs.nodePackages.npm
  ];
}
