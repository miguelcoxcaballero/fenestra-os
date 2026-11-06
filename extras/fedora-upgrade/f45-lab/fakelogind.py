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
GLib.MainLoop().run()
