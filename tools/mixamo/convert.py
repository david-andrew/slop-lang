# Mixamo FBX (a skinned character and animations without skin) -> one .glb, with Blender as a
# Python module (uv run --python 3.11 --with bpy python convert.py -- ...):
#   convert.py -- out.glb character.fbx Name=anim.fbx[:inplace] ...
# ":inplace" takes the walk out of a moving animation (its hips stay over the spot), and prints
# how fast it went. Breakwater's vanguard.glb: Vanguard with these, from the Pro Rifle Pack (R)
# and Basic Shooter Pack (B):
#   Idle=R/idle aiming  Walk, WalkBack, WalkLeft, WalkRight=R/walk forward, backward, left, right
#   Run, RunBack, RunLeft, RunRight=R/run forward, backward, left, right (all :inplace)
#   DieBack=R/death from the front  DieForward=R/death from the back  DieHead=R/death from front
#   headshot  Hit=B/hit reaction  Fire=B/firing rifle  Toss=B/toss grenade  Reload=B/reloading
import bpy, sys, os
args = sys.argv[sys.argv.index('--') + 1:]
out, char, anims = args[0], args[1], args[2:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=char)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
arm.name = 'Vanguard'

def fcurves(a):
    fcs = []
    for L in a.layers:
        for st in L.strips:
            for cb in st.channelbags: fcs += [(cb, fc) for fc in cb.fcurves]
    return fcs

# leaf bones (finger tips, head top, toe ends) bend nothing: removed, to keep under 64 joints
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
for b in list(arm.data.edit_bones):
    if b.name.endswith('_End') or b.name[-1] == '4' and 'Hand' in b.name:
        arm.data.edit_bones.remove(b)
bpy.ops.object.mode_set(mode='OBJECT')
names = {b.name for b in arm.data.bones}
print('bones', len(names))
for a in list(bpy.data.actions): bpy.data.actions.remove(a)

arm.animation_data_create()
speeds = {}
for spec in anims:
    name, path = spec.split('=', 1)
    inplace = path.endswith(':inplace')
    if inplace: path = path[:-8]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    src = [o for o in new if o.type == 'ARMATURE'][0]
    act = src.animation_data.action
    act.name = name
    f0, f1 = act.frame_range
    for cb, fc in fcurves(act):
        bone = fc.data_path.split('"')[1] if '"' in fc.data_path else ''
        # only rotations, and the hips' place; nothing for bones removed
        keep = bone in names and (fc.data_path.endswith('rotation_quaternion') or (bone.endswith('Hips') and fc.data_path.endswith('location')))
        if not keep:
            cb.fcurves.remove(fc)
            continue
        if inplace and bone.endswith('Hips') and fc.data_path.endswith('location') and fc.array_index in (0, 2):
            ks = fc.keyframe_points
            a0, a1 = ks[0].co[1], ks[-1].co[1]
            speeds.setdefault(name, []).append((a1 - a0) * 0.01 / ((f1 - f0) / 30.0))
            for k in ks:
                t = (k.co[0] - f0) / max(f1 - f0, 1)
                d = a0 + (a1 - a0) * t
                k.co[1] -= d - a0
                k.handle_left[1] -= d - a0
                k.handle_right[1] -= d - a0
    act.use_fake_user = True
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, int(f0), act)
    st.action_slot = act.slots[0]
    for o in new: bpy.data.objects.remove(o, do_unlink=True)
print('speeds (m/s along x, z)', speeds)

# only the base color texture is used: normal and specular maps are dropped
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            for inp in ('Normal', 'Specular IOR Level', 'Specular Tint', 'Roughness', 'Metallic'):
                if inp in n.inputs:
                    for l in list(n.inputs[inp].links): m.node_tree.links.remove(l)
for img in bpy.data.images:
    if img.size[0] > 1024: img.scale(1024, 1024)

bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animation_mode='NLA_TRACKS',
    export_image_format='JPEG', export_jpeg_quality=85, export_optimize_animation_size=True,
    export_def_bones=True, export_leaf_bone=False, export_morph=False, export_tangents=False,
    export_extras=False, export_cameras=False, export_lights=False, export_apply=False)
print('wrote', out, os.path.getsize(out))
