cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(xrpl-rpc-spec REQUIRED CONFIG)
find_package(xrpl REQUIRED CONFIG)

# The package ships rpcspec_generate_instantiations() as a CMake build module. Verify
# find_package() delivered it and that it generates a per-handler TU.
if(NOT COMMAND rpcspec_generate_instantiations)
    message(
        FATAL_ERROR
        "xrpl-rpc-spec: find_package() did not provide rpcspec_generate_instantiations()"
    )
endif()
rpcspec_generate_instantiations(OUT_VAR rpcspec_instantiations HANDLERS account_info)
if(NOT rpcspec_instantiations)
    message(FATAL_ERROR "xrpl-rpc-spec: rpcspec_generate_instantiations() produced no TUs")
endif()
foreach(tu IN LISTS rpcspec_instantiations)
    if(NOT EXISTS "${tu}")
        message(FATAL_ERROR "xrpl-rpc-spec: instantiation TU not generated: ${tu}")
    endif()
endforeach()

add_library(rpcspec_instantiations STATIC ${rpcspec_instantiations})
target_compile_features(rpcspec_instantiations PRIVATE cxx_std_23)
target_link_libraries(rpcspec_instantiations PRIVATE rpcspec::rpcspec xrpl::libxrpl)

add_executable(${PROJECT_NAME} test_package.cpp)
target_compile_features(${PROJECT_NAME} PRIVATE cxx_std_23)
target_link_libraries(${PROJECT_NAME} PRIVATE rpcspec::rpcspec)
