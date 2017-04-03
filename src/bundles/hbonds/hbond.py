# vim: set expandtab ts=4 sw=4:

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

verbose = False

from .acceptor_geom import acc_syn_anti, acc_phi_psi, acc_theta_tau, acc_generic
from .donor_geom import don_theta_tau, don_upsilon_tau, don_generic, don_water
from .common_geom import ConnectivityError, AtomTypeError
from chimerax.chem_group import find_group
from chimerax.core.geometry import AdaptiveTree
from .hydpos import hyd_positions
from chimerax.core.atomic.idatm import type_info, tetrahedral, planar, linear, single
from chimerax.core.atomic import Element
from chimerax.core.errors import UserError
import copy

from chimerax.chem_group import H, N, C, O, R
from chimerax.chem_group.chem_group import find_ring_planar_NHR2, find_nonring_ether, \
    find_nonring_NR2, find_6ring_planar_NR2, find_5ring_planar_NR2, find_5ring_OR2
_ring5_NH = lambda structs, ret_coll: find_ring_planar_NHR2(structs, ret_coll, 5)
_ring6_aro_NH = lambda structs, ret_coll: find_ring_planar_NHR2(structs, ret_coll, 6,
    aromatic_only=True)
_ring6_sym_N = lambda structs, ret_coll: find_6ring_planar_NR2(structs, ret_coll, symmetric=True)
_ring5_sym_N = lambda structs, ret_coll: find_5ring_planar_NR2(structs, ret_coll, symmetric=True)
_ring6_asym_N = lambda structs, ret_coll: find_6ring_planar_NR2(structs, ret_coll, symmetric=False)
_ring5_asym_N = lambda structs, ret_coll: find_5ring_planar_NR2(structs, ret_coll, symmetric=False)
_ring5_O = lambda structs, ret_coll: find_5ring_OR2(structs, ret_coll)

tet = {'geometry':tetrahedral}
explicit_single_bond = ({'geometry':tetrahedral}, {'geometry':single})
non_O3_minus_sb = ({'geometry':tetrahedral, 'not type': ['O3-']},
                            {'geometry':single})
non_Sac_Pac_H_sb = ({'geometry':tetrahedral, 'not type': ['Sac', 'Pac']},
                {'geometry':single, 'not type': ['H', 'HC', 'D']})

"""
# recommended distance and angle constraint relaxations for biomolecules
recDistSlop = 0.4
recAngleSlop = 20.0
"""

# layout of acceptor_params is:
#     name or spec of acceptor group,
#     tuple indicating index of acceptor or acceptors in group,
#     function to determine if acceptor satisfied,
#     tuple of arguments to give to that function
#
#     in argument tuple, conversions will occur before function gets called.
#     namely:
#         floats are assumed to be distances, and will be squared
#         integers are assumed to be angles in degrees, and will be
#             converted to radians
#         integer/None tuples are assumed to refer to other atoms in
#             the group, and will be replaced by them.  None remains
#             None.  '-1' means the other acceptor of the group.

acceptor_params = [
    # phosphodiester-like (negative oxygens) [3+ O-]
    [[['Pac', ['O3-', 'O3-', 'O3-', explicit_single_bond]], [1,1,1,1,0]],
        (1,), acc_syn_anti, ((2, 0), 3.03, 110, 145, 3.03, 110, 135)],
    # phosphodiester-like (negative oxygens) [2 O-]
    [[['Pac', ['O3-', 'O3-', non_O3_minus_sb, non_O3_minus_sb]], [1,1,1,0,0]],
        (1, 2), acc_syn_anti, ((-1, 0), 3.03, 110, 145, 3.03, 110, 135)],
    # carboxylate
    [[['Cac', ['O2-', 'O2-', explicit_single_bond]], [1,1,1,0]], (1, 2), acc_syn_anti,
        ((-1, 0), 3.17, 90, 145, 3.17, 110, 145)],
    ["thiocarbonyl", (0,), acc_phi_psi, ((1, None), 3.73, 90, 145)],
    # carboxylic acid
    [[[C, [['O2', []], ['O3', [H]], explicit_single_bond]],[1,1,1,0,0]], (1,),
        acc_syn_anti, ((2, 0), 3.17, 110, 130, 3.17, 110, 135)],
    # amide
    [[['C2', ['O2', 'Npl',  explicit_single_bond]], [1,1,1,0]], (1,), acc_syn_anti,
        ((2, 0), 3.30, 110, 135, 3.30, 110, 130)],
    # ketone/aldehyde carbonyl
    [[['C2', ['O2', C, R]], [1,1,0,0]],
        (1,), acc_phi_psi, ((0, None), 3.30, 110, 130)],
    # ester carbonyl
    [[['C2', ['O2', ['O3', [tet]], C]], [1,1,0,0,0]],
        (1,), acc_phi_psi, ((0, None), 3.17, 110, 135)],
    # nitro group
    [[['Ntr', ['O2-', 'O2-', explicit_single_bond]], [1,1,1,0]], (1, 2), acc_syn_anti,
        ((-1, 0), 3.42, 90, 145, 3.53, 110, 130)],
    # sulfone
    [[['Son', ['O2', 'O2', explicit_single_bond, explicit_single_bond]], [1,1,1,0,0]], (1, 2), acc_syn_anti,
        ((-1, 0), 3.30, 110, 130, 3.30, 120, 135)],
    # phosphones
    [[['Pac', ['O3', 'O3-', 'O3-', explicit_single_bond]], [1,1,0,0,0]],
        (1,), acc_theta_tau, ((0,), 3.03, 103, -146, 145)],
    [[['O2', ['Pox']], [1,1]],
        (0,), acc_theta_tau, ((1,), 3.03, 109, -180, 145)],
    # sulfoxide
    [[['O2', ['Sxd']], [1,1]],
        (0,), acc_theta_tau, ((1,), 3.03, 100, -180, 145)],
    # non-protonated aliphatic primary amine
    [[['N3', [tet, H, H]], [1,1,0,0]],
        (0,), acc_theta_tau, ((1,), 3.03, 103, -180, 155)],
    # non-phenol hydroxyl
    [[['O3', [non_Sac_Pac_H_sb, H]], [1,1,1]],
        (0,), acc_theta_tau, ((1,), 3.03, 100, -161, 145)],
    [[['Sac', ['O3-', 'O3-', ['O3', [{'default': True, 'not type': ['Pac']}]], explicit_single_bond]], [1,1,1,1,0,0]],
        (3,), acc_theta_tau, ((0,), 3.17, 103, -180, 150)],
    # non-protonated aliphatic tertiary amine
    [[['N3', [tet, tet, tet]], [1,1,1,1]],
        (0,), acc_theta_tau, (None, 3.17, 153, -180, 145)],
    # nitrile
    [[['N1', ['C1']], [1,1]],
        (0,), acc_theta_tau, ((1,), 3.30, 153, -180, 150)],
    # non-protonated aliphatic secondary amine
    [[['N3', [tet, tet, H]], [1,1,1,0]],
        (0,), acc_theta_tau, (None, 3.30, 153, -180, 150)],
    # phenol
    [[['O3', ['Car', H]], [1,1,0]],
        (0,), acc_theta_tau, ((1,), 3.17, 100, -153, 150)],
    # anilene
    [[[('Npl', 'N3'), ['Car', H, H]], [1,1,1,1]],
        (0,), acc_theta_tau, ((1,), 3.42, 90, -137, 140)],
    # waddah
    [[[O, [H, H]], [1,0,0]], (0,), acc_phi_psi,
                ((None, None), 3.03, 120, 145)],
    # non-ring ether
    [[lambda structs, ret_coll: find_nonring_ether(structs, ret_coll), None],
        (0,), acc_phi_psi, ((1, 2), 3.42, 140, 140)],
    # secondary amine not in a ring system
    [[lambda structs, ret_coll: find_nonring_NR2(structs, ret_coll), None],
        (0,), acc_phi_psi, ((1, 2), 3.42, 140, 140)],

    # check ring systems last, since conflicts of ring systems with
    # non-ring systems are not considered to be a problem (non-ring
    # "wins") and the code that checks the conflict assumes this order

    # nitrogen in symmetric 6-member ring
    [[_ring6_sym_N, None], (0,), acc_phi_psi, ((1, 2), 3.17, 150, 145)],
    # nitrogen in symmetric 5-member ring
    [[_ring5_sym_N, None], (0,), acc_phi_psi, ((1, 2), 3.30, 140, 155)],
    # nitrogen in asymmetric 6-member ring
    [[_ring6_asym_N, None], (0,), acc_phi_psi, ((1, 2), 3.30, 140, 140)],
    # nitrogen in asymmetric 5-member ring
    [[_ring5_asym_N, None], (0,), acc_phi_psi, ((1, 2), 3.30, 150, 135)],
    # oxygen in 5-member ring
    [[_ring5_O, None], (0,), acc_phi_psi, ((1, 2), 3.42, 150, 135)]
]
processed_acceptor_params = {}

