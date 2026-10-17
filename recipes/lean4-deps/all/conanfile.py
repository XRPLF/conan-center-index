import os
import shutil
from io import StringIO
from pathlib import Path

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.build import build_jobs
from conan.tools.files import copy

required_conan_version = ">=2.0.0"

# The Lean libraries reachable from mathlib. `:static` compiles each module's
# generated C to a native object; the archive itself is assembled by
# _bundle_deps rather than by lake, for the reason given in _build_targets.
#
# `Cli` is absent because it compiles nothing -- it is pulled in for its oleans
# only. Nothing needs to know that, though: it has no generated C either, so it
# drops out of the check in _verified_objects on its own.
DEP_TARGETS = [
    "ProofWidgets:static",
    "ImportGraph:static",
    "LeanSearchClient:static",
    "Plausible:static",
    "Aesop:static",
    "Qq:static",
    "Batteries:static",
    "Mathlib:static",
]

PACKAGES_DIR = "packages"
LIB_DIR = "lib"
# Keep in step with cpp_info.libs in package_info: the linker derives the file
# name from the library name, so "LeanDeps" there means "libLeanDeps.a" here.
ARCHIVE_NAME = "libLeanDeps.a"


class Lean4DepsConan(ConanFile):
    """Prebuilt mathlib and its Lean dependency closure.

    Downloads mathlib's olean cache and compiles the dependency `:static`
    objects once, bundling them into lib/libLeanDeps.a. Consumers get both the
    elaboration artifacts (the olean tree, so lake can resolve imports) and the
    native objects, so they never compile mathlib themselves.

    The version tracks the Lean toolchain: mathlib tags releases against a
    toolchain, so lean4-deps/X.Y.Z bundles the mathlib revision pinned for Lean
    X.Y.Z. That coupling is what puts the Lean version into this package's
    identity -- Conan excludes tool_requires from package_id by default, and
    oleans are only loadable by the exact Lean release that produced them.

    The pinned dependency closure lives in lake/<version>/lake-manifest.json,
    exported alongside this recipe and packaged so consumers can check it. What
    has to agree is the `packages` array -- the name and revision of every
    entry -- not the whole file: the root `name` deliberately differs from any
    consumer's. If the closures diverge, lake re-resolves and the prebuilt
    oleans go unused.

    Each dependency keeps its `.git` directory. Lake resolves a dependency's
    revision and URL from it; without it lake treats the URL as changed,
    deletes the directory, re-clones and rebuilds everything -- inside this
    package. A consumer's `lake build` also runs `git diff HEAD` in each
    dependency, which may rewrite `.git/index`; package() prepares the
    repositories to prevent that, but if it happens
    `conan cache check-integrity` reports this package as modified. Harmless
    for the build.
    """

    name = "lean4-deps"
    description = "Prebuilt Lean 4 mathlib and its dependency closure"
    license = "Apache-2.0"
    url = "https://github.com/XRPLF/conan-center-index"
    homepage = "https://github.com/leanprover-community/mathlib4"
    topics = ("lean", "lean4", "mathlib", "formal-verification", "pre-built")

    package_type = "static-library"
    # olean files are arch-specific memory images and the bundled objects are
    # native code, so the package varies by platform -- but not by the
    # consumer's compiler or build type, since everything here is produced by
    # the Lean toolchain's own bundled clang.
    settings = "os", "arch"

    def export_sources(self):
        # The lake pin, one workspace per version under lake/<version>/, flattened
        # into the source root. lakefile.toml declares the workspace,
        # lake-manifest.json fixes the dependency closure (and is packaged so
        # consumers can check that theirs matches). lean-toolchain looks
        # redundant next to the recipe version but is required: `lake exe cache
        # get` reads it directly, throwing "no such file or directory" when it is
        # absent and refusing to use the olean cache (exit 1) when it disagrees
        # with mathlib's own toolchain. Do not drop it.
        copy(
            self,
            "*",
            src=os.path.join(self.recipe_folder, "lake", self.version),
            dst=self.export_sources_folder,
        )

    def package_id(self):
        # Everything here is produced by the Lean toolchain's own bundled clang,
        # so the content depends on the platform and nothing else. Consumer
        # profiles inject C++ concerns into every package_id through
        # `tools.info.package_id:confs` (rippled's default profile adds
        # user.package:cppstd_version, XRPLF's ci profile also
        # user.package:libc_version); clearing them keeps one binary per
        # platform, so a consumer whose profile differs from the publisher's
        # still gets a cache hit instead of rebuilding mathlib.
        if self.info.conf is not None:
            self.info.conf.clear()

    def validate(self):
        if self.settings.os == "Windows":
            raise ConanInvalidConfiguration(
                f"{self.name}/{self.version}: Windows is not supported yet"
            )

    def build_requirements(self):
        self.tool_requires(f"lean4/{self.version}")

    def _require_toolchain_bindir(self):
        """The tool_requires toolchain, and only that one. Raises if it cannot run.

        Never a lean/lake found on PATH: lake records Lean's githash in its build
        traces, so a same-version but differently-built toolchain would produce
        oleans the published package cannot be reused with. Taking it from the
        dependency graph keeps the output reproducible.

        The upstream release names the FHS loader (/lib64/ld-linux-x86-64.so.2)
        in PT_INTERP, so it needs that loader present -- on NixOS via nix-ld.
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
            raise ConanException(
                f"{self.name}/{self.version}: the lean4 package's binaries "
                f"cannot be executed. They need the FHS loader "
                f"/lib64/ld-linux-x86-64.so.2. On NixOS, provide it by enabling "
                f"nix-ld (programs.nix-ld.enable = true); other distributions "
                f"have it already."
            ) from exc
        return bindir

    def _prepare_environment(self, bindir):
        """Point the build at the toolchain in `bindir`, and size its job pool.

        PATH -- put the toolchain first, so lake's own lookups (leanc, clang)
        and the archive step's llvm-ar all resolve to the same install.

        LEAN_CC -- leanc invokes it when set, and otherwise its own bundled
        clang. It emits link flags assuming that clang's default library search
        paths, so an ambient LEAN_CC pointing at the system compiler fails to
        find Lean's bundled libc++/gmp/uv. It has to be *removed*, not emptied:
        lake fails with "external command '' exited with code 255" on an empty
        value. conan.tools.env.Environment.unset() only emits a real `unset` in
        generated scripts; applied in-process it assigns an empty string.

        LEAN_GITHASH -- overrides the githash lake keys its traces on. A dev
        shell may export it for a different Lean build, which would make the
        whole mathlib cache look stale.

        LEAN_NUM_THREADS -- Lake 5 has no --jobs flag; its scheduler runs on
        Lean's task runtime, which this sizes. Each job is a clang invocation on
        generated C, so an unbounded pool OOMs a many-core, low-memory builder.

        build() restores the environment afterwards: Lean's bin/ holds clang,
        ld.lld and llvm-ar, which would otherwise shadow the compiler of every
        package built later in the same `conan install`.
        """
        os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
        os.environ.pop("LEAN_CC", None)
        os.environ.pop("LEAN_GITHASH", None)
        os.environ["LEAN_NUM_THREADS"] = str(build_jobs(self))

    def build(self):
        bindir = self._require_toolchain_bindir()
        saved_environ = dict(os.environ)
        try:
            self._prepare_environment(bindir)
            self._build(Path(bindir))
        finally:
            os.environ.clear()
            os.environ.update(saved_environ)

    def _build(self, bindir):
        lake = bindir / "lake"

        # Capture lake's output and surface it only on failure: a successful run
        # emits tens of thousands of progress lines.
        log = StringIO()
        try:
            self.run(
                f'"{lake}" exe cache get',
                cwd=self.build_folder,
                stdout=log,
                stderr=log,
            )
            lake_failed = self._build_targets(lake, log)
            objects = self._verified_objects()
            if lake_failed:
                self.output.warning(
                    f"{self.name}: tolerating lake's failure, all "
                    f"{len(objects)} objects are present (expected on macOS, "
                    f"see _build_targets)"
                )
            self._bundle_deps(objects, bindir)
        except Exception:
            self.output.error(log.getvalue())
            raise
        self.output.info(
            f"{self.name}: compiled {len(objects)} objects into {ARCHIVE_NAME}"
        )

    def _build_targets(self, lake, log):
        """Compile DEP_TARGETS. Returns True if lake reported a failure.

        lake's `:static` step archives a library by passing every object on one
        command line -- 1,155,381 bytes across 7,652 arguments for mathlib. That
        sits comfortably under Linux's limit (a quarter of the stack rlimit) but
        over macOS's fixed kern.argmax of 1 MiB, so on macOS lake fails after
        every object has already been compiled.

        We never use lake's archives -- _bundle_deps builds its own with a
        response file -- so that failure is harmless. Harmless only if the
        objects really are all there, though, so the status is returned rather
        than discarded and _verified_objects has to pass either way.
        """
        try:
            self.run(
                f'"{lake}" build ' + " ".join(DEP_TARGETS),
                cwd=self.build_folder,
                stdout=log,
                stderr=log,
            )
        except ConanException:
            return True
        return False

    def _verified_objects(self):
        """The native objects, checked against the C sources they come from.

        A lake failure is tolerated above, so something else has to establish
        that the compilation really finished. Every generated `.c` must have a
        matching `.c.o.export`: the sources arrive with `lake exe cache get`,
        independently of the compile, so they are an authoritative statement of
        what should have been built. That catches a dependency which failed
        outright and one which compiled only partially -- neither of which is
        visible in an object count.

        Returned sorted by path relative to the packages tree. The order is
        load-bearing: _bundle_deps names archive members positionally, so
        directory iteration order would otherwise leak into the archive bytes
        and the same objects would produce a different archive on every builder.

        ir/Cache/ is skipped: those belong to mathlib's own `cache` executable,
        the tool `lake exe cache get` runs. Build tooling, not library code a
        consumer links against.
        """
        packages_dir = Path(self.build_folder) / ".lake" / PACKAGES_DIR
        sources, objects = set(), {}
        for dirpath, _dirs, filenames in os.walk(packages_dir):
            if "/ir/Cache/" in (dirpath.replace("\\", "/") + "/"):
                continue
            for name in filenames:
                path = Path(dirpath) / name
                key = str(path.relative_to(packages_dir))
                if name.endswith(".c.o.export"):
                    objects[key[: -len(".c.o.export")]] = path
                elif name.endswith(".c"):
                    sources.add(key[: -len(".c")])

        # Guard the degenerate case first: with no sources at all the
        # comparison below would pass vacuously.
        if not sources:
            raise ConanException(
                f"{self.name}: no generated C sources under {packages_dir}, so "
                f"there is nothing to verify the objects against. Expected "
                f"`lake exe cache get` to have populated the dependency tree."
            )
        missing = sorted(sources - set(objects))
        if missing:
            raise ConanException(
                f"{self.name}: {len(missing)} of {len(sources)} generated C "
                f"sources have no compiled object, so the build did not "
                f"finish: " + ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
            )
        # Sorted on the full relative path rather than the suffix-stripped key:
        # the two differ (an apostrophe sorts before the '.' of the suffix, as
        # in Mathlib/Tactic/LinearCombination') and the archive member's
        # identity is the full path.
        return sorted(objects.values(), key=lambda p: str(p.relative_to(packages_dir)))

    def _bundle_deps(self, objects, bindir):
        # Two limits to dodge when archiving ~8,000 objects:
        #  - llvm-ar rejects the batch on long member names, so each object gets
        #    a short-named symlink;
        #  - the full path list overflows ARG_MAX, so it goes in a @response
        #    file rather than on the command line.
        build_dir = Path(self.build_folder)
        symlink_dir = build_dir / "lean_deps_symlinks"
        shutil.rmtree(symlink_dir, ignore_errors=True)
        symlink_dir.mkdir()

        symlinks = [symlink_dir / f"obj{i}.o" for i in range(len(objects))]
        for symlink, target in zip(symlinks, objects):
            symlink.symlink_to(target)

        response_file = build_dir / "lean_deps_objects.rsp"
        response_file.write_text(
            "".join(f"{symlink}\n" for symlink in symlinks), encoding="utf-8"
        )

        # Taken from the toolchain rather than PATH, so this reads standalone
        # and cannot pick up a different ar.
        archive = build_dir / ARCHIVE_NAME
        self.run(f'"{Path(bindir) / "llvm-ar"}" qcs "{archive}" "@{response_file}"')

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
        self._settle_git_indexes(package_dir / PACKAGES_DIR)
        copy(self, ARCHIVE_NAME, src=build_dir, dst=package_dir / LIB_DIR)
        copy(
            self,
            "lake-manifest.json",
            src=build_dir,
            dst=package_dir,
        )
        copy(
            self,
            "LICENSE*",
            src=build_dir / ".lake" / PACKAGES_DIR / "mathlib",
            dst=package_dir / "licenses",
        )

    def _settle_git_indexes(self, packages_dir):
        # Keep the consumer's `git diff HEAD` from rewriting `.git/index`.
        # Packaging and extraction keep mtimes and sizes but change inodes and
        # ctimes, which git's default stat checks see as dirty. And lake's clone
        # wrote each index in the same second as the checkout, so git smudged
        # those "racily clean" entries; refreshing now, with every file older
        # than the new index, records their real stat data. Extraction does not
        # restore symlink mtimes, so tracked symlinks are marked unchanged.
        for git_dir in sorted(packages_dir.glob("*/.git")):
            repo = git_dir.parent
            with open(git_dir / "config", "a", encoding="utf-8") as f:
                f.write("[core]\n\tcheckStat = minimal\n\ttrustctime = false\n")
            self.run(f'git -C "{repo}" update-index -q --refresh')
            listing = StringIO()
            self.run(f'git -C "{repo}" ls-files -s -z', stdout=listing, quiet=True)
            symlinks = [
                entry.split("\t", 1)[1]
                for entry in listing.getvalue().split("\0")
                if entry.startswith("120000 ")
            ]
            if symlinks:
                self.run(
                    f'git -C "{repo}" update-index --assume-unchanged -- '
                    + " ".join(f'"{path}"' for path in symlinks)
                )

    def package_info(self):
        package_dir = Path(self.package_folder)
        # libLeanDeps.a rides the ordinary CMake target, so consumers link
        # lean4-deps::lean4-deps rather than being handed a path.
        self.cpp_info.libs = ["LeanDeps"]
        self.cpp_info.libdirs = [LIB_DIR]
        self.cpp_info.includedirs = []
        # Two things have no cpp_info equivalent, so they travel as properties:
        # the olean tree, which cmake/XrplLean4.cmake symlinks in as the model's
        # .lake/packages, and the manifest this package was built against, which
        # the consumer checks its own pin against before trusting those oleans.
        self.cpp_info.set_property("packages", str(package_dir / PACKAGES_DIR))
        self.cpp_info.set_property(
            "lake_manifest", str(package_dir / "lake-manifest.json")
        )
