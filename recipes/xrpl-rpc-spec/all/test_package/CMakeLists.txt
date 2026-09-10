cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(xrpl-rpc-spec REQUIRED CONFIG)

# The package ships rpcspec_generate_instantiations() as a CMake build module. Verify
# find_package() delivered it and that it generates a per-handler TU. The generated TU is
# not compiled here: it includes a spec header, which needs the consumer's xrpl headers.
if(NOT COMMAND rpcspec_generate_instantiations)
    message(
        FATAL_ERROR
        "xrpl-rpc-spec: find_package() did not provide rpcspec_generate_instantiations()"
    )
endif()
rpcspec_generate_instantiations(OUT_VAR rpcspec_instantiations HANDLERS account_info)
if(NOT EXISTS "${rpcspec_instantiations}")
    message(FATAL_ERROR "xrpl-rpc-spec: no instantiation TU generated for account_info")
endif()

add_executable(${PROJECT_NAME} test_package.cpp)
target_compile_features(${PROJECT_NAME} PRIVATE cxx_std_23)
target_link_libraries(${PROJECT_NAME} PRIVATE rpcspec::rpcspec)
