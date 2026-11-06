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
find_package(KF6Service 6.10 REQUIRED)
find_package(KF6KIO 6.10 REQUIRED)
find_package(KF6WindowSystem 6.10 REQUIRED)
find_package(KF6NetworkManagerQt 6.10 REQUIRED)
find_package(KF6PulseAudioQt 1.5 REQUIRED)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH} ${ECM_FIND_MODULE_DIR})
find_package(WaylandScanner REQUIRED)
find_package(QtWaylandScanner REQUIRED)
find_package(Wayland 1.15 REQUIRED COMPONENTS Client)
find_package(PkgConfig REQUIRED)
pkg_check_modules(GWEATHER REQUIRED IMPORTED_TARGET gweather4 gio-2.0)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(fenestra-shell
    src/main.cpp
    src/core/testprobe.cpp src/core/testprobe.h
    src/core/shellsettings.cpp src/core/shellsettings.h
    src/core/theme.cpp src/core/theme.h
    src/core/shellutil.h
    src/core/shellcontrol.h
    src/services/apps.cpp src/services/apps.h
    src/services/taskbarmodel.cpp src/services/taskbarmodel.h
    src/services/weather.cpp src/services/weather.h
    src/services/status.cpp src/services/status.h
    src/services/trayitems.cpp src/services/trayitems.h
    src/services/startservices.cpp src/services/startservices.h
    src/services/search.cpp src/services/search.h
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

set_source_files_properties(qml/design/Strings.qml qml/design/Metrics.qml qml/design/Motion.qml qml/ShellState.qml
    PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

qt_add_qml_module(fenestra-shell
    URI Fenestra.Shell
    VERSION 1.0
    QML_FILES
        qml/Main.qml
        qml/ShellState.qml
        qml/components/ContextMenu.qml
        qml/components/Flyout.qml
        qml/components/MenuRow.qml
        qml/components/ShellPopup.qml
        qml/components/SymbolicIcon.qml
        qml/design/Metrics.qml
        qml/design/Motion.qml
        qml/design/Strings.qml
        qml/desktop/Wallpaper.qml
        qml/search/SearchFlyout.qml
        qml/start/AppTile.qml
        qml/start/SectionHeader.qml
        qml/start/StartMenu.qml
        qml/taskbar/Clock.qml
        qml/taskbar/SearchButton.qml
        qml/taskbar/TaskButton.qml
        qml/taskbar/TaskPreview.qml
        qml/taskbar/Taskbar.qml
        qml/taskbar/WeatherButton.qml
        qml/tray/Tray.qml
        qml/tray/TrayButton.qml
)

target_include_directories(fenestra-shell PRIVATE src/core src/services ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(fenestra-shell PRIVATE FENESTRA_SHELL_VERSION="${PROJECT_VERSION}")

target_link_libraries(fenestra-shell PRIVATE
    Qt6::Core Qt6::Gui Qt6::Quick Qt6::DBus Qt6::WaylandClient Qt6::WaylandClientPrivate
    LayerShellQt::Interface Wayland::Client
    KF6::Service KF6::KIOGui KF6::WindowSystem KF6::NetworkManagerQt KF6::PulseAudioQt PkgConfig::GWEATHER)

install(TARGETS fenestra-shell RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.fenestra.Shell.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)

# The session itself (GDM entry, launcher, systemd user units, crash notice): ../session.
option(FENESTRA_INSTALL_SESSION "Install the Fenestra session files from ../session" ON)
if(FENESTRA_INSTALL_SESSION)
    set(session_dir ${CMAKE_CURRENT_SOURCE_DIR}/../session)
    install(FILES ${session_dir}/wayland-sessions/fenestra.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/wayland-sessions)
    install(PROGRAMS ${session_dir}/libexec/fenestra-session ${session_dir}/libexec/fenestra-session-inner
                     ${session_dir}/libexec/fenestra-shell-crashlog ${session_dir}/libexec/fenestra-shell-failed
            DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/fenestra)
    install(FILES ${session_dir}/systemd/fenestra-session.target ${session_dir}/systemd/fenestra-shell.service
                  ${session_dir}/systemd/fenestra-shell-failed.service
            DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/systemd/user)
endif()
