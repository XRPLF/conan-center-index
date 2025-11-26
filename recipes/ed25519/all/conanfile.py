from conan import ConanFile, tools
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.files import apply_conandata_patches, export_conandata_patches, get
from conan.tools.scm import Git

required_conan_version = ">=2.0.0"

class EdDonnaConan(ConanFile):
    name = "ed25519"
    description = "ed25519 is an Elliptic Curve Digital Signature Algorithm."
    url = "https://github.com/floodyberry/ed25519-donna.git"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        git = Git(self)
        git.fetch_commit(**self.conan_data["sources"][self.version])
        apply_conandata_patches(self)

    def generate(self):
        tc = CMakeToolchain(self)
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
        self.cpp_info.libs = ["ed25519"]
        self.cpp_info.names["cmake_find_package"] = "ed25519"
        self.cpp_info.names["cmake_find_package_multi"] = "ed25519"

    def package_id(self):
        self.info.clear()
