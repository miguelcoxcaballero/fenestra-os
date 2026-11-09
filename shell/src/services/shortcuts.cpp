// SPDX-License-Identifier: GPL-3.0-or-later
#include "shortcuts.h"

#include "apps.h"
#include "kbdbacklight.h"
#include "kwinintegration.h"
#include "shellcontrol.h"
#include "snip.h"
#include "status.h"
#include "system.h"

#include <utility>
#include <KGlobalAccel>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <KGlobalShortcutInfo>
#include <PulseAudioQt/Context>
#include <PulseAudioQt/Server>
#include <PulseAudioQt/Source>
#include <QAction>

Shortcuts *Shortcuts::instance()
{
    static auto *s = new Shortcuts;
    return s;
}

Shortcuts *Shortcuts::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Shortcuts::Shortcuts(QObject *parent)
    : QObject(parent)
{
}

QAction *Shortcuts::add(const QString &id, const QString &text, const QList<QKeySequence> &keys)
{
    auto *a = new QAction(text, this);
    a->setObjectName(id);
    a->setProperty("componentName", QStringLiteral("fenestra-shell"));
    a->setProperty("componentDisplayName", QStringLiteral("Fenestra Shell"));
    KGlobalAccel::self()->setDefaultShortcut(a, keys);
    KGlobalAccel::self()->setShortcut(a, keys, KGlobalAccel::Autoloading);
    return a;
}

QAction *Shortcuts::addLockable(const QString &component, const QString &id, const QString &text, const QKeySequence &key)
{
    auto *a = new QAction(text, this);
    a->setObjectName(id);
    a->setProperty("componentName", component);
    a->setProperty("componentDisplayName", QStringLiteral("Fenestra Shell"));
    bool othersOwn = false;
    for (const KGlobalShortcutInfo &o : KGlobalAccel::globalShortcutsByKey(key))
        othersOwn |= o.componentUniqueName() != component || o.uniqueName() != id;
    if (othersOwn)
        KGlobalAccel::stealShortcutSystemwide(key);
    KGlobalAccel::self()->setDefaultShortcut(a, {key});
    KGlobalAccel::self()->setShortcut(a, {key}, KGlobalAccel::NoAutoloading);
    return a;
}

void Shortcuts::volume(int delta)
{
    auto *audio = AudioStatus::instance();
    if (!audio->available())
        return;
    if (delta == 0)
        audio->setMuted(!audio->muted());
    else {
        if (audio->muted())
            audio->setMuted(false);
        audio->setVolume(std::clamp(audio->volume() + delta, 0, 100));
    }
    // The sink reports the new volume asynchronously; show the value we asked for.
    Q_EMIT osd(QStringLiteral("volume"), audio->muted() && delta == 0 ? -1 : std::clamp(audio->volume() + delta, 0, 100));
}

