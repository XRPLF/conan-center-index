import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout

required_conan_version = ">=2.0.0"


class Lean4Conan(ConanFile):
    """The Lean 4 toolchain (lean, lake, leanc, headers, runtime).

    Unpacks the official leanprover/lean4 release rather than building from
    source. A release build reports the upstream `lean --githash`, which lake
    records in its build traces, so artifacts produced with it stay compatible
    with the mathlib olean cache.

    No package_type is declared: the release is at once a toolchain (bin/lean,
    bin/lake) and a mix of static and shared libraries (libLake.a beside
    libleanshared.so), with no shared/static choice to expose. Declaring
    "library" would require a `shared` option that means nothing here.
    """

    name = "lean4"
    description = "The Lean 4 theorem prover and toolchain"
    license = "Apache-2.0"
    url = "https://github.com/XRPLF/conan-center-index"
    homepage = "https://github.com/leanprover/lean4"
    topics = ("lean", "lean4", "theorem-prover", "formal-verification", "pre-built")

    # The release archives are prebuilt, so their contents depend only on the
    # platform, not on the consumer's compiler or build type. Declaring os/arch
    # alone yields exactly one binary per platform, shared by every consumer
    # configuration, instead of an identical copy per compiler/build_type.
    settings = "os", "arch"

    @property
    def _platforms(self):
        return self.conan_data["sources"][self.version]

    def layout(self):
        basic_layout(self, src_folder="src")

    def package_id(self):
        # An unpacked upstream release: the content depends on the platform and
        # nothing else. Consumer profiles inject C++ concerns into every
        # package_id through `tools.info.package_id:confs` (rippled's default
        # profile adds user.package:cppstd_version, XRPLF's ci profile also
        # user.package:libc_version); clearing them keeps
        # one binary per platform, so a consumer whose profile differs from the
        # publisher's still gets a cache hit instead of re-downloading.
        if self.info.conf is not None:
            self.info.conf.clear()

    def validate(self):
        # Also how Windows is rejected: upstream publishes a Windows release,
        # but conandata.yml does not list one, so it lands here.
        os_name, arch = str(self.settings.os), str(self.settings.arch)
        if arch not in self._platforms.get(os_name, {}):
            raise ConanInvalidConfiguration(
                f"{self.name}/{self.version}: no upstream release for "
                f"{os_name}/{arch}"
            )

    @property
    def _release_folder(self):
        # A subfolder, so the layout's generators folder stays out of package().
        return os.path.join(self.build_folder, "release")

    # Downloaded in build() into the build folder: the archive is
    # platform-specific, while source() and the source folder are shared across
    # package_ids, so a second platform would unpack over the first.
    def build(self):
        get(
            self,
            **self._platforms[str(self.settings.os)][str(self.settings.arch)],
            destination=self._release_folder,
            strip_root=True,
            keep_permissions=True,
        )

    def package(self):
        # Keep the release layout as shipped: bin/ needs lib/lean/ beside it,
        # and lake resolves the stdlib relative to its own location.
        copy(self, "*", src=self._release_folder, dst=self.package_folder)
        for name in ("LICENSE", "LICENSES/*"):
            copy(
                self,
                name,
                src=self._release_folder,
                dst=os.path.join(self.package_folder, "licenses"),
            )

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = [os.path.join("lib", "lean")]
        # Order matters: Lake before the runtime it depends on.
        self.cpp_info.libs = ["Lake", "leanshared"]
        # Conan puts bindirs on PATH for tool_requires consumers by itself, so
        # no explicit buildenv_info is needed. lean4-deps does not rely on that
        # either -- it resolves bindirs[0] and prepends it itself.
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.set_property("cmake_file_name", "lean4")
        self.cpp_info.set_property("cmake_target_name", "lean4::lean4")
