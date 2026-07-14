cmake_minimum_required(VERSION 3.20)
project(trading_swarm_worker LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SWARM_ENABLE_AVX2 "Enable AVX2 SIMD optimizations" ON)

if(SWARM_ENABLE_AVX2)
    include(CheckCXXCompilerFlag)
    check_cxx_compiler_flag("-mavx2" COMPILER_SUPPORTS_AVX2)
    if(COMPILER_SUPPORTS_AVX2)
        add_compile_options(-mavx2 -mfma)
        add_compile_definitions(SWARM_AVX2=1)
    endif()
endif()

find_package(Arrow REQUIRED)

add_library(swarm_core STATIC
    src/ColumnarTickStore.cpp
    src/ArrowTickReader.cpp
    src/OrderMatchingSimulator.cpp
    src/BacktestEngine.cpp
)

target_include_directories(swarm_core PUBLIC include)
target_link_libraries(swarm_core PUBLIC Arrow::arrow_shared)

add_executable(swarm_worker src/main.cpp)
target_link_libraries(swarm_worker PRIVATE swarm_core dl)

add_executable(swarm_benchmark src/benchmark_main.cpp)
target_link_libraries(swarm_benchmark PRIVATE swarm_core)

add_library(example_bollinger SHARED strategies/example_bollinger.cpp)
target_include_directories(example_bollinger PRIVATE include)
set_target_properties(example_bollinger PROPERTIES
    OUTPUT_NAME "example_bollinger"
    PREFIX ""
)
