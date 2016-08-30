# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

# -----------------------------------------------------------------------------
# Save and restore map series state.
#
def map_series_states(session):
    from .series import Map_Series
    s = [state_from_series(s, session) for s in session.model_list() if isinstance(s, Map_Series)]
    return s

# -----------------------------------------------------------------------------
#
def restore_map_series(ms_states, session, file_paths, attributes_only = False):
    for ms_state in ms_states:
        from ..session import find_volumes_by_session_id
        maps = find_volumes_by_session_id(ms_state['maps'], session)
        from .series import Map_Series
        ms = Map_Series(ms_state['name'], maps, session)
        ms.id = ms_state['id']
        oids = session.object_ids
        if 'session_id' in ms_state:
            oids.set_object_id(ms, ms_state['session_id'])
        session.add_model(ms)

# ---------------------------------------------------------------------------
#
def state_from_series(series, session):
    oids = session.object_ids
    s = {
        'name': series.name,
        'id': series.id,
        'maps': [m.session_volume_id for m in series.maps],
        'session_id': oids.object_id(series),        # Used to reference series in gui session state
    }
    return s
    
# -----------------------------------------------------------------------------
# Save and restore map series gui state.
#
def map_series_slider_states(session):
    from .slider import sliders
    st = [slider_state(s,session) for s in sliders(session)]
    return st

# -----------------------------------------------------------------------------
#
def restore_map_series_sliders(sl_states, session, file_paths, attributes_only = False):
    oids = session.object_ids
    for sl_state in sl_states:
        series = [oids.object_from_id(s) for s in sl_state['series']]
        from . import slider
        vss = slider.Volume_Series_Slider(series, session)
        vss.show()

# ---------------------------------------------------------------------------
#
def slider_state(slider, session):
    oids = session.object_ids
    s = { 'series': tuple(oids.object_id(s) for s in slider.series), }
    return s
