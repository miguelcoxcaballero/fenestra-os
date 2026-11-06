/**
 * @file Shell.GLSLEffect was removed in GNOME 51. This base class keeps the
 * GLSLEffect API used by the effects (vfunc_build_pipeline, add_glsl_snippet,
 * get_uniform_location, set_uniform_float) on top of Clutter.ShaderEffect,
 * like GNOME 51's own shader effects. On older GNOME, Shell.GLSLEffect is used.
 */
import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';

// Subclasses implement _buildPipeline() (a vfunc_ name would not register on
// Clutter.ShaderEffect, which has no build_pipeline virtual function).
export const GLSLEffectBase = Shell.GLSLEffect
    ? GObject.registerClass({}, class GLSLEffectLegacy extends Shell.GLSLEffect {
        vfunc_build_pipeline() {
            this._buildPipeline();
        }
    })
    : GObject.registerClass({}, class GLSLEffectCompat extends Clutter.ShaderEffect {
        vfunc_get_static_snippet() {
            this._fenestraSnippet = null;
            this._buildPipeline();
            return this._fenestraSnippet;
        }

        add_glsl_snippet(hook, declarations, code, isReplace) {
            const snippet = Cogl.Snippet.new(hook, declarations, isReplace ? null : code);
            if (isReplace)
                snippet.set_replace(code);
            this._fenestraSnippet = snippet;
        }

        get_uniform_location(name) {
            return name;
        }
    });
