{ pkgs }:

{
  deps = [
    pkgs.python311
    pkgs.nodejs_20
    pkgs.openssl
    pkgs.libffi
    pkgs.zlib
    pkgs.curl
    pkgs.git
  ];
}