# layout of donor_params somewhat similar to acceptor_params:
#    name or spec of donor group,
#    index of donor in group,
#    type of donor geometry
#    degree of tau symmetry
#    argument tuple used when geometry-check function is called
#
#    in argument tuple, conversions will occur before function gets called.
#    namely:
#        positive floats are assumed to be distances, and will be squared
#        integers are assumed to be angles in degrees, and will be
#            converted to radians

import sys
water = sys.intern("water")
theta_tau = sys.intern('theta_tau')
upsilon_tau = sys.intern('upsilon_tau')
OH_bond_dist = Element.bond_length("O", "H")

donor_params = [
    # neutral carboxylic acid
    [[['O3', ['Cac', H]], [1,1,0]],
        0, upsilon_tau, 2,
        (2.87, 103, -128, 140, -30,
         2.87, 103, -128, 155, -30, 150,
         2.87, 103, -128, 140, -30, 150)],
    # protonated nitrogen double-bonded to carbon
    [[['Npl', [['C2', [explicit_single_bond, explicit_single_bond]], H, H]], [1,1,0,0,0,0]],
        0, upsilon_tau, 4,
        (3.17,  90, -146, 140, -30,
         3.17,  90, -146, 140, -22.5, 150,
         # next line extrapolated
         3.17, 113, -161, 125, None, 140)],
    [[['Ng+', ['C2', H, H]], [1,1,0,0]],
        0, upsilon_tau, 4,
        (3.17,  90, -146, 140, -30,
         3.17,  90, -146, 140, -22.5, 150,
         # next line extrapolated
         3.17, 113, -161, 125, None, 140)],
    # protonated primary amine
    [[['N3+', [tet, H, H, H]], [1,1,0,0,0]],
        0, upsilon_tau, 6,
        (3.17,  90, -136, 140, 20,
         3.17,  90, -132, 150, 25, 130,
         3.17,  90, -124, 155, 15, 150)],
    # hydroxyl
    [[['O3', [tet, H]], [1,1,0]],
        0, upsilon_tau, 6,
        (3.17,  90, -141, 130, None,
         3.03,  90, -141, 135, None, 140,
         3.03, 100, -132, 145, None, 150)],
    # amide (two hydrogens)
    #   though the paper gives the tau symmetry as '2', we use '4' since
    #   we aren't distinguishing between the carbonyl oxygen and the
    #   other bonded substituent
    [[['C2', ['O2', [N, [H, H]], explicit_single_bond]], [1,1,1,0,0,0]],
        2, upsilon_tau, 4,
        (3.30, 103, -153, 135, -45,
         3.30, 109, -141, 140, -30, 140,
         3.30, 113, -161, 125, -30, 145)],
    # aniline-like
    ["aromatic primary amine",
        0, upsilon_tau, 4,
        (3.30, 100, -146, 145, -37.5,
         3.30, 103, -146, 140, -37.5, 130,
         # estimated
         3.42,  90,  161, 125, None, 140)],
    # phenol-like
    [[['O3', ['Car', H]], [1,0,0]],
        0, upsilon_tau, 4,
        (3.03, 103, -136, 145, -37.5,
         3.03, 103, -136, 150, -45.0, 140,
         2.87, 109, -128, 145, -52.5, 150)],
    # neutral primary aliphatic amine
    [[['N3', [tet, H, H]], [1,0,1,1]],
        0, upsilon_tau, 6,
        (3.30, 90, -128, 150, 30,
         3.42, 90, -124, 155, 25, 130,
         3.42, 90, -132, 155, 20, 140)],
    # planar charged nitrogen with one hydrogen
    [[['Npl', [tet, [{'geometry':planar}, [(tet,H), (tet,H)]], H]], [1,0,0,0,0,0]],
        0, theta_tau, 4,
        (1.92, 146, 1.92, 153, 150, 2.48, 141, 145)],
    # sp3 charged nitrogen with 2 hydrogens
    [[['N3+', [tet, tet, H, H]], [1,0,0,1,1]],
        0, theta_tau, 2,
        (2.09, 141, 2.09, 141, 155, 2.48, 141, 145)],
    # waddah
    [[[O, [H, H]], [1,0,0]],
        0, water, 2,
        (2.36, 2.36 + OH_bond_dist, 146,
        2.23, 2.23 + OH_bond_dist, 146, 140,
        2.23, 2.23 + OH_bond_dist, 146, 150)],
    # amide (one hydrogen)
    [[['C2', ['O2', [N, [tet, H]], explicit_single_bond]], [1,1,1,0,0,0]],
        2, theta_tau, 2,
        (2.23, 146, 2.23, 146, 140, 2.36, 141, 145)],
    # aliphatic tertiary amine
    [[['N3+', [tet, tet, tet, H]], [1,0,0,0,1]],
        0, theta_tau, 6,
        (1.92, 146, 2.09, 146, 140, 2.48, 141, 145)],
    # double-bonded nitrogen
    [[['N2', [{'geometry':planar}, H]], [1,1,0]],
        0, theta_tau, 2,
        (2.23, 132, 2.36, 146, 140, 2.48, 141, 145)],
    # secondary amine
    [[['N3', [tet, tet, H]], [1,0,0,1]],
        0, theta_tau, 2,
        (2.36, 141, 2.48, 146, 150, 2.48, 153, 155)],

    # check ring systems last, since conflicts of ring systems with
    # non-ring systems are not considered to be a problem (non-ring
    # "wins") and the code that checks the conflict assumes this order

    # nitrogen in 5-member ring
    [[_ring5_NH, None],
        0, theta_tau, 4,
        (2.09, 146, 2.09, 141, 140, 2.48, 141, 145)],
    # nitrogen in aromatic 6-member ring
    [[_ring6_aro_NH, None],
        0, theta_tau, 2,
        (2.23, 136, 2.23, 141, 150, 2.48, 141, 145)],
    # need below to cause check for generic donors
    [None, 0, 'generic', 0, (3.73, 3.73, 3.73)]
]
processed_donor_params = {}

