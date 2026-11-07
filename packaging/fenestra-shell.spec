# SPDX-License-Identifier: GPL-3.0-or-later
# Fenestra Shell and the Fenestra session (KWin). Build: packaging/build-rpm.sh
# build-rpm.sh passes the commit it builds: Release = <commit date>.git<short id> (ordered by
# date, so every newer Fenestra build is an upgrade), e.g. 0.1.0-20261106153000.gitc27400b.fc45.
%{!?fenestra_release: %global fenestra_release 1}
Name:           fenestra-shell
Version:        0.1.0
Release:        %{fenestra_release}%{?dist}
Summary:        Fenestra desktop shell and session for KWin
License:        GPL-3.0-or-later
URL:            https://github.com/miguelcoxcaballero/fenestra-os
Source0:        %{name}-%{version}.tar.gz
%{?fenestra_commit:VCS:            %{url}/commit/%{fenestra_commit}}

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
# Power profiles: tuned-ppd provides power-profiles-daemon's D-Bus API (Quick settings, Energy saver).
Recommends:     tuned-ppd

%description
Fenestra Shell draws the Fenestra desktop (taskbar, Start, Search, quick settings,
notifications, calendar, desktop icons, lock screen) on top of KWin. The package adds the
"Fenestra" session to GDM next to GNOME, the Fenestra window decoration and Alt+Tab switcher.
«Migrar a KDE» (fenestra-migrate) is not in this package: the Fenestra overlay ships it, so
it is there before this package is installed and stays when it is removed.

%prep
%autosetup

%build
python3 tools/build-aurorae-theme.py
%cmake -S shell -G Ninja -DFENESTRA_INSTALL_MIGRATOR=OFF
%cmake_build

%install
%cmake_install

%post
# On battery, tuned-ppd's "Balanced" becomes fenestra-battery (desktop/power/tuned): any laptop.
ppd=%{_sysconfdir}/tuned/ppd.conf
if [ -f "$ppd" ] && ! grep -q '^balanced=fenestra-battery' "$ppd"; then
    if grep -q '^\[battery\]' "$ppd"; then
        sed -i -E '/^\[battery\]/,/^\[/{s/^balanced=.*/balanced=fenestra-battery/}' "$ppd"
        grep -q '^balanced=fenestra-battery' "$ppd" || sed -i '/^\[battery\]/a balanced=fenestra-battery' "$ppd"
    else
        printf '\n[battery]\nbalanced=fenestra-battery\n' >> "$ppd"
    fi
    systemctl try-restart tuned-ppd.service >/dev/null 2>&1 || :
fi

%postun
# Removed (not upgraded): give "Balanced" on battery back to tuned's own profile.
if [ "$1" -eq 0 ] && [ -f %{_sysconfdir}/tuned/ppd.conf ]; then
    sed -i 's/^balanced=fenestra-battery$/balanced=balanced-battery/' %{_sysconfdir}/tuned/ppd.conf
    systemctl try-restart tuned-ppd.service >/dev/null 2>&1 || :
fi

%files
%license LICENSE
%{_bindir}/fenestra-shell
%{_libexecdir}/fenestra/fenestra-session
%{_libexecdir}/fenestra/fenestra-session-inner
%{_libexecdir}/fenestra/fenestra-shell-crashlog
%{_libexecdir}/fenestra/fenestra-shell-failed
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
%{_datadir}/kwin/effects/fenestra-window-motion
%{_datadir}/plasma/look-and-feel/org.fenestra.desktop
%{_datadir}/xdg-desktop-portal/fenestra-portals.conf
%{_prefix}/lib/tuned/profiles/fenestra-battery

%changelog
* Fri Nov 06 2026 Fenestra <fenestra@users.noreply.github.com> - 0.1.0-1
- First package of the Fenestra session on KWin.
