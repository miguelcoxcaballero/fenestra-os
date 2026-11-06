# Qt test of the shell's icon lookup with an imported pack (tests/icon-pack/run.sh builds it in the
# KWin lab image). Compiles shell/src/core/iconoverrides.cpp, the code fenestra-shell uses.
cmake_minimum_required(VERSION 3.24)
project(iconpack-test LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.8 REQUIRED COMPONENTS Gui Quick)
set(SHELL ${CMAKE_CURRENT_SOURCE_DIR}/../../../shell)
add_executable(iconpack-test main.cpp ${SHELL}/src/core/iconoverrides.cpp ${SHELL}/src/core/iconoverrides.h)
target_include_directories(iconpack-test PRIVATE ${SHELL}/src/core)
target_link_libraries(iconpack-test PRIVATE Qt6::Gui Qt6::Quick)