def flush_cache():
    global _d_cache, _a_cache, _prev_limited
    _prev_limited = _d_cache = _a_cache = None
flush_cache()

_problem = None
_ring_funcs = [_ring5_asym_N, _ring6_asym_N, _ring5_O,
                _ring5_sym_N, _ring6_sym_N, _ring5_NH, _ring6_aro_NH]

@line_profile
def find_hbonds(session, models, intermodel=True, intramodel=True, donors=None, acceptors=None,
        dist_slop=0.0, angle_slop=0.0, inter_submodel=False, cache_da=False):
    """Hydrogen bond detection based on criteria in "Three-dimensional
        hydrogen-bond geometry and probability information from a
        crystal survey", J. Computer-Aided Molecular Design, 10 (1996),
        607-622

        If donors and/or acceptors are specified (as :py:class:`~chimerax.core.atomic.Atoms` collections
        or anything an Atoms collection can be constructued from), then H-bond donors/acceptors
        are restricted to being from those atoms.

        Dist/angle slop are the amount that distances/angles are allowed to exceed
        the values given in the above reference and still be considered hydrogen bonds.

        'cache_da' allows donors/acceptors in molecules to be cached if it is anticipated that
        the same structures will be examined for H-bonds repeatedly (e.g. a dynamics trajectory).
    """

    from chimerax.core.atomic import Atoms
    if donors and not isinstance(donors, Atoms):
        limited_donors = Atoms(donors)
    else:
        limited_donors = donors
    if acceptors and not isinstance(acceptors, Atoms):
        limited_acceptors = Atoms(acceptors)
    else:
        limited_acceptors = acceptors
    global _d_cache, _a_cache, _prev_limited
    if cache_da:
        if limited_donors:
            dIDs = [id(d) for d in limited_donors]
            dIDs.sort()
        else:
            dIDs = None
        if limited_acceptors:
            aIDs = [id(a) for a in limited_acceptors]
            aIDs.sort()
        else:
            aIDs = None
        key = (dIDs, aIDs)
        if _prev_limited and _prev_limited != key:
            flush_cache()
        _prev_limited = key
        from weakref import WeakKeyDictionary
        if _d_cache is None:
            _d_cache = WeakKeyDictionary()
            _a_cache = WeakKeyDictionary()
    else:
        flush_cache()
    global donor_params, acceptor_params
    global processed_donor_params, processed_acceptor_params
    global _compute_cache
    global verbose
    global _problem
    _problem = None

    bad_connectivities = 0

    # Used (as necessary) to cache expensive calculations (by other functions also)
    _compute_cache = {}

    process_key = (dist_slop, angle_slop)
    if process_key not in processed_acceptor_params:
        # copy.deepcopy() refuses to copy functions (even as
        # references), so do this instead...
        a_params = []
        for p in acceptor_params:
            a_params.append(copy.copy(p))

        for i in range(len(a_params)):
            a_params[i][3] = _process_arg_tuple(a_params[i][3], dist_slop, angle_slop)
        processed_acceptor_params[process_key] = a_params
    else:
        a_params = processed_acceptor_params[process_key]

    # compute some info for generic acceptors/donors
    generic_acc_info = {}
    # oxygens...
    generic_O_acc_args = _process_arg_tuple([3.53, 90], dist_slop, angle_slop)
    generic_acc_info['misc_O'] = (acc_generic, generic_O_acc_args)
    # dictionary based on bonded atom's geometry...
    generic_acc_info['O2-'] = {
        single: (acc_generic, generic_O_acc_args),
        linear: (acc_generic, generic_O_acc_args),
        planar: (acc_phi_psi, _process_arg_tuple([3.53, 90, 130], dist_slop, angle_slop)),
        tetrahedral: (acc_generic, generic_O_acc_args)
    }
    generic_acc_info['O3-'] = generic_acc_info['O2-']
    generic_acc_info['O2'] = {
        single: (acc_generic, generic_O_acc_args),
        linear: (acc_generic, generic_O_acc_args),
        planar: (acc_phi_psi, _process_arg_tuple([3.30, 110, 130], dist_slop, angle_slop)),
        tetrahedral: (acc_theta_tau, _process_arg_tuple(
            [3.03, 100, -180, 145], dist_slop, angle_slop))
    }
    # list based on number of known bonded atoms...
    generic_acc_info['O3'] = [
        (acc_generic, generic_O_acc_args),
        (acc_theta_tau, _process_arg_tuple([3.17, 100, -161, 145], dist_slop, angle_slop)),
        (acc_phi_psi, _process_arg_tuple([3.42, 120, 135], dist_slop, angle_slop))
    ]
    # nitrogens...
    generic_N_acc_args = _process_arg_tuple([3.42, 90], dist_slop, angle_slop)
    generic_acc_info['misc_N'] = (acc_generic, generic_N_acc_args)
    generic_acc_info['N2'] = (acc_phi_psi, _process_arg_tuple([3.42, 140, 135],
            dist_slop, angle_slop))
    # tuple based on number of bonded heavy atoms...
    generic_N3_mult_heavy_acc_args = _process_arg_tuple([3.30, 153, -180, 145],
            dist_slop, angle_slop)
    generic_acc_info['N3'] = (
        (acc_generic, generic_N_acc_args),
        # only one example to draw from; weaken by .1A, 5 degrees
        (acc_theta_tau, _process_arg_tuple([3.13, 98, -180, 150], dist_slop, angle_slop)),
        (acc_theta_tau, generic_N3_mult_heavy_acc_args),
        (acc_theta_tau, generic_N3_mult_heavy_acc_args)
    )
    # one example only; weaken by .1A, 5 degrees
    generic_acc_info['N1'] = (acc_theta_tau, _process_arg_tuple(
                [3.40, 136, -180, 145], dist_slop, angle_slop))
    # sulfurs...
    # one example only; weaken by .1A, 5 degrees
    generic_acc_info['S2'] = (acc_phi_psi, _process_arg_tuple([3.83, 85, 140],
            dist_slop, angle_slop))
    generic_acc_info['Sar'] = generic_acc_info['S3-'] = (acc_generic,
            _process_arg_tuple([3.83, 85], dist_slop, angle_slop))
    # now the donors...

    # planar nitrogens
    gen_don_Npl_1h_params = (don_theta_tau, _process_arg_tuple([2.23, 136,
        2.23, 141, 140, 2.46, 136, 140], dist_slop, angle_slop))
    gen_don_Npl_2h_params = (don_upsilon_tau, _process_arg_tuple([3.30, 90, -153,
        135, -45, 3.30, 90, -146, 140, -37.5, 130, 3.40, 108, -166, 125, -35, 140],
        dist_slop, angle_slop))
    gen_don_O_dists = [2.41, 2.28, 2.28, 3.27, 3.14, 3.14]
    gen_don_O_params = (don_generic, _process_arg_tuple(gen_don_O_dists, dist_slop, angle_slop))
    gen_don_N_dists = [2.36, 2.48, 2.48, 3.30, 3.42, 3.42]
    gen_don_N_params = (don_generic, _process_arg_tuple(gen_don_N_dists, dist_slop, angle_slop))
    gen_don_S_dists = [2.42, 2.42, 2.42, 3.65, 3.65, 3.65]
    gen_don_S_params = (don_generic, _process_arg_tuple(gen_don_S_dists, dist_slop, angle_slop))
    generic_don_info = {
        'O': gen_don_O_params,
        'N': gen_don_N_params,
        'S': gen_don_S_params
    }

    acc_trees = {}
    hbonds = []
    has_sulfur = {}
    for model in models:
        session.logger.status("Finding acceptors in model '%s'" % model.name, blank_after=0)
        if cache_da and model in _a_cache and (dist_slop, angle_slop) in _acache[model]:
            acc_atoms = []
            acc_data = []
            for acc_atom, data in _a_cache[model][(dist_slop, angle_slop)].items():
                if not acc_atom.deleted:
                    acc_atoms.append(acc_atom)
                    acc_data.append(data)
        else:
            acc_atoms, acc_data = _find_acceptors(model, a_params,
                    limited_acceptors, generic_acc_info)
            if cache_da:
                cache = WeakKeyDictionary()
                for i in range(len(acc_atoms)):
                    cache[acc_atoms[i]] = acc_data[i]
                if model not in _a_cache:
                    _a_cache[model] = {}
                _a_cache[model][(dist_slop, angle_slop)] = cache
        xyz = []
        has_sulfur[model] = False
        for acc_atom in acc_atoms:
            c = acc_atom.scene_coord
            xyz.append([c[0], c[1], c[2]])
            if acc_atom.element == Element.get_element('S'):
                has_sulfur[model] = True
        session.logger.status("Building search tree of acceptor atoms", blank_after=0)
        acc_trees[model] = AdaptiveTree(xyz, acc_data, 3.0)
    
    if process_key not in processed_donor_params:
        # find max donor distances before they get squared..

        # copy.deepcopy() refuses to copy functions (even as
        # references), so do this instead...
        d_params = []
        for p in donor_params:
            d_params.append(copy.copy(p))

        for di in range(len(d_params)):
            geom_type = d_params[di][2]
            arg_list = d_params[di][4]
            don_rad = Element.bond_radius('N')
            if geom_type == theta_tau:
                max_dist = max((arg_list[0], arg_list[2], arg_list[5]))
            elif geom_type == upsilon_tau:
                max_dist = max((arg_list[0], arg_list[5], arg_list[11]))
            elif geom_type == water:
                max_dist = max((arg_list[1], arg_list[4], arg_list[8]))
            else:
                max_dist = max(gen_don_O_dists + gen_don_N_dists + gen_don_S_dists)
                don_rad = Element.bond_radius('S')
            d_params[di].append(max_dist + dist_slop + don_rad + Element.bond_radius('H'))

        for i in range(len(d_params)):
            d_params[i][4] = _process_arg_tuple(d_params[i][4], dist_slop, angle_slop)
        processed_donor_params[process_key] = d_params
    else:
        d_params = processed_donor_params[process_key]

    generic_water_params = _process_arg_tuple([2.36, 2.36 + OH_bond_dist, 146],
                            dist_slop, angle_slop)
    generic_theta_tau_params = _process_arg_tuple([2.48, 132], dist_slop, angle_slop)
    generic_upsilon_tau_params = _process_arg_tuple([3.42, 90, -161, 125], dist_slop, angle_slop)
    generic_generic_params = _process_arg_tuple([2.48, 3.42, 130, 90], dist_slop, angle_slop)
    for dmi in range(len(models)):
        model = models[dmi]
        session.logger.status("Finding donors in model '%s'" % model.name, blank_after=0)
        if cache_da and model in _d_cache and (dist_slop, angle_slop) in _d_cache[model]:
            don_atoms = []
            don_data = []
            for don_atom, data in _d_cache[model][(dist_slop, angle_slop)].items():
                if not don_atom.deleted:
                    don_atoms.append(don_atom)
                    don_data.append(data)
        else:
            don_atoms, don_data = _find_donors(model, d_params, limited_donors, generic_don_info)
            if cache_da:
                cache = WeakKeyDictionary()
                for i in range(len(don_atoms)):
                    cache[don_atoms[i]] = don_data[i]
                if model not in _d_cache:
                    _d_cache[model] = {}
                _d_cache[model][(dist_slop, angle_slop)] = cache

        session.logger.status("Matching donors in model '%s' to acceptors"
                        % model.name, blank_after=0)
        for i in range(len(don_atoms)):
            donor_atom = don_atoms[i]
            geom_type, tau_sym, arg_list, test_dist = don_data[i]
            donor_hyds = hyd_positions(donor_atom)
            coord = donor_atom.scene_coord
            for acc_model in models:
                if acc_model == model and not intramodel or acc_model != model and not intermodel:
                    continue
                if acc_model.id[0] == model.id[0] and not inter_submodel \
                and acc_model.id[1:] != model.id[1:]:
                    continue
                if has_sulfur[acc_model]:
                    from .common_geom import SULFUR_COMP
                    td = test_dist + SULFUR_COMP
                else:
                    td = test_dist
                accs = acc_trees[acc_model].search_tree([coord[0], coord[1], coord[2]], td)
                if verbose:
                    session.logger.info("Found %d possible acceptors for donor %s:"
                        % (len(accs), donor_atom))
                    for acc_data in accs:
                        session.logger.info("\t%s\n" % acc_data[0])
                for acc_atom, geom_func, args in accs:
                    if acc_atom == donor_atom:
                        # e.g. hydroxyl
                        if verbose:
                            print("skipping: donor == acceptor")
                        continue
                    try:
                        if not geom_func(donor_atom, donor_hyds, *args):
                            continue
                    except ConnectivityError as e:
                        session.logger.info("Skipping possible acceptor with bad geometry: %s\n%s\n"
                            % (acc_atom, e))
                        bad_connectivities += 1
                        continue
                    except:
                        print("donor:", donor_atom, " acceptor:", acc_atom)
                        raise
                    if verbose:
                        session.logger.info("\t%s satisfies acceptor criteria" % acc_atom)
                    if geom_type == upsilon_tau:
                        donor_func = don_upsilon_tau
                        add_args = generic_upsilon_tau_params + [tau_sym]
                    elif geom_type == theta_tau:
                        donor_func = don_theta_tau
                        add_args = generic_theta_tau_params
                    elif geom_type == water:
                        donor_func = don_water
                        add_args = generic_water_params
                    else:
                        if donor_atom.idatm_type in ["Npl", "N2+"]:
                            heavys = 0
                            for bonded in donor_atom.neighbors:
                                if bonded.element.number > 1:
                                    heavys += 1
                            if heavys > 1:
                                info = gen_don_Npl_1h_params
                            else:
                                info = gen_don_Npl_2h_params
                        else:
                            info = generic_don_info[donor_atom.element.name]
                        donor_func, arg_list = info
                        add_args = generic_generic_params
                        if donor_func == don_upsilon_tau:
                            # tack on generic
                            # tau symmetry
                            add_args = generic_upsilon_tau_params + [4]
                        elif donor_func == don_theta_tau:
                            add_args = generic_theta_tau_params
                    try:
                        if not donor_func(donor_atom, donor_hyds, acc_atom,
                                *tuple(arg_list + add_args)):
                            continue
                    except ConnectivityError as e:
                        session.logger.info("Skipping possible donor with bad geometry: %s\n%s\n"
                            % (donor_atom, e))
                        bad_connectivities += 1
                        continue
                    except AtomTypeError as e:
                        _problem = ("atom type", donor_atom, str(v), None)
                        continue
                    if verbose:
                        session.logger.info("\t%s satisfies donor criteria" % donor_atom)
                    hbonds.append((donor_atom, acc_atom))
        session.logger.status("")
    if bad_connectivities:
        session.logger.warning("Skipped %d atom(s) with bad connectivities; see log for details"
            % bad_connectivities);
    if _problem:
        if session.ui.is_gui and False:
            #TODO: report bug
            da, atom, grp1, grp2 = _problem
            from BugReport import bugNotify
            resAtoms = atom.residue.oslChildren()
            def resAtomRep(a):
                try:
                    i = resAtoms.index(a)
                except ValueError:
                    return "other %s" % a.element.name
                return "%2d" % (i+1)
            if da in ["donor", "acceptor"]:
                descript = "geometry class 1: %s\n\n" \
                        "geometry class 2: %s" % (
                        repr(grp1), repr(grp2))
            else:
                descript = "problem: %s" % grp1
            bugNotify(
"""At least one atom was classified into more than one acceptor or donor
geometry class or had a bad atom type.  This indicates a problem in the
classification/atom-typing mechanism and we would appreciate it if you
would use the bug-report button below to send us the information that
will allow us to improve the classification/atom-typing code.
""",
"""residue name: %s

problem %s atom: %d

residue atoms:
    %s

residue bonds:
    %s

%s
""" % (atom.residue.type, da, resAtoms.index(atom)+1,
"\n\t".join(["%2d %-4s %-s (%s)" % (en[0]+1, en[1].name, en[1].idatm_type, str(en[1].coord())) for en in enumerate(resAtoms)]),
"\n\t".join(["%s <-> %-s" % (resAtomRep(b.atoms[0]), resAtomRep(b.atoms[1])) for b in chimera.misc.bonds(resAtoms, internal=False)]),
descript)
)
        _problem = None
    return hbonds

