from gi.repository import Gio, GLib
XML = '''<node>
<interface name="org.freedesktop.login1.Manager">
 <method name="GetSession"><arg type="s" direction="in"/><arg type="o" direction="out"/></method>
 <method name="GetSessionByPID"><arg type="u" direction="in"/><arg type="o" direction="out"/></method>
 <method name="GetUser"><arg type="u" direction="in"/><arg type="o" direction="out"/></method>
 <method name="ListSessions"><arg type="a(susso)" direction="out"/></method>
 <method name="Inhibit"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="h" direction="out"/></method>
 <method name="CanSuspend"><arg type="s" direction="out"/></method>
 <method name="CanHibernate"><arg type="s" direction="out"/></method>
 <method name="CanPowerOff"><arg type="s" direction="out"/></method>
 <method name="CanReboot"><arg type="s" direction="out"/></method>
 <method name="CanRebootToBootLoaderMenu"><arg type="s" direction="out"/></method>
 <signal name="PrepareForSleep"><arg type="b"/></signal>
 <property name="PreparingForSleep" type="b" access="read"/>
</interface>
<interface name="org.freedesktop.login1.Session">
 <property name="Active" type="b" access="read"/><property name="Id" type="s" access="read"/>
 <property name="LockedHint" type="b" access="read"/><property name="Class" type="s" access="read"/>
 <property name="Type" type="s" access="read"/><property name="State" type="s" access="read"/>
 <property name="Remote" type="b" access="read"/><property name="Seat" type="(so)" access="read"/>
 <method name="SetLockedHint"><arg type="b" direction="in"/></method>
 <method name="Lock"/><method name="Unlock"/>
 <signal name="Lock"/><signal name="Unlock"/>
</interface>
<interface name="org.freedesktop.login1.User">
 <property name="Display" type="(so)" access="read"/><property name="Sessions" type="a(so)" access="read"/>
 <property name="RuntimePath" type="s" access="read"/>
</interface>
</node>'''
node = Gio.DBusNodeInfo.new_for_xml(XML)
S = '/org/freedesktop/login1/session/c1'; UP = '/org/freedesktop/login1/user/_1000'
def call(conn, sender, path, iface, method, params, inv):
    out = {'GetSession': GLib.Variant('(o)', (S,)), 'GetSessionByPID': GLib.Variant('(o)', (S,)),
           'GetUser': GLib.Variant('(o)', (UP,)), 'ListSessions': GLib.Variant('(a(susso))', ([('c1', 1000, 'alex', 'seat0', S)],)),
           }.get(method)
    if method.startswith('Can'): out = GLib.Variant('(s)', ('yes',))
    if method == 'Inhibit':
        r, w = __import__('os').pipe(); fl = Gio.UnixFDList.new(); fl.append(w); inv.return_value_with_unix_fd_list(GLib.Variant('(h)', (0,)), fl); return
    inv.return_value(out)
def prop(conn, sender, path, iface, name):
    v = {'PreparingForSleep': GLib.Variant('b', False), 'Active': GLib.Variant('b', True), 'Id': GLib.Variant('s', 'c1'),
         'LockedHint': GLib.Variant('b', False), 'Class': GLib.Variant('s', 'user'), 'Type': GLib.Variant('s', 'wayland'),
         'State': GLib.Variant('s', 'active'), 'Remote': GLib.Variant('b', False), 'Seat': GLib.Variant('(so)', ('seat0', '/org/freedesktop/login1/seat/seat0')),
         'Display': GLib.Variant('(so)', ('c1', S)), 'Sessions': GLib.Variant('a(so)', [('c1', S)]), 'RuntimePath': GLib.Variant('s', '/run/user/1000')}
    return v.get(name)
def acquired(conn, name):
    for path, i in (('/org/freedesktop/login1', 0), (S, 1), ('/org/freedesktop/login1/session/auto', 1), (UP, 2)):
        conn.register_object(path, node.interfaces[i], call, prop, None)
Gio.bus_own_name(Gio.BusType.SYSTEM, 'org.freedesktop.login1', 0, acquired, None, None)

# Minimal org.gnome.DisplayManager: GNOME Shell only shows the login dialog when GDM answers
# (LoginManager.canLock reads Manager.Version). Sessions cannot really be opened here.
GDM_XML = '''<node><interface name="org.gnome.DisplayManager.Manager">
 <method name="RegisterSession"><arg type="a{sv}" direction="in"/></method>
 <method name="RegisterDisplay"><arg type="a{ss}" direction="in"/></method>
 <method name="OpenSession"><arg type="s" direction="out"/></method>
 <method name="OpenReauthenticationChannel"><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
 <property name="Version" type="s" access="read"/>
</interface></node>'''
gdm_node = Gio.DBusNodeInfo.new_for_xml(GDM_XML)
# GDM hands the greeter a private peer-to-peer D-Bus server (OpenSession) with the Greeter and
# UserVerifier interfaces at /org/gnome/DisplayManager/Session; the login dialog only loads
# its user list after that works. Interfaces from GDM's daemon/gdm-session.xml (signatures
# only). Every call is answered neutrally: no timed login, nothing ever authenticates.
import os
GREETER_ADDR = 'unix:path=/run/fake-gdm-greeter'
try:
    os.unlink('/run/fake-gdm-greeter')
except OSError:
    pass
