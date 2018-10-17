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

def modeller_copy(seq):
	from copy import copy
	mseq = copy(seq)
	mseq.name = mseq.name[:16].replace(' ', '_')
	mseq.characters = "".join([c.upper() if c.isalpha() else '-' for c in mseq.characters])
	return mseq


def write_modeller_scripts(license_key, num_models, het_preserve, water_preserve, hydrogens, fast, loop_info,
        custom_script, temp_path, thorough_opt, dist_restraints_path):
    """Function to prepare the Modeller scripts.

    Returns (path-to-Modeller-script, path-to-Modeller-XML-config-file,
        temporary dir [tempfile.TemporaryDirectory-like instance])
    """

    if temp_path:
        # not auto-destroyed
        class FakeTmpDir:
            name = temp_path
        temp_dir = FakeTmpDir()
    else:
        import tempfile
        temp_dir = tempfile.TemporaryDirectory(dir=temp_path)

    # Write out a config file
    # Remember to bump the (non-xml) version number when changing contents
    import os
    with open(os.path.join(temp_dir.name, "ModellerScriptConfig.xml"), 'w') as config_file:
        print(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<modeller9v8>\n'
            '\t<key>%s</key>\n'
            '\t<version>2</version>\n'
            '\t<numModel>%s</numModel>\n'
            '\t<hetAtom>%s</hetAtom>\n'
            '\t<water>%s</water>\n'
            '\t<allHydrogen>%s</allHydrogen>\n'
            '\t<veryFast>%s</veryFast>\n'
            '\t<loopInfo>%s</loopInfo>\n'
            '</modeller9v8>' % (license_key, num_models, int(het_preserve), int(water_preserve), int(hydrogens),
                int(fast), repr(loop_info)), file=config_file)

    if custom_script:
        return custom_script, config_file.name, temp_dir

    with open(os.path.join(temp_dir.name, "ModellerModelling.py"), 'w') as script_file:
        # header: read in from script_head.py
        pkg_dir = os.path.dirname(__file__)
        with open(os.path.join(pkg_dir, "script_head.py"), 'r') as f:
            script_file.write(f.read())

        # write body of script based on arg values
        body = '\n'
        if het_preserve:
            body += '# Read in HETATM records from template PDBs\n'
            body += 'env.io.hetatm = True\n\n'
        if water_preserve:
            body += '# Read in water molecules from template PDBs \n'
            body += 'env.io.water = True\n\n'

        body += '# create a subclass of automodel or loopmodel, MyModel.\n'
        body += '# user can further modify the MyModel class, to override certain routines.\n'

        if hydrogens:
            body += 'class MyModel(allhmodel):'
        elif loop_info:
            method_prefix, loop_data = loop_info
            res_range = ",\n".join(["\t\t\tself.residue_range('%s', '%s')" % (start, end)
                                    for start, end in loop_data])
            body += 'class MyModel(%sloopmodel):' % method_prefix
            body += """
    def select_loop_atoms(self):
        from modeller import selection
        return selection(%s)

    def select_atoms(self):
        from modeller import selection
        return selection(%s)

""" % (res_range, res_range)
        else:
            body += 'class MyModel(automodel):'

        if dist_restraints_path:
            body += """
    def customised_function(self): pass

    def special_restraints(self, aln):
        %s

    #code overrides the special_patches method.
    # e.g. to include the addtional disulfides.
    #def special_patches(self, aln):
    """	% process_dist_restraints(dist_restraints_path)
        else:	# put in a commented-out line for special restraints
            body += """
    def customised_function(self): pass
    #code overrides the special_restraints method

    #def special_restraints(self, aln):

    #code overrides the special_patches method.
    # e.g. to include the addtional disulfides.
    #def special_patches(self, aln):
    """

        if loop_info:
            body += """
a = MyModel(env, sequence = tarSeq,
        # alignment file with template codes and target sequence
        alnfile = 'alignment.ali',
        # name of initial PDB template
        knowns = template[0])

# one fixed model to base loops on
a.starting_model = 1
a.ending_model = 1

# %s loop models
loopRefinement = True
a.loop.starting_model = 1
a.loop.ending_model = %s
a.loop.assess_methods=(assess.DOPE, assess.GA341, assess.normalized_dope)

""" % (num_models, num_models)
        else:
            body += """
a = MyModel(env, sequence = tarSeq,
        # alignment file with template codes and target sequence
        alnfile = 'alignment.ali',
        # PDB codes of the templates
        knowns = template)
# index of the first model
a.starting_model = 1
# index of the last model
a.ending_model = %s
loopRefinement = False

""" % num_models

        if fast:
            body += '# To get an approximate model very quickly\n'
            body += 'a.very_fast()\n\n'

        if thorough_opt:
            body += """
# perform thorough optimization
a.library_schedule = autosched.normal
a.max_var_iterations = 500
a.md_level = refine.slow

"""

        script_file.write(body)

        # Tail part: contains the a.make and data output
        with open(os.path.join(pkg_dir, "script_tail.py"), 'r') as f:
            script_file.write(f.read())

    return script_file.name, config_file.name, temp_dir