def _process_arg_tuple(arg_tuple, dist_slop, angle_slop):
    new_args = []
    for arg in arg_tuple:
        if isinstance(arg, (int, float)):
            if arg > 0.0 and arg < 7.5:
                # square distances
                arg = arg + dist_slop
                new_args.append(arg * arg)
            else:
                if arg < 0.0:
                    arg = arg - angle_slop
                    if arg < -180.0:
                        arg = -180.0
                    # can't convert to positive value
                    # here because some constraints vary
                    # between "greater than" and "less than"
                else:
                    arg = arg - angle_slop
                    if arg < 0.0:
                        arg = 0.0
                new_args.append(arg)
        else:
            new_args.append(arg)
    return new_args  # returns list

def _find_acceptors(model, a_params, limited_acceptors, generic_acc_info):
    global _problem
    acc_atoms = []
    acc_data = []
    std_acceptors = {}
    for ap in a_params:
        group_key, acc_indices, geom_func, arg_list = ap
        groups = find_group(group_key, [model])
        for group in groups:
            for i in range(len(acc_indices)):
                acc_atom = group[acc_indices[i]]
                if limited_acceptors and acc_atom not in limited_acceptors:
                    continue
                if acc_atom in std_acceptors:
                    if group_key != std_acceptors[acc_atom] \
                    and not (
                    # conflicts of non-ring groups with
                    # ring groups not considered a problem
                    # (non-ring groups "win")
                    group_key[0] in _ring_funcs and std_acceptors[acc_atom][0] not in _ring_funcs):
                        _problem = ("acceptor", acc_atom, std_acceptors[acc_atom], group_key)
                    continue
                std_acceptors[acc_atom] = group_key

                args = [acc_atom]
                if isinstance(arg_list[0], tuple):
                    for index in arg_list[0]:
                        if index is None:
                            args.append(None)
                        elif index < 0:
                            args.append(group[acc_indices[1-i]])
                        else:
                            args.append(group[index])
                    args = args + arg_list[1:]
                else:
                    args = args + arg_list
                
                acc_atoms.append(acc_atom)
                acc_data.append([acc_atom, geom_func, tuple(args)])
    # find acceptors not covered by above
    for atom in model.atoms:
        if atom in std_acceptors:
            continue
        if limited_acceptors and atom not in limited_acceptors:
            continue
        if atom.idatm_type in generic_acc_info:
            acc_info = generic_acc_info[atom.idatm_type]
            if isinstance(acc_info, dict):
                try:
                    bonded_geom = type_info[atom.neighbors[0].idatm_type].geometry
                except KeyError:
                    bonded_geom = single
                acc_func, args = acc_info[bonded_geom]
            elif isinstance(acc_info, list):
                try:
                    acc_func, args = acc_info[atom.num_bonds]
                except IndexError:
                    _problem = ("connectivity", atom,
                        "bad number of bonds (%d)" % atom.num_bonds, None)
                    continue
            elif isinstance(acc_info, tuple) and isinstance(acc_info[0], tuple):
                acc_func, args = acc_info[numpy.count_nonzero(atom.neighbors.element_numbers > 1)]
            else:
                acc_func, args = acc_info
            if acc_func == acc_phi_psi:
                bonded = atom.neighbors
                args = list(bonded) + [None] * (2-len(bonded)) + args
            elif acc_func == acc_theta_tau:
                bonded = atom.neighbors
                if len(bonded) > 1:
                    args = [None] + args
                else:
                    args = [nb for nb in bonded] + args
        else:
            atomic_number = atom.element.number
            if atomic_number == 8:
                # oxygen
                acc_func, args = generic_acc_info['misc_O']
            elif atomic_number == 7:
                # nitrogen
                if atom.idatm_type not in ['N2', 'N3']:
                    continue
                acc_func, args = generic_acc_info['misc_N']
            else:
                continue
            if verbose:
                print("miscellaneous generic acceptor:", atom)
        acc_atoms.append(atom)
        acc_data.append([atom, acc_func, tuple([atom] + args)])
    return acc_atoms, acc_data

