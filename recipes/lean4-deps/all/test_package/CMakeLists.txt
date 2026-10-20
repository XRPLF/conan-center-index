cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES C)

# lean4 (lean.h, libleanshared) must arrive through lean4-deps itself.
find_package(lean4-deps REQUIRED CONFIG)

add_executable(test_package test_package.c)
target_link_libraries(test_package PRIVATE lean4-deps::lean4-deps)
