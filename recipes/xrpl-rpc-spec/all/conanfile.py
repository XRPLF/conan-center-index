import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout

required_conan_version = ">=2.0.0"


class XrplRpcSpecConan(ConanFile):
    name = "xrpl-rpc-spec"
    description = "Consteval RPC spec DSL for XRPL: shared by Clio and xrpld"
    license = "ISC"
    url = "https://github.com/XRPLF/rpc-spec"
    package_type = "header-library"
    settings = "os", "arch", "compiler", "build_type"
    no_copy_source = True

    requires = [
        "boost/1.91.0",
    ]

    options = {
        # Selects the server backend macro handed to consumers (see package_info).
        "server": [None, "clio", "xrpld"],
    }

    default_options = {
        # Defaults to None so that consumers are forced to override
        "server": None,
        "boost/*:without_cobalt": True,
    }

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        basic_layout(self, src_folder="src")

    def package_id(self):
        self.info.clear()

    def validate(self):
        if self.settings.compiler.cppstd:
            check_min_cppstd(self, 23)
        if self.options.server == None:
            raise ConanInvalidConfiguration(
                "xrpl-rpc-spec: the 'server' option must be set to 'clio' or 'xrpld'; "
                'add \'"xrpl-rpc-spec/*:server": "clio"\' to your conanfile\'s default_options'
            )

    def package(self):
        copy(
            self,
            "*.hpp",
            src=os.path.join(self.source_folder, "include"),
            dst=os.path.join(self.package_folder, "include"),
        )
        copy(
            self,
            "*",
            src=os.path.join(self.source_folder, "cmake"),
            dst=os.path.join(self.package_folder, "lib", "cmake", "rpcspec"),
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
        self.cpp_info.defines = [f"RPCSPEC_IS_{str(self.options.server).upper()}=1"]

        # CMakeDeps includes build modules from find_package(xrpl-rpc-spec), so consumers
        # get rpcspec_generate_instantiations() without vendoring a copy of it.
        cmake_dir = os.path.join("lib", "cmake", "rpcspec")
        self.cpp_info.builddirs = [cmake_dir]
        self.cpp_info.set_property(
            "cmake_build_modules",
            [os.path.join(cmake_dir, "RpcSpecInstantiations.cmake")],
        )