void Shortcuts::install()
{
    // Super alone opens Start. KWin 6.8 no longer reads kwinrc [ModifierOnlyShortcuts]: modifier-only
    // shortcuts are handled by the kglobalaccel built into KWin (GlobalShortcutsRegistry::keyEvent: a
    // released Meta with nothing pressed in between looks up the shortcut "Meta"). Plasma registers
    // "Meta" for plasmashell's "activate application launcher", and that entry in kglobalshortcutsrc
    // keeps the key even with plasmashell not running, so Super did nothing. Take the key from whatever
    // other component holds it, as Windows' Start does.
    const QKeySequence super(Qt::Key_Meta);
    for (const KGlobalShortcutInfo &info : KGlobalAccel::globalShortcutsByKey(super)) {
        if (info.componentUniqueName() != QLatin1String("fenestra-shell"))
            KGlobalAccel::stealShortcutSystemwide(super);
    }
    // Volume, brightness and keyboard light moved to lock-screen components (addLockable): drop
    // the entries they had under fenestra-shell, which would otherwise keep the keys.
    for (const char *old : {"volume-up", "volume-down", "volume-mute", "brightness-up", "brightness-down",
                            "kbd-backlight-up", "kbd-backlight-down", "kbd-backlight-toggle"}) {
        QDBusConnection::sessionBus().asyncCall(QDBusMessage::createMethodCall(
            QStringLiteral("org.kde.kglobalaccel"), QStringLiteral("/kglobalaccel"), QStringLiteral("org.kde.KGlobalAccel"), QStringLiteral("unregister"))
            << QStringLiteral("fenestra-shell") << QString::fromLatin1(old));
    }
    connect(add(QStringLiteral("start"), QStringLiteral("Start"), {super}), &QAction::triggered, ShellControl::instance(), &ShellControl::ToggleStart);
    connect(addLockable(QStringLiteral("kmix"), QStringLiteral("increase_volume"), QStringLiteral("Volume up"), QKeySequence(Qt::Key_VolumeUp)), &QAction::triggered, this, [this] { volume(+2); });
    connect(addLockable(QStringLiteral("kmix"), QStringLiteral("decrease_volume"), QStringLiteral("Volume down"), QKeySequence(Qt::Key_VolumeDown)), &QAction::triggered, this, [this] { volume(-2); });
    connect(addLockable(QStringLiteral("kmix"), QStringLiteral("mute"), QStringLiteral("Mute"), QKeySequence(Qt::Key_VolumeMute)), &QAction::triggered, this, [this] { volume(0); });
    connect(add(QStringLiteral("mic-mute"), QStringLiteral("Mute microphone"), {QKeySequence(Qt::Key_MicMute)}), &QAction::triggered, this, [this] {
        if (auto *src = PulseAudioQt::Context::instance()->server()->defaultSource()) {
            src->setMuted(!src->isMuted());
            Q_EMIT osd(QStringLiteral("microphone"), src->isMuted() ? 100 : -1); // value: the new state before the async update
        }
    });
    connect(addLockable(QStringLiteral("org_kde_powerdevil"), QStringLiteral("Increase Screen Brightness"), QStringLiteral("Brightness up"), QKeySequence(Qt::Key_MonBrightnessUp)), &QAction::triggered, this, [this] {
        Brightness::instance()->step(+5);
        Q_EMIT osd(QStringLiteral("brightness"), Brightness::instance()->percent());
    });
    connect(addLockable(QStringLiteral("org_kde_powerdevil"), QStringLiteral("Decrease Screen Brightness"), QStringLiteral("Brightness down"), QKeySequence(Qt::Key_MonBrightnessDown)), &QAction::triggered, this, [this] {
        Brightness::instance()->step(-5);
        Q_EMIT osd(QStringLiteral("brightness"), Brightness::instance()->percent());
    });
    // Keyboard backlight keys that reach userspace (most hotkeys change it in the firmware, which
    // KbdBacklight reports by itself): the banner comes from KbdBacklight::keyChanged.
    connect(addLockable(QStringLiteral("org_kde_powerdevil"), QStringLiteral("Increase Keyboard Brightness"), QStringLiteral("Keyboard backlight up"), QKeySequence(Qt::Key_KeyboardBrightnessUp)),
            &QAction::triggered, KbdBacklight::instance(), [] { KbdBacklight::instance()->step(+1); });
    connect(addLockable(QStringLiteral("org_kde_powerdevil"), QStringLiteral("Decrease Keyboard Brightness"), QStringLiteral("Keyboard backlight down"), QKeySequence(Qt::Key_KeyboardBrightnessDown)),
            &QAction::triggered, KbdBacklight::instance(), [] { KbdBacklight::instance()->step(-1); });
    connect(addLockable(QStringLiteral("org_kde_powerdevil"), QStringLiteral("Toggle Keyboard Backlight"), QStringLiteral("Keyboard backlight"), QKeySequence(Qt::Key_KeyboardLightOnOff)),
            &QAction::triggered, KbdBacklight::instance(), [] { KbdBacklight::instance()->toggle(); });
    connect(add(QStringLiteral("security-screen"), QStringLiteral("Security options (Ctrl+Alt+Del)"),
                {QKeySequence(Qt::CTRL | Qt::ALT | Qt::Key_Delete)}),
            &QAction::triggered, this, &Shortcuts::securityScreenRequested);
    connect(add(QStringLiteral("task-manager"), QStringLiteral("Task Manager"), {QKeySequence(Qt::CTRL | Qt::SHIFT | Qt::Key_Escape)}),
            &QAction::triggered, this, [] { Apps::instance()->runCommand(QStringLiteral("fenestra-taskmgr")); });
    connect(add(QStringLiteral("notification-center"), QStringLiteral("Notifications and calendar"), {QKeySequence(Qt::META | Qt::Key_N)}),
            &QAction::triggered, this, &Shortcuts::notificationCenterRequested);
    connect(add(QStringLiteral("quick-settings"), QStringLiteral("Quick settings"), {QKeySequence(Qt::META | Qt::Key_A)}),
            &QAction::triggered, this, &Shortcuts::quickSettingsRequested);
    connect(add(QStringLiteral("next-keyboard"), QStringLiteral("Next keyboard"), {QKeySequence(Qt::META | Qt::Key_Space)}),
            &QAction::triggered, this, &Shortcuts::nextKeyboardRequested);
    connect(add(QStringLiteral("search"), QStringLiteral("Search"), {QKeySequence(Qt::META | Qt::Key_S)}),
            &QAction::triggered, this, &Shortcuts::searchRequested);
    connect(add(QStringLiteral("snap-layouts"), QStringLiteral("Snap layouts"), {QKeySequence(Qt::META | Qt::Key_Z)}),
            &QAction::triggered, this, &Shortcuts::snapLayoutsRequested);
    connect(add(QStringLiteral("task-view"), QStringLiteral("Task View"), {QKeySequence(Qt::META | Qt::Key_Tab)}),
            &QAction::triggered, this, [] { KWinIntegration::instance()->toggleOverview(); });
    // Print and Super+Shift+S open the snipping overlay (Q04), as on the reference. "screenshot" keeps
    // its id (and so any saved key) from when Print saved the whole workspace straight away.
    // Windows' snipping keys belong to the snipping tool. Spectacle's .desktop file claims Meta+Shift+S
    // ("Launch Spectacle") and Print, and kglobalaccel gave the keys to Spectacle, so pressing them did
    // nothing here: take them from any other component and set ours without autoloading (a saved
    // "none" from such a conflict would otherwise stick).
    const QKeySequence printKey(Qt::Key_Print), snipKey(Qt::META | Qt::SHIFT | Qt::Key_S);
    QAction *printAction = add(QStringLiteral("screenshot"), QStringLiteral("Snip a screenshot (Print)"), {printKey});
    QAction *snipAction = add(QStringLiteral("snip"), QStringLiteral("Snip a screenshot"), {snipKey});
    for (const auto &[action, key] : {std::pair{printAction, printKey}, std::pair{snipAction, snipKey}}) {
        const QList<KGlobalShortcutInfo> owners = KGlobalAccel::globalShortcutsByKey(key);
        bool othersOwn = false;
        for (const KGlobalShortcutInfo &o : owners)
            othersOwn |= o.componentUniqueName() != QLatin1String("fenestra-shell");
        if (othersOwn)
            KGlobalAccel::stealShortcutSystemwide(key);
        if (othersOwn || KGlobalAccel::self()->shortcut(action) != QList<QKeySequence>{key})
            KGlobalAccel::self()->setShortcut(action, {key}, KGlobalAccel::NoAutoloading);
    }
    connect(printAction, &QAction::triggered, Snip::instance(), &Snip::start);
    connect(snipAction, &QAction::triggered, Snip::instance(), &Snip::start);
    connect(Snip::instance(), &Snip::saved, this, &Shortcuts::screenshotSaved);
}

void Shortcuts::takeScreenshot()
{
    Snip::instance()->captureWorkspaceNow();
}
