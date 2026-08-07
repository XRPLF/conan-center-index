import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get

required_conan_version = ">=2.0"


class CorrosionConan(ConanFile):
    name = "corrosion"
    description = "Marrying Rust and CMake - Easy Rust and C/C++ Integration!"
    license = "MIT"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/corrosion-rs/corrosion"
    topics = ("cmake", "rust", "cargo", "build-scripts")
    package_type = "build-scripts"
    settings = "os", "arch", "compiler", "build_type"

    def layout(self):
        cmake_layout(self, src_folder="src")

    def package_id(self):
        self.info.clear()

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        # Corrosion is consumed as a set of CMake modules. `CORROSION_INSTALL_ONLY`
        # skips `include(Corrosion)`, which would otherwise require a Rust toolchain
        # to be present while building this package. Rust is only needed by consumers.
        tc.cache_variables["CORROSION_INSTALL_ONLY"] = True
        tc.cache_variables["CORROSION_BUILD_TESTS"] = False
        # The CMake modules are installed to ${CMAKE_INSTALL_DATADIR}/cmake
        tc.cache_variables["CMAKE_INSTALL_DATAROOTDIR"] = "res"
        tc.generate()

    def build(self):
        # Nothing is compiled, the install rules only copy the CMake modules
        cmake = CMake(self)
        cmake.configure()

    def package(self):
        copy(self, "LICENSE",
             src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        # Corrosion ships its own CorrosionConfig.cmake, don't shadow it
        self.cpp_info.set_property("cmake_find_mode", "none")
        self.cpp_info.set_property("cmake_file_name", "Corrosion")

        self.cpp_info.builddirs = [
            os.path.join("lib", "cmake", "Corrosion"),
            os.path.join("res", "cmake"),
        ]
        self.cpp_info.resdirs = ["res"]
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = []
