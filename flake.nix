{
    description = "SystemRDL inspired CSR generation in spinal";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
        nixpkgs-old.url = "github:NixOS/nixpkgs/2d068ae5c6516b2d04562de50a58c682540de9bf";
        flake-parts.url = "github:hercules-ci/flake-parts";
    };

    outputs = { flake-parts, nixpkgs-old, ... } @ inputs:
        flake-parts.lib.mkFlake { inherit inputs; } {
            systems = [ "x86_64-linux" ];

            perSystem = { pkgs, system, ... }: let
                pkgs_old = nixpkgs-old.legacyPackages.${system};
            in {
                devShells.default = pkgs.mkShell {
                    MILL_JVM_VERSION = "system";
                    JAVA_HOME = "${pkgs.zulu}";
                    packages = [
                        pkgs_old.mill
                        pkgs.verilator
                        pkgs.coursier
                        pkgs.zulu
                        pkgs.python313
                        pkgs.zsh
                        pkgs.uv
                        ];

                    shellHook = ''
                        unset PYTHONPATH
                        uv sync
                        . .venv/bin/activate
                        '';
                };
            };
        };
}
