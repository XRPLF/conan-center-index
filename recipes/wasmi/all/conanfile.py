from conan import ConanFile, tools
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.env import Environment
from conan.tools.files import get
import os

required_conan_version = ">=2.0.0"

class WasmiConan(ConanFile):
    name = "wasmi"
    license = "Apache License v2.0"
    url = "https://github.com/wasmi-labs/wasmi.git"
    description = "WebAssembly (Wasm) interpreter"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [False], "coverage": [True, False]}
    default_options = {"shared": False, "coverage": False}

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

        if self.options.coverage:
            env = Environment()
            env.append("RUSTFLAGS", "-Cinstrument-coverage", separator=" ")
            env.vars(self, scope="build").save_script("wasmi_coverage")

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(self.source_folder, "crates", "c_api"))
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["wasmi"]

        if self.options.coverage:
            compiler = str(self.settings.compiler)
            if compiler in ("clang", "apple-clang"):
                coverage_flags = ["-fprofile-instr-generate", "-fcoverage-mapping"]
                self.cpp_info.cflags.extend(coverage_flags)
                self.cpp_info.cxxflags.extend(coverage_flags)
                self.cpp_info.exelinkflags.extend(coverage_flags)
                self.cpp_info.sharedlinkflags.extend(coverage_flags)
            else:
                self.output.warning(
                    "wasmi coverage=True has no effect with compiler '%s': libwasmi "
                    "is instrumented with LLVM source-based coverage, which requires "
                    "a Clang consumer to link the LLVM profiling runtime." % compiler
                )
