cmake_minimum_required(VERSION 3.22)
project(test_package LANGUAGES CXX)

find_package(Corrosion REQUIRED)

corrosion_import_crate(MANIFEST_PATH rust/Cargo.toml)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE rust_test_lib)