def _find_donors(model, d_params, limited_donors, generic_don_info):
    don_atoms = []
    don_data = []
    std_donors = {}
    for dp in d_params:
        group_key, donorIndex, geom_type, tau_sym, arg_list, test_dist = dp

        if group_key:
            groups = find_group(group_key, [model])
        else:
            # generic donors
            groups = []
            for atom in model.atoms:
                if atom in std_donors:
                    continue
                if atom.element.number not in [7,8,16]:
                    continue
                if limited_donors and atom not in limited_donors:
                    continue
                # oxygen, nitrogen, or sulfur
                try:
                    expect_bonds = type_info[atom.idatm_type].substituents
                except KeyError:
                    expect_bonds = 0
                num_bonds = atom.num_bonds
                # screen out the partial terminal N that AddH can leave, since the geometry is
                # problematic and the H direction isn't really determined
                if atom.idatm_type == "Npl" and num_bonds == 2 \
                and 1 in [n.element.number for n in atom.neighbors]:
                    continue
                if num_bonds < expect_bonds:
                    groups.append([atom])
                    continue
                for bonded in atom.neighbors:
                    if bonded.element.number == 1:
                        groups.append([atom])
                        break
            if verbose:
                for g in groups:
                    print("generic donor:", g[0])

        if groups and geom_type == theta_tau:
            # extend probe distance by H-bond length so that all relevant acceptors will be found
            test_dist = test_dist + Element.bond_length(groups[0][donorIndex].element, 'H')
        for group in groups:
            donor_atom = group[donorIndex]
            if limited_donors and donor_atom not in limited_donors:
                continue
            if donor_atom in std_donors:
                if group_key != std_donors[donor_atom] and not (
                # conflicts of non-ring groups with ring
                # groups not considered a problem (non-ring
                # groups "win")
                group_key[0] in _ring_funcs and std_donors[donor_atom][0] not in _ring_funcs):
                    global _problem
                    _problem = ("donor", donor_atom, std_donors[donor_atom], group_key)
                continue
            std_donors[donor_atom] = group_key
            don_atoms.append(donor_atom)
            don_data.append((geom_type, tau_sym, arg_list, test_dist))
    return don_atoms, don_data

