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
from chimerax.atomic import AtomicStructure
from chimerax.core.commands import run

from . import dbparsers

from typing import Callable, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

import re

@dataclass
class Database(ABC):
    parser_factory: Callable[[dbparsers.Parser], object]
    parser: Optional[object] = None
    name: str = ""

    @abstractmethod
    def load_model(chimerax_session, match_code):
        pass

    @staticmethod
    def display_model(chimerax_session, ref_atomspec, model, chain_id):
        spec = model.atomspec
        if chain_id:
            spec += '/' + chain_id
        if ref_atomspec:
            run(chimerax_session, "matchmaker %s to %s" %
                (spec, ref_atomspec))
        else:
            run(chimerax_session, "select add %s" % spec)

    def parse(self, query, sequence, results):
        self.parser = self.parser_factory(query, sequence, results)

@dataclass
class NCBIDB(Database):
    name: str = ""
    parser_factory: object = dbparsers.PDBParser
    NCBI_IDS: tuple[str, str] = ("ref", "gi")
    NCBI_ID_URL: str = "https://ncbi.nlm.nih.gov/protein/%s"
    NCBI_ID_PAT = re.compile(r"\b(%s)\|([^|]+)\|" % '|'.join(NCBI_IDS))

    @staticmethod
    def load_model(chimerax_session, match_code):
        """
        url: Instance of Qt.QtCore.QUrl
        """
        # If there are two underscores only split on the first
        parts = match_code.split('_', 1)
        try:
            pdb_id, chain_id = parts
        except:
            pdb_id, chain_id = parts[0], None
        models = run(chimerax_session, "open pdb:%s" % pdb_id)[0]
        if isinstance(models, AtomicStructure):
            models = [models]
        return models, chain_id

    def add_url(self, hit, m):
        mdb = None
        mid = None
        match = self.NCBI_ID_PAT.search(m.name)
        if match:
            mdb = match.group(1)
            mid = match.group(2)
            hit["name"] = "%s (%s)" % (mid, mdb)
            hit["url"] = self.NCBI_ID_URL % mid
        else:
            hit["name"] = m.name
            hit["url"]= ""
        return hit

    @staticmethod
    def add_info(session, matches):
        from .pdbinfo import fetch_pdb_info
        chain_ids = matches.keys()
        data = fetch_pdb_info(session, chain_ids)
        for chain_id, hit in matches.items():
            for k, v in data[chain_id].items():
                if isinstance(v, list):
                    v = ", ".join([str(s) for s in v])
                hit[k] = v

@dataclass
class PDB(NCBIDB):
    name: str = "pdb"
    pretty_name: str = "Protein Data Bank"


@dataclass
class NRDB(NCBIDB):
    name: str = "nrdb"
    pretty_name: str = "NRDB"

@dataclass
class AlphaFoldDb(Database):
    name: str = "alphafold"
    pretty_name: str = "AlphaFold Database"
    parser_factory: object = dbparsers.AlphaFoldParser
    AlphaFold_URL: str = "https://alphafold.ebi.ac.uk/files/AF-%s-F1-model_v1.pdb"

    @staticmethod
    def load_model(chimerax_session, match_code):
        models = run(chimerax_session, "alphafold fetch %s" % match_code)[0]
        if isinstance(models, AtomicStructure):
            models = [models]
        return models, None

    def add_info(self, session, matches):
        for match in matches:
            raw_desc = matches[match]["description"]
            # Splitting by = then spaces lets us cut out the X=VAL attributes
            # and the longform Uniprot ID,
            hit_title = ' '.join(raw_desc.split('=')[0].split(' ')[1:-1])
            matches[match]["title"] = hit_title
            matches[match]["chain_species"] = self._get_species(raw_desc)

    def _get_species(self, raw_desc):
        """AlphaFold's BLAST output is polluted with lots of metadata in the
        form XY=Z, in the order OS OX GN PE SV, some of which may be missing.
        This is some ugly string hacking to return the species if it exists."""
        try:
            species_loc = raw_desc.index('OS')
        except:
            # No species
            return ""
        else:
            next_attr_start = raw_desc[species_loc+3:].index('=')
            # Cut off the first equals sign, and the ' XY' of the
            # second XY parameter
            return raw_desc[species_loc+3:][:next_attr_start-3]

def get_database(db):
    """Instantiate and return a database instance.
    db: A supported database e.g 'alphafold', 'nr', 'pdb'
    """
    dbs = {
        'alphafold': AlphaFoldDb,
        'nr': NRDB,
        'pdb': PDB
    }
    return dbs[db]() # Instantiate the class so it can access 'self'