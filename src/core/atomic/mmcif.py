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

"""
mmcif: mmCIF format support
===========================

Read mmCIF files.
"""

from ..errors import UserError

_builtin_open = open
_initialized = False

_additional_categories = (
    "pdbx_struct_assembly",
    "pdbx_struct_assembly_gen",
    "pdbx_struct_oper_list",
    "entity",
    "entity_src_gen",
    "entity_src_nat",
    "cell",
    "symmetry",
    "software",
    "citation",
    "citation_author",
)


def open_mmcif(session, path, file_name=None, auto_style=True, coordsets=False, atomic=True,
               log_info=True, extra_categories=()):
    # mmCIF parsing requires an uncompressed file

    from . import _mmcif
    _mmcif.set_Python_locate_function(
        lambda name, session=session: _get_template(session, name))
    categories = _additional_categories + tuple(extra_categories)
    pointers = _mmcif.parse_mmCIF_file(path, categories, session.logger, coordsets, atomic)

    if file_name is None:
        from os.path import basename
        file_name = basename(path)
    if atomic:
        from .structure import AtomicStructure as StructureClass
    else:
        from .structure import Structure as StructureClass
    models = [StructureClass(session, name=file_name, c_pointer=p, auto_style=auto_style, log_info=log_info)
              for p in pointers]
    for m in models:
        m.filename = path

    info = "Opened mmCIF data containing %d atoms%s %d bonds" % (
        sum(m.num_atoms for m in models),
        ("," if coordsets else " and"),
        sum(m.num_bonds for m in models))
    if coordsets:
        num_cs = 0
        for m in models:
            num_cs += m.num_coordsets
        info += " and %s coordinate sets" % num_cs
        if session.ui.is_gui:
            mc = [m for m in models if m.num_coordsets > 1]
            if mc:
                from ..commands.coordset import coordset_slider
                coordset_slider(session, mc)
    return models, info


_mmcif_sources = {
    # "rcsb": "http://www.pdb.org/pdb/files/%s.cif",
    "rcsb": "http://files.rcsb.org/download/%s.cif",
    "pdbe": "http://www.ebi.ac.uk/pdbe/entry-files/download/%s.cif",
    "pdbe_updated": "http://www.ebi.ac.uk/pdbe/entry-files/download/%s_updated.cif",
    "pdbj": "https://pdbj.org/rest/downloadPDBfile?format=mmcif&id=%s",
}


def fetch_mmcif(session, pdb_id, fetch_source="rcsb", ignore_cache=False, **kw):
    if len(pdb_id) != 4:
        raise UserError('PDB identifiers are 4 characters long, got "%s"' % pdb_id)
    import os
    pdb_id = pdb_id.lower()
    filename = None
    if not fetch_source.endswith('updated'):
        # check on local system -- TODO: configure location
        subdir = pdb_id[1:3]
        filename = "/databases/mol/mmCIF/%s/%s.cif" % (subdir, pdb_id)
        if os.path.exists(filename):
            session.logger.info("Fetching mmCIF %s from system cache: %s" % (pdb_id, filename))
        else:
            filename = None
    if filename is None:
        base_url = _mmcif_sources.get(fetch_source, None)
        if base_url is None:
            raise UserError('unrecognized mmCIF/PDB source "%s"' % fetch_source)
        url = base_url % pdb_id
        pdb_name = "%s.cif" % pdb_id
        from ..fetch import fetch_file
        filename = fetch_file(session, url, 'mmCIF %s' % pdb_id, pdb_name, 'PDB',
                              ignore_cache=ignore_cache)
        # double check that a mmCIF file was downloaded instead of an
        # HTML error message saying the ID does not exist
        with open(filename, 'U') as f:
            line = f.readline()
            if not line.startswith(('data_', '#')):
                f.close()
                import os
                os.remove(filename)
                raise UserError("Invalid mmCIF identifier")

    session.logger.status("Opening mmCIF %s" % (pdb_id,))
    from .. import io
    models, status = io.open_data(session, filename, format='mmcif', name=pdb_id, **kw)
    return models, status


