// Syntax check for GNOME Shell extension modules, outside GNOME Shell.
//   gjs -m tools/check-js-syntax.js FILE.js...
// Each file is imported as an ES module. GJS parses a module before it resolves its imports,
// so a SyntaxError is a real error in that file, while a failed import (e.g. the
// resource:///org/gnome/shell/... modules, which only exist inside the shell) is expected
// and ignored. Prints one line per broken file; exit status 1 if any.
import Gio from 'gi://Gio';
import System from 'system';

let bad = 0;
for (const path of ARGV) {
    const uri = Gio.File.new_for_path(path).get_uri();
    try {
        await import(uri);
    } catch (e) {
        if (e instanceof SyntaxError) {
            print(`${path}: ${e.name}: ${e.message}${e.lineNumber ? ` (line ${e.lineNumber})` : ''}`);
            bad++;
        }
    }
}
print(`${ARGV.length} module(s) checked, ${bad} with syntax errors`);
System.exit(bad ? 1 : 0);
