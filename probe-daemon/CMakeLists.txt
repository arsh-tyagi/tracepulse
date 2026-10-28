cmake_minimum_required(VERSION 3.20)
project(TracePulseProbeDaemon VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Optimization flags
if(MSVC)
    add_compile_options(/W4 /O2 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -O3 -pthread)
endif()

find_package(CURL REQUIRED)
find_package(Threads REQUIRED)

include_directories(include)

file(GLOB SOURCES 
    src/main.cpp
    src/curl_client.cpp
    src/thread_pool.cpp
    src/config_manager.cpp
    src/batch_queue.cpp
)

add_executable(probe_daemon ${SOURCES})

target_link_libraries(probe_daemon PRIVATE 
    CURL::libcurl 
    Threads::Threads
)