def fetch_mmcif_pdbe(session, pdb_id, **kw):
    return fetch_mmcif(session, pdb_id, fetch_source="pdbe", **kw)


def fetch_mmcif_pdbe_updated(session, pdb_id, **kw):
    return fetch_mmcif(session, pdb_id, fetch_source="pdbe_updated", **kw)


def fetch_mmcif_pdbj(session, pdb_id, **kw):
    return fetch_mmcif(session, pdb_id, fetch_source="pdbj", **kw)


def _get_template(session, name):
    """Get Chemical Component Dictionary (CCD) entry"""
    from ..fetch import fetch_file
    filename = '%s.cif' % name
    url = "http://ligand-expo.rcsb.org/reports/%s/%s/%s.cif" % (name[0], name,
                                                                name)
    try:
        return fetch_file(session, url, 'CCD %s' % name, filename, 'CCD')
    except UserError:
        session.logger.warning(
            "Unable to fetch template for '%s': might be missing bonds"
            % name)
        return None


def register_mmcif_format():
    global _initialized
    if _initialized:
        return

    from .. import io
    from . import structure

    # mmCIF uses same file suffix as CIF
    # PDB uses chemical/x-cif when serving CCD files
    # io.register_format(
    #     "CIF", structure.CATEGORY, (), ("cif",),
    #     mime=("chemical/x-cif"),
    #    reference="http://www.iucr.org/__data/iucr/cif/standard/cifstd1.html")
    from .mmcif_write import write_mmcif
    io.register_format(
        "mmCIF", structure.CATEGORY, (".cif", ".mmcif"), ("mmcif",),
        mime=("chemical/x-mmcif",),
        reference="http://mmcif.wwpdb.org/",
        open_func=open_mmcif, export_func=write_mmcif)


def register_mmcif_fetch():
    from .. import fetch
    fetch.register_fetch('pdb', fetch_mmcif, 'mmcif',
                         prefixes=['pdb'], is_default_format=True)
    fetch.register_fetch('pdbe', fetch_mmcif_pdbe, 'mmcif',
                         prefixes=['pdbe'], is_default_format=True)
    fetch.register_fetch('pdbe_updated', fetch_mmcif_pdbe_updated, 'mmcif',
                         prefixes=['pdbe_updated'], is_default_format=True)
    fetch.register_fetch('pdbj', fetch_mmcif_pdbj, 'mmcif',
                         prefixes=['pdbj'], is_default_format=True)


def quote(s):
    """Return CIF quoted value"""
    s = str(s)
    examine = s[0:1]
    sing_quote = examine == "'"
    dbl_quote = examine == '"'
    line_break = examine == '\n'
    special = examine in ' [;'
    for i in range(1, len(s)):
        examine = s[i:i + 1]
        if examine == '" ':
            dbl_quote = True
        elif examine == "' ":
            sing_quote = True
        elif examine[0] == '\n':
            line_break = True
        elif examine[0] == ' ':
            special = True
    if line_break or (sing_quote and dbl_quote):
        return ';' + s + '\n;\n'
    if sing_quote:
        return '"%s"' % s
    if dbl_quote:
        return "'%s'" % s
    if special:
        return "'%s'" % s
    return s


