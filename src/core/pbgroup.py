from .molecule import CPseudobondGroup
from .models import Model
class PseudobondGroup(CPseudobondGroup, Model):
    """Pseudobond group model"""

    def __init__(self, pbg_pointer):

        CPseudobondGroup.__init__(self, pbg_pointer)
        Model.__init__(self, self.category)
        self._pbond_drawing = None

        self._update_graphics()

    def delete(self):
        Model.delete(self)
        self._pbond_drawing = None
        CPseudobondGroup.delete(self)

    def added_to_session(self, session):
        v = session.main_view
        v.add_callback('graphics update', self._update_graphics_if_needed)

        # Detect when atoms moved so pseudobonds must be redrawn.
        # TODO: Update only when atoms move or are shown hidden, not when anything shown or hidden.
        v.add_callback('shape changed', self.update_graphics)

    def removed_from_session(self, session):
        v = session.main_view
        v.remove_callback('graphics update', self._update_graphics_if_needed)
        v.remove_callback('shape changed', self.update_graphics)

    def _update_graphics_if_needed(self):
        c, s, se = self.gc_color, self.gc_shape, self.gc_select
        if c or s or se:
            self.gc_color = self.gc_shape = self.gc_select = False
            self._update_graphics()
            self.redraw_needed(shape_changed = s, selection_changed = se)

    def _update_graphics(self):

        pbonds = self.pseudobonds
        d = self._pbond_drawing
        if len(pbonds) == 0:
            if d:
                d.delete()
                self._pbond_drawing = None
            return

        from . import structure
        if d is None:
            self._pbond_drawing = d = self.new_drawing('pbonds')
            va, na, ta = structure._pseudobond_geometry()
            d.vertices = va
            d.normals = na
            d.triangles = ta

        bond_atoms = pbonds.atoms
        radii = pbonds.radii
        bond_colors = pbonds.colors
        half_bond_coloring = pbonds.halfbonds
        to_pbg = self.scene_position.inverse()
        axyz0, axyz1 = to_pbg*bond_atoms[0].scene_coords, to_pbg*bond_atoms[1].scene_coords
        d.positions = structure._bond_cylinder_placements(axyz0, axyz1, radii, half_bond_coloring)
        d.display_positions = self._shown_bond_cylinders(bond_atoms, half_bond_coloring)
        d.colors = self._bond_colors(bond_atoms, bond_colors, half_bond_coloring)

    def _bond_colors(self, bond_atoms, bond_colors, half_bond_coloring):
        if half_bond_coloring.any():
            bc0,bc1 = bond_atoms[0].colors, bond_atoms[1].colors
            from numpy import concatenate
            c = concatenate((bc0,bc1))
        else:
            c = bond_colors
        return c

    def _shown_bond_cylinders(self, bond_atoms, half_bond_coloring):
        sb = bond_atoms[0].displays & bond_atoms[1].displays  # Show bond if both atoms shown
        if half_bond_coloring.any():
            from numpy import concatenate
            sb2 = concatenate((sb,sb))
            return sb2
        return sb

    def take_snapshot(self, phase, session, flags):
        if phase != self.SAVE_PHASE:
            return
        data = {}
        return [self.STRUCTURE_STATE_VERSION, data]

    def restore_snapshot(self, phase, session, version, data):
        if version != self.STRUCTURE_STATE_VERSION or len(data) > 0:
            raise RestoreError("Unexpected version or data")

    def reset_state(self):
        pass

def all_pseudobond_groups(models):
    return [m for m in models.list() if isinstance(m, PseudobondGroup)]
