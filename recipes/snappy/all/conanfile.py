from conan import ConanFile
from conan.tools.build import check_min_cppstd, stdcpp_library
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get, rmdir
from conan.tools.scm import Version
import os

required_conan_version = ">=2.1"


class SnappyConan(ConanFile):
    name = "snappy"
    description = "A fast compressor/decompressor"
    topics = ("google", "compressor", "decompressor")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/google/snappy"
    license = "BSD-3-Clause"

    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_bmi2": [True, False, "auto"],
        "with_ssse3": [True, False, "auto"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_bmi2": "auto",
        "with_ssse3": "auto",
    }

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC
        if self.settings.arch not in ["x86", "x86_64"]:
            del self.options.with_bmi2
            del self.options.with_ssse3

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def validate(self):
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, 11)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["SNAPPY_BUILD_TESTS"] = False
        if Version(self.version) >= "1.1.8":
            tc.variables["SNAPPY_FUZZING_BUILD"] = False
            # Don't use these avx options. These are useless.
            # https://github.com/conan-io/conan-center-index/pull/16495
            tc.variables["SNAPPY_REQUIRE_AVX"] = False
            tc.variables["SNAPPY_REQUIRE_AVX2"] = False
            tc.variables["SNAPPY_INSTALL"] = True
        if Version(self.version) >= "1.1.9":
            tc.variables["SNAPPY_BUILD_BENCHMARKS"] = False
        if self.settings.arch in ["x86", "x86_64"]:
            if self.options.with_bmi2 != "auto":
                tc.variables["SNAPPY_HAVE_BMI2"] = self.options.with_bmi2
            if self.options.with_ssse3 != "auto":
                tc.variables["SNAPPY_HAVE_SSSE3"] = self.options.with_ssse3
        if Version(self.version) < "1.2.2": # pylint: disable=conan-condition-evals-to-constant
            tc.cache_variables["CMAKE_POLICY_VERSION_MINIMUM"] = "3.5" # CMake 4 support
        tc.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "COPYING", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Snappy")
        self.cpp_info.set_property("cmake_target_name", "Snappy::snappy")
        # TODO: back to global scope in conan v2 once cmake_find_package* generators removed
        self.cpp_info.components["snappylib"].libs = ["snappy"]
        if not self.options.shared:
            if self.settings.os in ["Linux", "FreeBSD"]:
                self.cpp_info.components["snappylib"].system_libs.append("m")

        self.cpp_info.components["snappylib"].set_property("cmake_target_name", "Snappy::snappy")
