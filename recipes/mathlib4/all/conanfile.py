import json
import os
import shutil
from io import StringIO
from pathlib import Path

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.build import build_jobs
from conan.tools.env import Environment
from conan.tools.files import copy

required_conan_version = ">=2.0.0"

PACKAGES_DIR = "packages"
LIB_DIR = "lib"
# Keep in step with cpp_info.libs in package_info: the linker derives the file
# name from the library name, so "mathlib4" there means "libmathlib4.a" here.
ARCHIVE_NAME = "libmathlib4.a"


class Mathlib4Conan(ConanFile):
    """Prebuilt mathlib and its Lean dependency closure.

    Downloads mathlib's olean cache and compiles the dependency `:static`
    objects once, bundling them into lib/libmathlib4.a. Consumers get both the
    elaboration artifacts (the olean tree, so lake can resolve imports) and the
    native objects, so they never compile mathlib themselves. One archive
    rather than lake's per-library ones, so consumers need no link order.

    The version tracks the Lean toolchain: mathlib tags releases against a
    toolchain, so mathlib4/X.Y.Z bundles the mathlib revision pinned for Lean
    X.Y.Z. lean4/X.Y.Z is both the tool that builds this package and a host
    requirement: the objects reference Init/Std/Lean and the runtime in
    libleanshared (and Lake, through ImportGraph), so mathlib4::mathlib4
    links lean4 transitively and the two versions cannot drift apart.

    The pinned dependency closure lives in lake/<version>/lake-manifest.json,
    exported alongside this recipe and packaged so consumers can check it. What
    has to agree is the `packages` array -- the name and revision of every
    entry -- not the whole file: the root `name` deliberately differs from any
    consumer's. If the closures diverge, lake re-resolves and the prebuilt
    oleans go unused. The `:static` targets to build for each version are in
    conandata.yml (`dep_targets`), next to the version's other data.

    Each dependency keeps a `.git` directory. Lake resolves a dependency's
    revision and URL from it; without it lake treats the URL as changed,
    deletes the directory, re-clones and rebuilds everything -- inside this
    package. Only a shallow repository is kept (one commit, the pinned
    revision), which satisfies everything lake checks: `git rev-parse HEAD`,
    `git remote get-url origin` and a clean `git diff HEAD`. That last check
    may rewrite `.git/index`; package() prepares the repositories to prevent
    that, but if it happens `conan cache check-integrity` reports this package
    as modified. Harmless for the build.

    Building needs `git` (lake clones the dependencies, and package() rewrites
    their repositories) and `curl` (mathlib's cache tool downloads with it) on
    PATH, plus network access.
    """

    name = "mathlib4"
    description = "Prebuilt Lean 4 mathlib and its dependency closure"
    # Cli is MIT; the rest of the closure is Apache-2.0.
    license = ("Apache-2.0", "MIT")
    url = "https://github.com/XRPLF/conan-center-index"
    homepage = "https://github.com/leanprover-community/mathlib4"
    topics = ("lean", "lean4", "mathlib", "formal-verification", "pre-built")

    package_type = "static-library"
    # olean files are arch-specific memory images and the bundled objects are
    # native code, so the package varies by platform -- but not by the
    # consumer's compiler or build type, since everything here is produced by
    # the Lean toolchain's own bundled clang.
    settings = "os", "arch"

    @property
    def _dep_targets(self):
        return self.conan_data["dep_targets"][self.version]

    def export_sources(self):
        # The lake pin, one workspace per version under lake/<version>/, flattened
        # into the source root. lakefile.toml declares the workspace,
        # lake-manifest.json fixes the dependency closure (and is packaged so
        # consumers can check that theirs matches). lean-toolchain looks
        # redundant next to the recipe version but is required: `lake exe cache
        # get` reads it directly, throwing "no such file or directory" when it is
        # absent and refusing to use the olean cache (exit 1) when it disagrees
        # with mathlib's own toolchain. Do not drop it.
        workspace = os.path.join(self.recipe_folder, "lake", self.version)
        for name in ("lakefile.toml", "lake-manifest.json", "lean-toolchain"):
            if not os.path.isfile(os.path.join(workspace, name)):
                raise ConanException(
                    f"{self.name}/{self.version}: missing {name} in "
                    f"lake/{self.version}/; each version needs its own lake "
                    f"workspace there"
                )
        copy(self, "*", src=workspace, dst=self.export_sources_folder)

    def package_id(self):
        # Everything here is produced by the Lean toolchain's own bundled clang,
        # so the content depends on the platform and nothing else. Consumer
        # profiles inject C++ concerns into every package_id through
        # `tools.info.package_id:confs` (rippled's default profile adds
        # user.package:cppstd_version, XRPLF's ci profile also
        # user.package:libc_version); clearing them keeps one binary per
        # platform, so a consumer whose profile differs from the publisher's
        # still gets a cache hit instead of rebuilding mathlib.
        self.info.conf.clear()

    def validate(self):
        if str(self.settings.os) not in self.conan_data["platforms"]:
            raise ConanInvalidConfiguration(
                f"{self.name}/{self.version}: {self.settings.os} is not supported"
            )

    def validate_build(self):
        # The tool_requires lean4 is the build platform's, and its bundled clang
        # gets no target flag, so the objects would be build-platform code under
        # the host package_id. validate_build rather than validate: consumers
        # can still download correctly built host binaries.
        if (
            str(self.settings.os) != str(self.settings_build.os)
            or str(self.settings.arch) != str(self.settings_build.arch)
        ):
            raise ConanInvalidConfiguration(
                f"{self.name}/{self.version}: cross-building is not supported"
            )

    def requirements(self):
        # transitive_headers: anything that calls into the bundled objects
        # needs lean.h for the runtime it talks to.
        self.requires(f"lean4/{self.version}", transitive_headers=True)

    def build_requirements(self):
        self.tool_requires(f"lean4/{self.version}")

    def _require_tools(self):
        missing = [tool for tool in ("git", "curl") if shutil.which(tool) is None]
        if missing:
            raise ConanException(
                f"{self.name}/{self.version}: {' and '.join(missing)} not found "
                f"on PATH. lake clones the dependencies with git and mathlib's "
                f"cache tool downloads with curl."
            )

    def _require_toolchain_bindir(self):
        """The tool_requires toolchain, and only that one. Raises if it cannot run.

        Never a lean/lake found on PATH: lake records Lean's githash in its build
        traces, so a same-version but differently-built toolchain would produce
        oleans the published package cannot be reused with. Taking it from the
        dependency graph keeps the output reproducible.
        """
        bindir = self.dependencies.build["lean4"].cpp_info.bindirs[0]
        probe = StringIO()
        try:
            self.run(
                f'"{Path(bindir) / "lake"}" --version',
                stdout=probe,
                stderr=probe,
                quiet=True,
            )
        except ConanException as exc:
            hint = ""
            if self.settings_build.os == "Linux":
                # The upstream release names the FHS loader in PT_INTERP.
                hint = (
                    " On Linux they need the FHS loader "
                    "/lib64/ld-linux-x86-64.so.2; NixOS provides it through "
                    "nix-ld (programs.nix-ld.enable = true)."
                )
            raise ConanException(
                f"{self.name}/{self.version}: the lean4 package's binaries "
                f"cannot be executed.{hint}\n{probe.getvalue().strip()}"
            ) from exc
        return bindir

    def generate(self):
        # Applied by every self.run, and only there. Conan already puts the
        # tool_requires' bin/ first on PATH.
        #
        # LEAN_CC -- leanc invokes it when set, and otherwise its own bundled
        # clang. It emits link flags assuming that clang's default library
        # search paths, so an ambient LEAN_CC pointing at the system compiler
        # fails to find Lean's bundled libc++/gmp/uv. It has to be *removed*,
        # not emptied: lake fails with "external command '' exited with code
        # 255" on an empty value. The saved script emits a real `unset`.
        #
        # LEAN_GITHASH -- overrides the githash lake keys its traces on. A dev
        # shell may export it for a different Lean build, which would make the
        # whole mathlib cache look stale.
        #
        # LEAN_NUM_THREADS -- Lake 5 has no --jobs flag; its scheduler runs on
        # Lean's task runtime, which this sizes. Each job is a clang invocation
        # on generated C, so an unbounded pool OOMs a many-core, low-memory
        # builder.
        env = Environment()
        env.unset("LEAN_CC")
        env.unset("LEAN_GITHASH")
        env.define("LEAN_NUM_THREADS", str(build_jobs(self)))
        env.vars(self).save_script("lean_env")

    def build(self):
        self._require_tools()
        bindir = Path(self._require_toolchain_bindir())
        lake = bindir / "lake"
        # Capture lake's output and surface it only on failure: a successful run
        # emits tens of thousands of progress lines.
        log = StringIO()
        try:
            for command in ("exe cache get", "build " + " ".join(self._dep_targets)):
                self.run(f'"{lake}" {command}', cwd=self.build_folder, stdout=log, stderr=log)
            objects = self._objects()
            self._bundle_deps(objects, bindir)
        except Exception:
            self.output.error(log.getvalue())
            raise
        self.output.info(
            f"{self.name}: compiled {len(objects)} objects into {ARCHIVE_NAME}"
        )

    def _objects(self):
        """Every `.c.o.export` under the dependency tree, sorted by relative
        path so the archive is byte-for-byte the same on every builder.
        ir/Cache/ belongs to mathlib's own `cache` executable, the tool
        `lake exe cache get` runs, not library code."""
        packages_dir = Path(self.build_folder) / ".lake" / PACKAGES_DIR
        objects = [
            path
            for path in packages_dir.rglob("*.c.o.export")
            if "/ir/Cache/" not in path.as_posix()
        ]
        if not objects:
            raise ConanException(f"{self.name}: lake built no objects under {packages_dir}")
        return sorted(objects, key=lambda p: p.relative_to(packages_dir).as_posix())

    def _bundle_deps(self, objects, bindir):
        # ~8,000 paths overflow ARG_MAX, so they go in a @response file. llvm-ar
        # tokenizes it like a shell: an unquoted apostrophe (as in
        # Mathlib/Tactic/LinearCombination') opens a string and swallows the
        # following lines, so each path is quoted and escaped, as lake does.
        build_dir = Path(self.build_folder)
        response_file = build_dir / "lean_deps_objects.rsp"
        response_file.write_text(
            "".join(
                '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"\n'
                for path in objects
            ),
            encoding="utf-8",
        )
        # `q` appends, so a leftover archive from an earlier run in the same
        # build folder would keep its stale members. llvm-ar taken from the
        # toolchain rather than PATH, so this reads standalone.
        archive = build_dir / ARCHIVE_NAME
        if archive.exists():
            archive.unlink()
        self.run(f'"{bindir / "llvm-ar"}" qcs "{archive}" "@{response_file}"')

    def package(self):
        build_dir = Path(self.build_folder)
        package_dir = Path(self.package_folder)
        # The lake build tree, so lake can resolve the model's imports without
        # re-elaborating mathlib. Excluded, as a model build never reads them:
        # the .c.o.export objects (bundled into the archive), each dependency's
        # own static library, and executables such as mathlib's `cache`. The
        # .c sources must stay: lake treats a module without one as stale.
        copy(
            self,
            "*",
            src=build_dir / ".lake" / PACKAGES_DIR,
            dst=package_dir / PACKAGES_DIR,
            excludes=[
                "*.c.o.export",
                "*.a",
                "*.a.trace",
                "*.a.rsp",
                "*/.lake/build/bin/*",
            ],
        )
        packages_dir = package_dir / PACKAGES_DIR
        self._shallow_git_repos(packages_dir)
        self._settle_git_indexes(packages_dir)
        copy(self, ARCHIVE_NAME, src=build_dir, dst=package_dir / LIB_DIR)
        copy(self, "lake-manifest.json", src=build_dir, dst=package_dir)
        self._package_licenses(build_dir, package_dir)

    def _package_licenses(self, build_dir, package_dir):
        # One directory per bundled project, named as in the manifest.
        manifest = json.loads((build_dir / "lake-manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["packages"]:
            name = entry["name"]
            copied = copy(
                self,
                "LICENSE*",
                src=build_dir / ".lake" / PACKAGES_DIR / name,
                dst=package_dir / "licenses" / name,
            )
            if not copied:
                raise ConanException(f"{self.name}: no LICENSE file in dependency {name}")

    def _git(self, repo, args, capture=False):
        out = StringIO() if capture else None
        self.run(f'git -C "{repo}" {args}', stdout=out, quiet=capture)
        return out.getvalue().strip() if capture else None

    def _shallow_git_repos(self, packages_dir):
        # lake clones every dependency in full; mathlib's history alone is
        # several hundred MB. Replace each .git with a one-commit repository at
        # the same HEAD and origin, fetched from the full clone next to it, so
        # no network is needed. `read-tree` fills the index without touching
        # the working tree; _settle_git_indexes then records the stat data.
        for git_dir in sorted(packages_dir.glob("*/.git")):
            repo = git_dir.parent
            rev = self._git(repo, "rev-parse HEAD", capture=True)
            url = self._git(repo, "remote get-url origin", capture=True)
            full = git_dir.with_name(".git.full")
            git_dir.rename(full)
            self._git(repo, "init -q")
            self._git(
                repo,
                f'-c uploadpack.allowAnySHA1InWant=true fetch -q --depth 1 '
                f'"file://{full}" {rev}',
            )
            self._git(repo, f"update-ref HEAD {rev}")
            self._git(repo, "read-tree HEAD")
            self._git(repo, f'remote add origin "{url}"')
            shutil.rmtree(full)

    def _settle_git_indexes(self, packages_dir):
        # Keep the consumer's `git diff HEAD` from rewriting `.git/index`.
        # Packaging and extraction keep mtimes and sizes but change inodes and
        # ctimes, which git's default stat checks see as dirty. The fresh index
        # from `read-tree` has no stat data at all; refreshing now, with every
        # file older than the new index, records it without "racily clean"
        # smudging. Extraction does not restore symlink mtimes, so tracked
        # symlinks are marked unchanged.
        for git_dir in sorted(packages_dir.glob("*/.git")):
            repo = git_dir.parent
            with open(git_dir / "config", "a", encoding="utf-8") as f:
                f.write("[core]\n\tcheckStat = minimal\n\ttrustctime = false\n")
            self._git(repo, "update-index -q --refresh")
            listing = self._git(repo, "ls-files -s -z", capture=True)
            symlinks = [
                entry.split("\t", 1)[1]
                for entry in listing.split("\0")
                if entry.startswith("120000 ")
            ]
            if symlinks:
                paths = git_dir / "conan-symlinks"
                paths.write_bytes("\0".join(symlinks).encode("utf-8") + b"\0")
                self._git(repo, f'update-index --assume-unchanged -z --stdin < "{paths}"')
                paths.unlink()

    def package_info(self):
        package_dir = Path(self.package_folder)
        # libmathlib4.a rides the ordinary CMake target, so consumers link
        # mathlib4::mathlib4 rather than being handed a path. lean4 comes
        # with it through the host requirement.
        self.cpp_info.libs = ["mathlib4"]
        self.cpp_info.libdirs = [LIB_DIR]
        self.cpp_info.includedirs = []
        # Two things have no cpp_info equivalent, so they travel as properties:
        # the olean tree, which cmake/XrplLean4.cmake symlinks in as the model's
        # .lake/packages, and the manifest this package was built against, which
        # the consumer checks its own pin against before trusting those oleans.
        self.cpp_info.set_property("lean4_packages_dir", str(package_dir / PACKAGES_DIR))
        self.cpp_info.set_property(
            "lean4_lake_manifest", str(package_dir / "lake-manifest.json")
        )
