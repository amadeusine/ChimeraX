# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2021 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

# Python/All
import re

# Python/Specific
from typing import Callable, List, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# ChimeraX/Core
from chimerax.core.commands import run

# ChimeraX/Bundles
from chimerax.alphafold.match import _log_alphafold_sequence_info
from chimerax.atomic import AtomicStructure
from chimerax.atomic import Sequence

# Local Imports
from . import dbparsers
from .pdbinfo import fetch_pdb_info

@dataclass
class Database(ABC):
    """Base class for defining blast protein databases; used to model the
    results of blast queries."""
    parser_factory: Callable[[dbparsers.Parser], object]
    parser: dbparsers.Parser = field(init=False)
    fetchable_col: str = ""
    name: str = ""
    default_cols: tuple = ("Name", "Evalue", "Description")
    # In BlastProteinWorker._process_results each hit's dict is created
    # and assigned an ID number, but we don't want to display it. It's
    # also used in BlastProteinResults._show_mav to retrieve selections.
    excluded_cols: tuple = ("id",)

    @abstractmethod
    def load_model(chimerax_session, match_code, ref_atomspec):
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
    fetchable_col: str = "name"
    NCBI_IDS: tuple[str, str] = ("ref", "gi")
    NCBI_ID_URL: str = "https://ncbi.nlm.nih.gov/protein/%s"
    NCBI_ID_PAT = re.compile(r"\b(%s)\|([^|]+)\|" % '|'.join(NCBI_IDS))
    default_cols: tuple = ("Name", "Evalue", "Description", "Resolution", "Ligand Symbols")

    @staticmethod
    def load_model(chimerax_session, match_code, ref_atomspec):
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
class AlphaFoldDB(Database):
    name: str = "alphafold"
    pretty_name: str = "AlphaFold Database"
    # The title of the data column that can be used to fetch the model
    fetchable_col: str = "name"
    parser_factory: object = dbparsers.AlphaFoldParser
    AlphaFold_URL: str = "https://alphafold.ebi.ac.uk/files/AF-%s-F1-model_v1.pdb"

    def load_model(self, chimerax_session, match_code, ref_atomspec):
        cmd = "alphafold fetch %s" % match_code
        if ref_atomspec:
            cmd += ' alignTo %s' % ref_atomspec
        models, _ = run(chimerax_session, cmd)

        # Log sequence similarity info
        if not ref_atomspec:
            query_name = self.parser.true_name or 'query'
            query_seq = Sequence(name = query_name,
                                 characters = self.parser.query_seq)
            for m in models:
                _log_alphafold_sequence_info(m, query_seq)
        # Hack around the fact that we use run(...) to load the model
        return [], None

    @staticmethod
    def add_info(session, matches):
        for match in matches:
            raw_desc = matches[match]["description"]
            # Splitting by = then spaces lets us cut out the X=VAL attributes
            # and the longform Uniprot ID,
            hit_title = ' '.join(raw_desc.split('=')[0].split(' ')[1:-1])
            uniprot_id = raw_desc.split(' ')[0].split('_')[0]
            matches[match]["title"] = hit_title
            matches[match]["chain_species"] = AlphaFoldDB._get_species(raw_desc)
            # Move UniProt ID to the correct column
            matches[match]["chain_sequence_id"] = uniprot_id

    @staticmethod
    def _get_species(raw_desc):
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


AvailableDBsDict = {
    'pdb': PDB,
    'nr': NRDB,
    'alphafold': AlphaFoldDB,
}
AvailableDBs = list(AvailableDBsDict.keys())
AvailableMatrices = ["BLOSUM45", "BLOSUM50", "BLOSUM62", "BLOSUM80", "BLOSUM90", "PAM30", "PAM70", "PAM250", "IDENTITY"]

def get_database(db: str) -> Database:
    """Instantiate and return a database instance.

    Parameters:
        db: A supported database e.g 'alphafold', 'nr', 'pdb'
    """
    return AvailableDBsDict[db]()