#TODO: handle chain IDs?  Does Modeller support that for this purpose?
def _process_dist_restraints(filename):
    """
    Parses the distance restraints file specified by user and returns code that needs
    to be injected into the "special_restraints" method of the Modeller input script.
    The distance restraints file needs four space-seperated numbers on each line.
    Format: res1 res2 dist stdev
    res1 and res2 can be residue ranges (e.g. res1 = 123-789), in which case atoms
    pseudoatom will be created by Modeller.
    """

    # this function will check whether a residue number is valid
    def verify_residue(value):
        try:
            res = int(value)
        except ValueError:
            raise UserError('The residue nr. %s specified in the additional distance restraints file'
                ' is not an integer.' % value)
        if res <= 0:
            raise UserError('The residue nr. %d specified in the additional distance restraints file'
                ' needs to be greater than 0.' % res)
        return res

    # check whether the specified path is a file:
    from os.path import isfile
    if not isfile(filename):
        raise UserError('The user-specified additional distance restraints file "%s" does not exist.'
            % filename)

    # initialize code that will be returned:
    headcode = """
                rsr = self.restraints
                atm = self.atoms
"""
    maincode = ""

    # parse file:
    with open(filename, 'r') as distrestrfile:
        i = 0 # number of pseudoatoms
        pseudodict = {} # to avoid having duplicate pseudoatoms
        for line in distrestrfile:

            try:
                residues1, residues2, dist, stdev = line.strip().split()
            except TypeError:
                raise UserError('The line "%s" specified in the additional distance restraints file'
                    ' is not exactly four space-seperated values.' % line)

            # check whether dist and stdev are ok:    
            try:
                dist = float(dist)
                stdev = float(stdev)
            except ValueError:
                raise UserError('The distance %s or standard deviation %s specified in the additional'
                    ' distance restraints file is not a real number.' % (dist, stdev))
            if stdev <= 0:
                raise UserError('The standard deviation %f specified in the additional distance restraints'
                    ' file needs to be greater than 0.' % stdev)

            # check whether residue ranges or single residues where specified:
            atoms = []
            for residues in [residues1, residues2]:
                if '-' in residues: # looks like a residue range was specified -> verify
                    try:
                        res1, res2 = residues.split('-')
                    except TypeError:
                        raise UserError('The residue range %s specified in the additional distance'
                            ' restraints file is not valid.' % residues)
                    resA = verify_residue(res1)
                    resB = verify_residue(res2)
                    if (resA, resB) not in pseudodict:
                        i += 1
                        atom = 'pseudo' + str(i)
                        # add to dict:
                        pseudodict[(resA, resB)] = atom
                        # add pseudoatoms to output code:
                        headcode +=    """
                        %s = pseudo_atom.gravity_center(self.residue_range('%d:','%d:'))
                        rsr.pseudo_atoms.append(%s)
        """ % (atom, resA, resB, atom)
                    else:
                        atom = pseudodict[(resA, resB)]
                else: # hopefully, a single residue was specified -> verify    
                    res = verify_residue(residues)
                    atom = "atm['CA:" + str(res) +"']"    
                atoms.append(atom)

            # add restraints line to output
            maincode += """
                    rsr.add(forms.gaussian(group=physical.xy_distance, feature=features.distance(%s,%s), mean=%f, stdev=%f))
""" % (atoms[0], atoms[1], dist, stdev)


    # concatenate and return output code:
    return headcode + maincode
