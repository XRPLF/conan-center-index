"""Print the inputs of .github/workflows/test-recipes.yml as GitHub step outputs."""

import argparse
import json
import subprocess
from pathlib import Path

import yaml

# The consumer's choice, xrpl-rpc-spec's test_package sets its own.
EXCLUDED_OPTIONS = {"xrpl-rpc-spec/*:server"}


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def list_recipes() -> list[dict[str, str]]:
    recipes = []
    for reference in load_yaml(Path("recipes.yml"))["recipes"]:
        name, version = reference.split("/")
        folder = load_yaml(Path("recipes", name, "config.yml"))["versions"][version]["folder"]
        recipes.append({"reference": reference, "directory": f"recipes/{name}/{folder}", "version": version})
    return recipes


def rippled_options(rippled: Path) -> list[str]:
    inspect = subprocess.run(
        ["conan", "inspect", str(rippled / "conanfile.py"), "--format=json"],
        check=True,
        capture_output=True,
        text=True,
    )
    default_options = json.loads(inspect.stdout)["default_options"]
    return [
        f"{key}={value}"
        for key, value in default_options.items()
        if "/" in key and key not in EXCLUDED_OPTIONS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rippled", type=Path, help="the rippled checkout")
    args = parser.parse_args()

    recipes = list_recipes()
    linux = json.loads((args.rippled / ".github/scripts/strategy-matrix/linux.json").read_text())
    sha = subprocess.run(
        ["git", "-C", str(args.rippled), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    outputs = {
        "recipes": json.dumps(recipes, separators=(",", ":")),
        # The test runners may not have Python with PyYAML, yq or jq.
        "exports": " ".join(f"{recipe['directory']}:{recipe['version']}" for recipe in recipes),
        "options": " ".join(rippled_options(args.rippled)),
        # So that all the test jobs use the same commit, even if develop moves on.
        "rippled_sha": sha,
        "linux_image": f"ghcr.io/xrplf/xrpld/nix-ubuntu:{linux['image_tag']}",
    }
    for key, value in outputs.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
