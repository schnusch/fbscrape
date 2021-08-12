{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  buildInputs = [
    pkgs.pandoc
    pkgs.python3Packages.selenium
  ];
  nativeBuildInputs = [
    pkgs.python3Packages.flake8
    pkgs.python3Packages.mypy
  ];
}
