# SPDX-License-Identifier: GPL-3.0-or-later
# Fenestra rounded corners: KWin effect plugin (C++), built against the installed KWin's headers
# (kwin-devel). KWin only loads plugins built for its exact version (KWIN_PLUGIN_VERSION_STRING).
cmake_minimum_required(VERSION 3.24)
if(NOT PROJECT_NAME)
    project(fenestra-corners LANGUAGES CXX)
    set(CMAKE_CXX_STANDARD 20)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_AUTOMOC ON)
    include(GNUInstallDirs)
endif()

# KWinConfig does not look up every target its link interface names.
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets DBus Quick)
find_package(KF6CoreAddons REQUIRED)
find_package(KWin REQUIRED)

add_library(fenestra_corners MODULE corners.cpp main.cpp)
target_link_libraries(fenestra_corners PRIVATE KWin::kwin KF6::CoreAddons Qt6::Core Qt6::Gui)
set_target_properties(fenestra_corners PROPERTIES PREFIX "" OUTPUT_NAME "fenestra-corners")
install(TARGETS fenestra_corners DESTINATION ${CMAKE_INSTALL_LIBDIR}/qt6/plugins/kwin/effects/plugins)
