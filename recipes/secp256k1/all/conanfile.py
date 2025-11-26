from conan import ConanFile, tools
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.files import get

required_conan_version = ">=2.0.0"

class SecpConan(ConanFile):
    name = "secp256k1"
    description = "High-performance high-assurance C library for digital signatures and other cryptographic primitives on the secp256k1 elliptic curve."
    url = "https://github.com/bitcoin-core/secp256k1.git"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        # Disable all tests and benchmarks.
        tc.variables["SECP256K1_INSTALL"] = 1
        tc.variables["SECP256K1_BUILD_BENCHMARK"] = 0
        tc.variables["SECP256K1_BUILD_TESTS"] = 0
        tc.variables["SECP256K1_BUILD_EXHAUSTIVE_TESTS"] = 0
        tc.variables["SECP256K1_BUILD_CTIME_TESTS"] = 0
        tc.variables["SECP256K1_BUILD_EXAMPLES"] = 0
        tc.generate()

        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.verbose = True
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.verbose = True
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["secp256k1"]
        self.cpp_info.names["cmake_find_package"] = "secp256k1"
        self.cpp_info.names["cmake_find_package_multi"] = "secp256k1"

    def package_id(self):
        self.info.clear()