SESSION_XML = '<node><interface name="org.gnome.DisplayManager.UserVerifier"><method name="EnableExtensions"><arg type="as" name="extensions" direction="in" /></method><method name="BeginVerification"><arg type="s" name="service_name" direction="in" /></method><method name="BeginVerificationForUser"><arg type="s" name="service_name" direction="in" /><arg type="s" name="username" direction="in" /></method><method name="AnswerQuery"><arg type="s" name="service_name" direction="in" /><arg type="s" name="answer" direction="in" /></method><method name="Cancel" /><signal name="ConversationStarted"><arg type="s" name="service_name" /></signal><signal name="ConversationStopped"><arg type="s" name="service_name" /></signal><signal name="ReauthenticationStarted"><arg type="i" name="pid_of_caller" /></signal><signal name="Info"><arg type="s" name="service_name" /><arg type="s" name="info" /></signal><signal name="Problem"><arg type="s" name="service_name" /><arg type="s" name="problem" /></signal><signal name="InfoQuery"><arg type="s" name="service_name" /><arg type="s" name="query" /></signal><signal name="SecretInfoQuery"><arg type="s" name="service_name" /><arg type="s" name="query" /></signal><signal name="Reset" /><signal name="ServiceUnavailable"><arg type="s" name="service_name" /><arg type="s" name="message" /></signal><signal name="VerificationFailed"><arg type="s" name="service_name" /></signal><signal name="VerificationComplete"><arg type="s" name="service_name" /></signal></interface><interface name="org.gnome.DisplayManager.UserVerifier.ChoiceList"><method name="SelectChoice"><arg type="s" name="service_name" direction="in" /><arg type="s" name="choice" direction="in" /></method><signal name="ChoiceQuery"><arg type="s" name="service_name" /><arg type="s" name="prompt_message" /><arg type="a{ss}" name="list" /></signal></interface><interface name="org.gnome.DisplayManager.UserVerifier.CustomJSON"><method name="Reply"><arg type="s" name="service_name" direction="in" /><arg type="s" name="reply" direction="in" /></method><method name="ReportError"><arg type="s" name="service_name" direction="in" /><arg type="s" name="error" direction="in" /></method><signal name="Request"><arg type="s" name="service_name" /><arg type="s" name="protocol" /><arg type="u" name="version" /><arg type="s" name="request" /></signal></interface><interface name="org.gnome.DisplayManager.Greeter"><method name="SelectSession"><arg type="s" name="session" direction="in" /></method><method name="SelectUser"><arg type="s" name="username" direction="in" /></method><method name="BeginAutoLogin"><arg type="s" name="username" direction="in" /></method><method name="GetTimedLoginDetails"><arg type="b" name="enabled" direction="out" /><arg type="s" name="username" direction="out" /><arg type="i" name="delay" direction="out" /></method><method name="StartSessionWhenReady"><arg type="s" name="service_name" direction="in" /><arg type="b" name="should_start_session" direction="in" /></method><method name="StopConflictingSession" /><signal name="SelectedUserChanged"><arg type="s" name="username" /></signal><signal name="DefaultLanguageNameChanged"><arg type="s" name="language_name" /></signal><signal name="DefaultSessionNameChanged"><arg type="s" name="session_name" /></signal><signal name="TimedLoginRequested"><arg type="s" name="username" /><arg type="i" name="delay" /></signal><signal name="SessionOpened"><arg type="s" name="service_name" /><arg type="s" name="session_id" /></signal><signal name="Reauthenticated"><arg type="s" name="service_name" /></signal></interface></node>'
session_node = Gio.DBusNodeInfo.new_for_xml(SESSION_XML)

def _session_call(conn, sender, path, iface, method, params, inv):
    if method == 'GetTimedLoginDetails':
        inv.return_value(GLib.Variant('(bsi)', (False, '', 0)))
    else:
        inv.return_value(None)   # every other method has no out arguments

_peers = []
def _new_peer(server, conn):
    _peers.append(conn)
    for i in session_node.interfaces:
        conn.register_object('/org/gnome/DisplayManager/Session', i, _session_call, None, None)
    return True

greeter_server = Gio.DBusServer.new_sync(GREETER_ADDR, Gio.DBusServerFlags.AUTHENTICATION_ALLOW_ANONYMOUS,
                                         Gio.dbus_generate_guid(), None, None)
greeter_server.connect('new-connection', _new_peer)
greeter_server.start()
os.chmod('/run/fake-gdm-greeter', 0o777)

def gdm_call(conn, sender, path, iface, method, params, inv):
    if method in ('RegisterSession', 'RegisterDisplay'):
        inv.return_value(None)
    elif method in ('OpenSession', 'OpenReauthenticationChannel'):
        inv.return_value(GLib.Variant('(s)', (GREETER_ADDR,)))
    else:
        inv.return_dbus_error('org.gnome.DisplayManager.Manager.Error', 'not available in the test lab')
def gdm_prop(conn, sender, path, iface, name):
    return GLib.Variant('s', '51.1') if name == 'Version' else None
def gdm_acquired(conn, name):
    conn.register_object('/org/gnome/DisplayManager/Manager', gdm_node.interfaces[0], gdm_call, gdm_prop, None)
Gio.bus_own_name(Gio.BusType.SYSTEM, 'org.gnome.DisplayManager', 0, gdm_acquired, None, None)
GLib.MainLoop().run()
