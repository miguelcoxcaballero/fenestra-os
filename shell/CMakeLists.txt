# Fenestra Shell: the desktop UI of the Fenestra session (KWin compositor).
# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.24)
project(fenestra-shell VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
include(GNUInstallDirs)

find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Quick DBus WaylandClient WaylandClientPrivate)
find_package(LayerShellQt 6.2 REQUIRED)
find_package(PlasmaWaylandProtocols 1.13 REQUIRED)
find_package(ECM 6.0 REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH} ${ECM_FIND_MODULE_DIR})
find_package(WaylandScanner REQUIRED)
find_package(QtWaylandScanner REQUIRED)
find_package(Wayland 1.15 REQUIRED COMPONENTS Client)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(fenestra-shell
    src/main.cpp
    src/services/windowsmodel.cpp src/services/windowsmodel.h
)

# org_kde_plasma_window_management: window list and control. KWin only offers it to clients whose
# .desktop file lists it in X-KDE-Wayland-Interfaces (data/org.fenestra.Shell.desktop).
# ecm_add_qtwayland_client_protocol generates both the C glue (wayland-scanner) and the Qt wrapper.
set(protocol_sources)
ecm_add_qtwayland_client_protocol(protocol_sources
    PROTOCOL ${PLASMA_WAYLAND_PROTOCOLS_DIR}/plasma-window-management.xml
    BASENAME plasma-window-management)
target_sources(fenestra-shell PRIVATE ${protocol_sources})

qt_add_qml_module(fenestra-shell
    URI Fenestra.Shell
    VERSION 1.0
    QML_FILES
        qml/Main.qml
        qml/desktop/Wallpaper.qml
        qml/taskbar/Taskbar.qml
        qml/taskbar/TaskButton.qml
)

target_include_directories(fenestra-shell PRIVATE src/services ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(fenestra-shell PRIVATE FENESTRA_SHELL_VERSION="${PROJECT_VERSION}")

target_link_libraries(fenestra-shell PRIVATE
    Qt6::Core Qt6::Gui Qt6::Quick Qt6::DBus Qt6::WaylandClient Qt6::WaylandClientPrivate
    LayerShellQt::Interface Wayland::Client)

install(TARGETS fenestra-shell RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.fenestra.Shell.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