'''
from chimera.selection import currentAtoms, currentMolecules

def createHBonds(models=None, intramodel=True, intermodel=True, relax=True,
    dist_slop=recDistSlop, angle_slop=recAngleSlop, twoColors=False,
    selRestrict=None, lineWidth=1.0, saveFile=None, batch=False,
    inter_submodel=False, makePseudobonds=True, retainCurrent=False,
    reveal=False, namingStyle=None, log=False, cache_da=None,
    color=(0.0, 0.8, 0.9, 1.0), slopColor=(0.95, 0.5, 0.0, 1.0),
    showDist=False, intraRes=True, intraMol=True, lineType="solid"):

    """Wrapper to be called by gui and command line.

       Use findHBonds for other programming applications.
    """

    from Midas import MidasError
    inColors = (color, slopColor)
    outColors = []
    for c in inColors:
        if isinstance(c, basestring):
            from chimera.colorTable import getColorByName
            try:
                outColors.append(getColorByName(c))
            except KeyError:
                raise MidasError("No known color named '%s'" % c)
        elif isinstance(c, tuple):
            oc = chimera.MaterialColor()
            oc.ambientDiffuse = c[:3]
            if len(c) > 3:
                oc.opacity = c[-1]
            outColors.append(oc)
        else:
            outColors.append(c)
    bondColor, slopColor = outColors

    donors = acceptors = None
    if selRestrict is not None:
        selAtoms = currentAtoms(asDict=True)
        if not selAtoms:
            if batch:
                return
            raise UserError("No atoms in selection.")
        if (not intermodel or selRestrict == "both") and models is None:
            # intramodel only or both ends in selection
            models = currentMolecules()
        if selRestrict == "both":
            # both ends in selection
            donors = acceptors = selAtoms

    if models is None:
        models = chimera.openModels.list(modelTypes=[chimera.Molecule])

    if not relax:
        dist_slop = angle_slop = 0.0

    if cache_da == None:
        # cache trajectories by default
        cache_da = len(models) == 1 and len(models[0].coordSets) > 1

    hbonds = findHBonds(models, intermodel=intermodel,
        intramodel=intramodel, dist_slop=dist_slop,
        angle_slop=angle_slop, donors=donors, acceptors=acceptors,
        inter_submodel=inter_submodel, cache_da=cache_da)
    if selRestrict and donors == None:
        hbonds = filterHBondsBySel(hbonds, selAtoms, selRestrict)
    if not intraMol:
        hbonds = [hb for hb in hbonds if hb[0].molecule.rootForAtom(hb[0], True)
                != hb[1].molecule.rootForAtom(hb[1], True)]
    if not intraRes:
        hbonds = [hb for hb in hbonds if hb[0].residue != hb[1].residue]
    
    outputInfo = (intermodel, intramodel, relax, dist_slop, angle_slop,
                            models, hbonds)
    if log:
        import sys
        # provide a separator from other output
        print>>sys.stdout, ""
        _fileOutput(sys.stdout, outputInfo, namingStyle)
    if saveFile == '-':
        from MolInfoDialog import SaveMolInfoDialog
        SaveMolInfoDialog(outputInfo, _fileOutput,
                    initialfile="hbond.info",
                    title="Choose H-Bond Save File",
                    historyID="H-bond info")
    elif saveFile is not None:
        _fileOutput(saveFile, outputInfo, namingStyle)

    session.logger.status("%d hydrogen bonds found"
                % len(hbonds), log=1, blank_after=120)
    if not makePseudobonds:
        return

    if twoColors:
        # color relaxed constraints differently
        precise = findHBonds(models,
            intermodel=intermodel, intramodel=intramodel,
            donors=donors, acceptors=acceptors,
            inter_submodel=inter_submodel, cache_da=cache_da)
        if selRestrict and donors == None:
            precise = filterHBondsBySel(precise, selAtoms, selRestrict)
        if not intraMol:
            precise = [hb for hb in precise if hb[0].molecule.rootForAtom(hb[0], True)
                    != hb[1].molecule.rootForAtom(hb[1], True)]
        if not intraRes:
            precise = [hb for hb in precise if hb[0].residue != hb[1].residue]
        # give another opportunity to read the result...
        session.logger.status("%d hydrogen bonds found" % len(hbonds),
                                blank_after=120)

    from chimera.misc import getPseudoBondGroup
    pbg = getPseudoBondGroup("hydrogen bonds", issueHint=True)
    if not retainCurrent:
        pbg.deleteAll()
    pbg.lineWidth = lineWidth
    lineTypes = ["solid", "dashed", "dotted", "dash-dot", "dash-dot-dot"]
    try:
        ltVal = lineTypes.index(lineType) + 1
    except ValueError:
        raise MidasError("No known lineType '%s'; legal values are %s" % 
            (lineType, ", ".join(lineTypes)))
    pbg.lineType = ltVal

    for don, acc in hbonds:
        nearest = None
        for h in [x for x in don.neighbors if x.element.number == 1]:
            sqdist = h.scene_coord.sqdistance(acc.scene_coord)
            if nearest is None or sqdist < nsqdist:
                nearest = h
                nsqdist = sqdist
        if nearest is not None:
            don = nearest
        if don.associated(acc, "hydrogen bonds"):
            continue
        pb = pbg.newPseudoBond(don, acc)
        if twoColors:
            if (don, acc) in precise:
                color = bondColor
            else:
                color = slopColor
        else:
            color = bondColor
        pb.color = color
        if reveal:
            for end in [don, acc]:
                if end.display:
                    continue
                for ea in end.residue.oslChildren():
                    ea.display = True
    from StructMeasure import DistMonitor
    if showDist:
        DistMonitor.addMonitoredGroup(pbg)
    else:
        DistMonitor.removeMonitoredGroup(pbg)
        global _sceneHandlersAdded
        if not _sceneHandlersAdded:
            from chimera import triggers, SCENE_TOOL_SAVE, SCENE_TOOL_RESTORE
            triggers.addHandler(SCENE_TOOL_SAVE, _sceneSave, None)
            triggers.addHandler(SCENE_TOOL_RESTORE, _sceneRestore, None)
            _sceneHandlersAdded = True

_sceneHandlersAdded = False
def _sceneSave(trigName, myData, scene):
    from chimera.misc import getPseudoBondGroup
    pbg = getPseudoBondGroup("hydrogen bonds", create=False)
    if not pbg:
        return
    from StructMeasure.DistMonitor import monitoredGroups
    if pbg in monitoredGroups:
        return
    from Animate.Tools import get_saveable_pb_info
    scene.tool_settings['hydrogen bonds'] = get_saveable_pb_info(pbg)

def _sceneRestore(trigName, myData, scene):
    from chimera.misc import getPseudoBondGroup
    pbg = getPseudoBondGroup("hydrogen bonds", create=False)
    if not pbg:
        return
    from StructMeasure.DistMonitor import monitoredGroups
    if pbg in monitoredGroups:
        return
    info = scene.tool_settings.get('hydrogen bonds')
    if not info:
        pbg.deleteAll()
        return
    from Animate.Tools import restore_pbs
    restore_pbs(pbg, info)

def filterHBondsBySel(hbonds, selAtoms, selRestrict):
    filtered = []
    selBoth = selRestrict == "both"
    selCross = selRestrict == "cross"
    if not selBoth and not selCross and selRestrict != "any":
        from Midas import evalSpec
        customAtoms = set(evalSpec(selRestrict).atoms())
    else:
        customAtoms = None
    for d, a in hbonds:
        d_in =  d in selAtoms
        a_in =  a in selAtoms
        num = a_in + d_in
        if num == 0:
            continue
        if customAtoms != None:
            if not ((d in customAtoms and a_in)
                    or (a in customAtoms and d_in)):
                continue
        else:
            if num == 1:
                if selBoth:
                    continue
            elif selCross:
                continue
        filtered.append((d, a))
    return filtered

def _fileOutput(fileName, outputInfo, namingStyle):
    intermodel, intramodel, relaxConstraints, \
            dist_slop, angle_slop, modelList, hbonds = outputInfo
    from OpenSave import osOpen
    outFile = osOpen(fileName, 'w')
    if intermodel:
        outFile.write("Finding intermodel H-bonds\n")
    if intramodel:
        outFile.write("Finding intramodel H-bonds\n")
    if relaxConstraints:
        outFile.write("Constraints relaxed by %g angstroms"
            " and %d degrees\n" % (dist_slop, angle_slop))
    else:
        outFile.write("Using precise constraint criteria\n")
    outFile.write("Models used:\n")
    for model in modelList:
        outFile.write("\t%s %s\n" % (model.oslIdent(), model.name))
    outFile.write("\nH-bonds (donor, acceptor, hydrogen, D..A dist, D-H..A dist):\n")
    # want the bonds listed in some kind of consistent
    # order...
    hbonds.sort(_oslSort)

    # figure out field widths to make things line up
    dwidth = awidth = hwidth = 0
    labels = {}
    from chimera.misc import chimeraLabel
    for don, acc in hbonds:
        labels[don] = chimeraLabel(don, style=namingStyle)
        labels[acc] = chimeraLabel(acc, style=namingStyle)
        dwidth = max(dwidth, len(labels[don]))
        awidth = max(awidth, len(labels[acc]))
        da = don.scene_coord.distance(acc.scene_coord)
        dha = None
        for h in don.neighbors:
            if h.element.number != 1:
                continue
            d = h.scene_coord.distance(acc.scene_coord)
            if dha is None or d < dha:
                dha = d
                hyd = h
        if dha is None:
            dhaOut = "N/A"
            hydOut = "no hydrogen"
        else:
            dhaOut = "%5.3f" % dha
            hydOut = chimeraLabel(hyd, style=namingStyle)
        hwidth = max(hwidth, len(hydOut))
        labels[(don, acc)] = (hydOut, da, dhaOut)
    for don, acc in hbonds:
        hydOut, da, dhaOut = labels[(don, acc)]
        outFile.write("%*s  %*s  %*s  %5.3f  %s\n" % (
            0-dwidth, labels[don], 0-awidth, labels[acc],
            0-hwidth, hydOut, da, dhaOut))
    if outFile != fileName:
        # we opened it, so close it...
        outFile.close()

def _oslSort(hb1, hb2):
    from chimera.misc import oslCmp
    don1, acc1 = hb1
    don2, acc2 = hb2

    sval = oslCmp(don1.oslIdent(), don2.oslIdent())
    if sval == 0:
        return oslCmp(acc1.oslIdent(), acc2.oslIdent())
    return sval
'''
