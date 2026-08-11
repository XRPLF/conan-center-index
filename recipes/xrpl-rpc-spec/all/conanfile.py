from conan import ConanFile
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout
import os

required_conan_version = ">=2.0.0"


class XrplRpcSpecConan(ConanFile):
    name = "xrpl-rpc-spec"
    description = "Consteval RPC spec DSL for XRPL: shared by Clio and xrpld"
    license = "ISC"
    url = "https://github.com/XRPLF/rpc-spec"
    package_type = "header-library"
    settings = "os", "arch", "compiler", "build_type"
    no_copy_source = True

    def requirements(self):
        # The headers include <boost/json/...>, so consumers need those headers too.
        self.requires("boost/[>=1.83 <2]", transitive_headers=True)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        basic_layout(self, src_folder="src")

    def package_id(self):
        # Header-only: the package is identical for every configuration.
        self.info.clear()

    def validate(self):
        # The DSL is consteval-heavy and requires C++23. Only enforced when the
        # consumer pins compiler.cppstd; profiles that leave it unset are not failed.
        if self.settings.compiler.cppstd:
            check_min_cppstd(self, 23)

    def package(self):
        copy(
            self,
            "*.hpp",
            src=os.path.join(self.source_folder, "include"),
            dst=os.path.join(self.package_folder, "include"),
        )
        copy(
            self,
            "LICENSE.md",
            src=self.source_folder,
            dst=os.path.join(self.package_folder, "licenses"),
        )

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.set_property("cmake_file_name", "xrpl-rpc-spec")
        self.cpp_info.set_property("cmake_target_name", "rpcspec::rpcspec")
        self.cpp_info.requires = ["boost::json"]
