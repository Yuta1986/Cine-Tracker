cmake_minimum_required(VERSION 3.20)

project(cinetracker_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(PYBIND11_FINDPYTHON ON)
find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)
find_package(Ceres CONFIG REQUIRED)

pybind11_add_module(cinetracker_native src/cinetracker_native.cpp)
target_link_libraries(cinetracker_native PRIVATE Ceres::ceres)
