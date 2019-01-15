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
# Wrap image data as grid data for displaying surface, meshes, and volumes.
#
from .. import GridData

# -----------------------------------------------------------------------------
#
def dicom_grids(paths, log = None, verbose = False):
  from .dicom_format import find_dicom_series, DicomData
  series = find_dicom_series(paths, verbose = verbose)
  grids = []
  for s in series:
    if s.num_times != 1:
      if log:
        log.warning('DICOM time series are not yet supported, %s... (%d files, %d times)'
                    % (s.paths[0], len(s.paths), s.num_times))
      continue
    d = DicomData(s)
    if d.mode == 'RGB':
      cgrids = [DicomGrid(d, channel) for channel in (0,1,2)]
      colors = [(1,0,0,1), (0,1,0,1), (0,0,1,1)]
      suffixes = [' red', ' green', ' blue']
      for g,rgba,cname in zip(cgrids,colors,suffixes):
        g.name += cname
        g.rgba = rgba
      grids.extend(cgrids)
    else:
      g = DicomGrid(d)
      grids.append(g)
  return grids

# -----------------------------------------------------------------------------
#
class DicomGrid(GridData):

  def __init__(self, d, channel = None):

    self.dicom_data = d

    GridData.__init__(self, d.data_size, d.value_type,
                      d.data_origin, d.data_step,
                      path = d.paths, name = d.name,
                      file_type = 'dicom', channel = channel)

    self.initial_plane_display = True
    self.initial_thresholds_linear = True
    self.ignore_pad_value = d.pad_value

  # ---------------------------------------------------------------------------
  #
  def read_matrix(self, ijk_origin, ijk_size, ijk_step, progress):

    from ..readarray import allocate_array
    m = allocate_array(ijk_size, self.value_type, ijk_step, progress)
    self.dicom_data.read_matrix(ijk_origin, ijk_size, ijk_step, self.channel, m, progress)
    return m