def citations(model, only=None):
    """Return APA-style HTML citations for model

    Parameters
    ----------
    model : instance of a :py:class:`~chimerax.core.atomic.AtomicStructure`
        The model.
    """
    if only is not None:
        only = only.casefold()
    from .structure import Structure
    if not isinstance(model, Structure):
        return ""
    citation, citation_author = get_mmcif_tables_from_metadata(model, [
        "citation", "citation_author"])
    if not citation:
        return ""
    if citation_author is None:
        citation_author = ()

    try:
        cf = citation.fields([
            'id', 'title', 'journal_abbrev', 'journal_volume', 'year'])
    except ValueError:
        return ""   # missing fields
    cf2 = citation.fields([
        'page_first', 'page_last',
        'journal_issue', 'pdbx_database_id_pubmed', 'pdbx_database_id_doi'],
        allow_missing_fields=True)
    try:
        caf = citation_author.fields(['citation_id', 'name', 'ordinal'])
        caf = tuple((ci, n, int(o)) for ci, n, o in caf)
    except ValueError:
        caf = ()
    citations = []
    from html import escape
    from itertools import zip_longest
    for (i, t, ja, jv, y), (pf, pl, ji, pm, doi) in zip_longest(cf, cf2):
        if only is not None and i.casefold() != only:
            continue
        authors = [(n, o) for ci, n, o in caf if ci == i]
        authors.sort(key=lambda x: x[1])
        authors = ', '.join([n for n, o in authors])
        c = escape(authors)
        if c and c[-1] != '.':
            c += '. '
        c += ' (%s). %s' % (escape(y), escape(t))
        if c[-1] != '.':
            c += '.'
        if ja and ja not in '.?':
            c += ' <i>%s</i>' % escape(ja)
            if jv and jv not in '.?':
                c += ', <i>%s</i>' % escape(jv)
                if ji and ji not in '.?':
                    c += '(%s)' % escape(ji)
            if pf and pf not in '.?':
                c += ', %s' % escape(pf)
                if pl and pl not in '.?':
                    c += '-%s' % escape(pl)
        if pm and pm not in '.?':
            if c[-1] != '.':
                c += '.'
            p = escape(pm)
            c += ' PMID: <a href="http://www.ncbi.nlm.nih.gov/pubmed/%s">%s</a>' % (p, p)
        if doi and doi not in '.?':
            if c[-1] != '.':
                c += '.'
            d = escape(doi)
            c += ' DOI: <a href="http://dx.doi.org/%s">%s</a>' % (d, d)
        citations.append(c)
    return citations


def get_mmcif_tables(filename, table_names):
    """Extract mmCIF tables from a file

    Parameters
    ----------
    filename : str
        The name of the file.
    table_names : list of str
        A list of mmCIF category names.
    """
    from os import path
    if path.exists(filename):
        from . import _mmcif
        data = _mmcif.extract_mmCIF_tables(filename, table_names)
    else:
        data = {}
    tlist = []
    for name in table_names:
        if name not in data:
            tlist.append(MMCIFTable(name))
        else:
            tags, values = data[name]
            tlist.append(MMCIFTable(name, tags, values))
    return tlist


def get_mmcif_tables_from_metadata(model, table_names):
    """Extract mmCIF tables from previously read metadata

    Parameters
    ----------
    model : instance of a :py:class:`~chimerax.core.atomic.AtomicStructure`
        The model.
    table_names : list of str
        A list of mmCIF category names.
    """
    try:
        raw_tables = model.metadata
    except AttributeError:
        raise ValueError("Expected a structure")
    tlist = []
    for n in table_names:
        if n not in raw_tables or (n + ' data') not in raw_tables:
            tlist.append(None)
        else:
            tags = raw_tables[n]
            values = raw_tables[n + ' data']
            tlist.append(MMCIFTable(n, tags, values))
    return tlist


