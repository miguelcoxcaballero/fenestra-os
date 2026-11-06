# SPDX-License-Identifier: GPL-3.0-or-later
# Fenestra Shell and the Fenestra session (KWin). Build: packaging/build-rpm.sh
Name:           fenestra-shell
Version:        0.1.0
Release:        1%{?dist}
Summary:        Fenestra desktop shell and session for KWin
License:        GPL-3.0-or-later
URL:            https://github.com/miguelcoxcaballero/fenestra-os
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  cmake ninja-build gcc-c++ extra-cmake-modules python3
BuildRequires:  qt6-qtbase-devel qt6-qtbase-private-devel qt6-qtdeclarative-devel qt6-qtwayland-devel
BuildRequires:  layer-shell-qt-devel plasma-wayland-protocols-devel wayland-devel
BuildRequires:  kf6-kservice-devel kf6-kio-devel kf6-kwindowsystem-devel kf6-networkmanager-qt-devel
BuildRequires:  kf6-bluez-qt-devel pulseaudio-qt-qt6-devel kf6-kglobalaccel-devel kf6-kconfig-devel
BuildRequires:  polkit-qt6-1-devel libgweather-devel pipewire-devel

Requires:       kwin xorg-x11-server-Xwayland layer-shell-qt qt6-qtsvg kscreenlocker kscreen
Requires:       xdg-desktop-portal-kde xdg-desktop-portal-gtk kf6-bluez-qt pipewire-libs
# GNOME stays installed as the fallback session; nothing here replaces GDM.
Requires:       gdm

%description
Fenestra Shell draws the Fenestra desktop (taskbar, Start, Search, quick settings,
notifications, calendar, desktop icons, lock screen) on top of KWin. The package adds the
"Fenestra" session to GDM next to GNOME, the Fenestra window decoration and Alt+Tab switcher,
and the «Migrar a KDE» backend.

%prep
%autosetup

%build
python3 tools/build-aurorae-theme.py
%cmake -S shell -G Ninja
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_bindir}/fenestra-shell
%{_libexecdir}/fenestra/fenestra-session
%{_libexecdir}/fenestra/fenestra-session-inner
%{_libexecdir}/fenestra/fenestra-shell-crashlog
%{_libexecdir}/fenestra/fenestra-shell-failed
%{_libexecdir}/fenestra/fenestra-migrate
%{_datadir}/wayland-sessions/fenestra.desktop
%{_datadir}/applications/org.fenestra.Shell.desktop
%{_userunitdir}/fenestra-session.target
%{_userunitdir}/fenestra-shell.service
%{_userunitdir}/fenestra-shell-failed.service
%{_userunitdir}/fenestra-release-upgrade-user.service
%{_userunitdir}/fenestra-oobe-first-login.service
%{_datadir}/aurorae/themes/Fenestra-Dark
%{_datadir}/aurorae/themes/Fenestra-Light
%{_datadir}/kwin/tabbox/fenestra
%{_datadir}/plasma/look-and-feel/org.fenestra.desktop
%{_datadir}/polkit-1/actions/org.fenestra.migrate.policy
%{_datadir}/xdg-desktop-portal/fenestra-portals.conf

%changelog
* Fri Nov 06 2026 Fenestra <fenestra@users.noreply.github.com> - 0.1.0-1
- First package of the Fenestra session on KWin.
