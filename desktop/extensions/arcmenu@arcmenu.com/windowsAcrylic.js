import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GObject from 'gi://GObject';
import Mtk from 'gi://Mtk';

/*
 * Windows 11 acrylic "luminosity" layer.
 *
 * Runs after Shell.BlurEffect (BACKGROUND) on the same actor: copies the
 * already-blurred backdrop under the actor and re-maps it so the brightness is
 * pinned to a narrow dark range while the hue/saturation of the backdrop is
 * kept. Over the green wallpaper it stays green, over black windows it stays a
 * readable grey and never goes see-through, like Windows' acrylic.
 *
 * Output is opaque with rounded corners; the actor's own content (and CSS
 * bands) are painted on top as usual.
 */
const DECL = `
uniform vec2 u_size;
uniform float u_radius;
uniform vec3 u_map; // base luminance, luminance gain, chroma gain
`;
const POST = `
vec3 c = cogl_color_out.rgb;
float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
float lt = u_map.x + u_map.y * l;
vec3 o = clamp(vec3(lt) + (c - vec3(l)) * u_map.z, 0.0, 1.0);
vec2 p = cogl_tex_coord_in[0].st * u_size;
vec2 q = abs(p - u_size * 0.5) - (u_size * 0.5 - vec2(u_radius));
float d = length(max(q, 0.0)) - u_radius;
float a = clamp(0.5 - d, 0.0, 1.0);
cogl_color_out = vec4(o * a, a);
`;

export const WindowsAcrylicEffect = GObject.registerClass(
class WindowsAcrylicEffect extends Clutter.Effect {
    _init(params = {}) {
        const {radius = 8, base = 0.128, gain = 0.265, chroma = 0.65} = params;
        super._init();
        this._radius = radius;
        this._map = [base, gain, chroma];
        this._w = 0;
        this._h = 0;
    }

    setMap(base, gain, chroma) {
        this._map = [base, gain, chroma];
        this.queue_repaint();
    }

    _ensure(ctx, w, h) {
        if (this._tex && this._w === w && this._h === h)
            return;
        this._w = w;
        this._h = h;
        this._tex = Cogl.Texture2D.new_with_size(ctx, w, h);
        this._fb = Cogl.Offscreen.new_with_texture(this._tex);
        this._fb.allocate();
        this._copyPipeline = Cogl.Pipeline.new(ctx);
        this._copyPipeline.set_layer_texture(0, this._tex);
        this._pipeline = Cogl.Pipeline.new(ctx);
        this._pipeline.set_layer_texture(0, this._tex);
        this._pipeline.set_layer_filters(0, Cogl.PipelineFilter.LINEAR, Cogl.PipelineFilter.LINEAR);
        this._pipeline.add_snippet(Cogl.Snippet.new(Cogl.SnippetHook.FRAGMENT, DECL, POST));
    }

    vfunc_paint_node(node, paintContext, flags) {
        const actor = this.get_actor();
        try {
            const src = paintContext.get_framebuffer();
            const ext = actor?.get_transformed_extents();
            const cx = ext ? ext.origin.x + ext.size.width / 2 : 0;
            const cy = ext ? ext.origin.y + ext.size.height / 2 : 0;
            const view = ext ? global.stage.peek_stage_views().find(v => {
                const r = new Mtk.Rectangle();
                v.get_layout(r);
                return cx >= r.x && cx < r.x + r.width && cy >= r.y && cy < r.y + r.height;
            }) : null;
            if (view && src && actor) {
                const layout = new Mtk.Rectangle();
                view.get_layout(layout);
                const scale = view.get_scale();
                const x = Math.max(0, Math.round((ext.origin.x - layout.x) * scale));
                const y = Math.max(0, Math.round((ext.origin.y - layout.y) * scale));
                const w = Math.round(ext.size.width * scale);
                const h = Math.round(ext.size.height * scale);
                if (w > 0 && h > 0) {
                    const ctx = Clutter.get_default_backend().get_cogl_context();
                    this._ensure(ctx, w, h);
                    const layer = Clutter.LayerNode.new_to_framebuffer(this._fb, this._copyPipeline);
                    node.add_child(layer);
                    const lbox = new Clutter.ActorBox();
                    lbox.set_origin(0, 0);
                    lbox.set_size(actor.width, actor.height);
                    layer.add_rectangle(lbox);
                    const blit = Clutter.BlitNode.new(src);
                    layer.add_child(blit);
                    blit.add_blit_rectangle(x, y, 0, 0, w, h);

                    const p = this._pipeline;
                    const sx = actor.width ? w / actor.width : scale;
                    p.set_uniform_float(p.get_uniform_location('u_size'), 2, 1, [actor.width, actor.height]);
                    p.set_uniform_1f(p.get_uniform_location('u_radius'), this._radius);
                    p.set_uniform_float(p.get_uniform_location('u_map'), 3, 1, this._map);
                    void sx;
                    const pnode = Clutter.PipelineNode.new(p);
                    node.add_child(pnode);
                    const box = new Clutter.ActorBox();
                    box.set_origin(0, 0);
                    box.set_size(actor.width, actor.height);
                    pnode.add_rectangle(box);
                }
            }
        } catch (e) {
            if (!this._warned) {
                this._warned = true;
                console.error(`Windows acrylic: ${e.message}`);
            }
        }
        node.add_child(Clutter.ActorNode.new(actor, -1));
    }
});