class MMCIFTable:
    # TODO: deal with case insensitivity of tags

    def __init__(self, table_name, tags=None, values=None):
        self.table_name = table_name
        self._tags = [] if tags is None else tags
        self._values = [] if values is None else values
        n = len(tags)
        if n == 0:
            assert len(values) == 0
        else:
            assert len(values) % n == 0

    def __bool__(self):
        return len(self._tags) != 0 and len(self._values) != 0

    def __eq__(self, other):
        # for debugging
        return self._tags == other._tags and self._values == other._values

    def __repr__(self):
        num_columns = len(self._tags)
        num_rows = len(self._values) / num_columns
        return "MMCIFTable(%s, %s, ...[%dx%d])" % (self.table_name, self._tags, num_rows, num_columns)

    def mapping(self, key_name, value_name, foreach=None):
        t = self._tags
        n = len(t)
        for name in (key_name, value_name, foreach):
            if name and name not in t:
                raise ValueError(
                    'Field "%s" not in table "%s", have fields %s'
                    % (name, self.table_name, ', '.join(t)))
        ki, vi = t.index(key_name), t.index(value_name)
        if foreach:
            fi = t.index(foreach)
            m = {}
            for k, v, f in zip(self._values[ki::n], self._values[vi::n], self._values[fi::n]):
                m.set_default(f, {})[k] = v
        else:
            m = dict(zip(self._values[ki::n], self._values[vi::n]))
        return m

    def fields(self, field_names, allow_missing_fields=False):
        t = self._tags
        n = len(self._tags)
        if allow_missing_fields:
            from itertools import zip_longest
            fi = [(t.index(f) if f in t else -1) for f in field_names]
            ftable = list(zip_longest(
                *(self._values[i::n] if i >= 0 else [] for i in fi),
                fillvalue=''))
        else:
            missing = [n for n in field_names if n not in t]
            if missing:
                from chimerax.core.commands.cli import commas, plural_form
                missed = commas(missing, ' and')
                missed_noun = plural_form(missing, 'Field')
                missed_verb = plural_form(missing, 'is', 'are')
                have = commas(t, ' and')
                have_noun = plural_form(t, 'field')
                raise ValueError('%s %s %s not in table "%s", have %s %s' % (
                    missed_noun, missed, missed_verb, self.table_name, have_noun,
                    have))
            fi = tuple(t.index(f) for f in field_names)
            ftable = list(zip(*(self._values[i::n] for i in fi)))
        return ftable

    def extend(self, table):
        """Extend mmCIF table

        Parameters
        ----------
        table : MMCIFTable to add on to current table

        If a column with a given tag exists, then that column is extended.
        Otherwise, a new column is added to the table.
        """
        if self.table_name != table.table_name:
            raise ValueError("incompatible tables")
        num_old_columns = len(self._tags)
        old_columns = [self._values[i::num_old_columns] for i in range(num_old_columns)]
        num_old_rows = len(old_columns[0])
        num_new_columns = len(table._tags)
        new_columns = [table._values[i::num_new_columns] for i in range(num_new_columns)]
        num_new_rows = len(new_columns[0])
        # extend existing columns
        new_unknown = ['?'] * num_new_rows
        new_values = dict(zip(table._tags, new_columns))
        for t, c in zip(self._tags, old_columns):
            d = new_values.pop(t, None)
            if d is None:
                c.extend(new_unknown)
            else:
                c.extend(d)
        # add additional columns if needed
        if new_values:
            old_tags = self._tags[:]
            old_unknown = ['?'] * num_old_rows
            for t, c in new_values.items():
                old_tags.append(t)
                old_columns.append(old_unknown + c)
            self._tags = old_tags
        from chimerax.core.utils import flattened
        self._values = flattened(zip(*old_columns), return_type=list)

    def has_field(self, field_name):
        return field_name in self._tags

    def field_has(self, field_name, value):
        try:
            i = self._tags.index(field_name)
        except ValueError:
            return False
        n = len(self._tags)
        return value in self._values[i::n]

    def num_rows(self):
        if len(self._tags) == 0:
            return 0
        return len(self._values) // len(self._tags)

    def print(self, file=None):
        if file is None:
            import sys
            file = sys.stdout
        if len(self._tags) == len(self._values):
            for t, v in zip(self._tags, self._values):
                print('_%s.%s %s' % (self.table_name, t, quote(v)), file=file)
        else:
            print('loop_', file=file)
            for t in self._tags:
                print('_%s.%s' % (self.table_name, t))
            n = len(self._tags)
            for i in range(0, len(self._values), n):
                print(' '.join(quote(x) for x in self._values[i:i + n]), file=file)
        print('#', file=file)
