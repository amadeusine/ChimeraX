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

import copy
from html import escape
import os
import pkg_resources
import shutil

def get_packages_info():
    # based on http://stackoverflow.com/questions/19086030/can-pip-or-setuptools-distribute-etc-list-the-license-used-by-each-install
    # updated for Python3 and modified for use in ChimeraX

    KEY_MAP = {
        "Name": 'name',
        "Version": 'version',
        "License": 'license',
        "Summary": 'summary',
        "Home-page": 'homepage',
    }
    empty_info = {}
    for key, name in KEY_MAP.items():
        empty_info[name] = ""

    infos = []
    for pkg in pkg_resources.working_set:
        if pkg.project_name.startswith('ChimeraX-'):
            continue
        info = copy.deepcopy(empty_info)
        try:
            lines = pkg.get_metadata_lines('METADATA')
        except (KeyError, IOError):
            lines = pkg.get_metadata_lines('PKG-INFO')

        classifier_licenses = []
        for line in lines:
            try:
                key, value = line.split(': ', 1)
            except ValueError:
                pass
            value = value.strip()
            if key in KEY_MAP:
                info[KEY_MAP[key]] = value
            elif key == 'Classifier':
                category, text = value.split('::', 1)
                category = category.strip()
                if category != 'License':
                    continue
                text = text.strip()
                # Classifier: License :: OSI Approved :: BSD License
                if text.startswith('OSI Approved'):
                    extract = text.split('::', 1)
                    if len(extract) > 1:
                        text = extract[1].strip()
                classifier_licenses.append(text)
        if classifier_licenses:
            #? if not info['license'].startswith('http'):
            info['license'] = ', '.join(classifier_licenses)

        license_file = find_license_file(pkg)
        info['license-file'] = license_file

        infos += [info]

    return infos

def find_license_file(pkg):
    # return absolute path to a file with the license for a package if found
    import os
    import fnmatch
    import re
    license_file = None

    # scan egg/wheel info for a license
    dir_re = re.compile(fnmatch.translate('%s-*.dist-info' % pkg.project_name))
    for filename in os.listdir(pkg.location):
        if dir_re.match(filename):
            break
    else:
        return license_file

    top_levels = []
    license_re = re.compile('licen[sc]e', re.I)
    dirname = os.path.join(pkg.location, filename)
    for filename in os.listdir(dirname):
        if filename == 'top_level.txt':
            fn = os.path.join(dirname, 'top_level.txt')
            with open(fn) as f:
                top_levels = [x.strip() for x in f.readlines()]
        elif license_re.match(filename):
            license_file = os.path.join(dirname, filename)

    # scan modules provided by egg/wheel for a license
    if not license_file and top_levels:
        import importlib
        for t in top_levels:
            try:
                m = importlib.import_module(t)
            except:
                continue
            if not hasattr(m, '__path__'):
                continue
            for dirname in m.__path__:
                for filename in os.listdir(dirname):
                    if license_re.match(filename):
                        license_file = os.path.join(dirname, filename)
                        return license_file
    return license_file

def html4_id(name):
    # must match [A-Za-z][-A-Za-z0-9_:.]*
    # Python package names must start with letter, so don't check
    def cvt(c):
        if c.isalnum() or c in '-_:.':
            return c
        return '_'
    return ''.join(cvt(c) for c in name)

def print_pkgs(out):
    infos = get_packages_info()
    infos.sort(key=(lambda item: item['name'].casefold()))

    ids = [html4_id(info['name']) for info in infos]
    print('<p>Packages:', file=out)
    sep = ' '
    for info, id in zip(infos, ids):
        print('%s<a href="#%s">%s</a>' % (sep, id, info['name']), end='', file=out)
        sep = ', '
    print('.', file=out)
    print('<dl>', file=out)
    for info, id in zip(infos, ids):
        print('<dt><a href="%s" id="%s" target="_blank">%s</a> version %s' % (
            escape(info['homepage']),
            id,
            escape(info['name']),
            escape(info['version'])), file=out)
        print('<dd>%s<br>' % escape(info['summary']), file=out)
        license = info['license']
        if license:
            lf = info['license-file']
            if not lf:
                print('License type: %s' % escape(license), file=out)
            else:
                fn = 'licenses/%s-%s' % (id, os.path.basename(lf))
                if not os.path.splitext(fn)[1]:
                    fn += '.txt'
                shutil.copyfile(lf, fn)
                print('License type: <a href="%s">%s</a>' % (fn, escape(license)), file=out)
    print('</dl>', file=out)

def ffmpeg_licenses():
    ffmpeg_srcdir = os.path.join('..', 'prereqs', 'ffmpeg')
    makefile = os.path.join(ffmpeg_srcdir, 'Makefile')
    with open(makefile) as f:
        #FFMPEG_VERSION = 3.2.4
        for line in f.readlines():
            if line.startswith('FFMPEG_VERSION = '):
                version = line.split()[2]
                break
        else:
            print('Unable to find ffmpeg version')
            return
    import zipfile
    windist_dir = 'ffmpeg-%s-win64-static' % version
    zip_filename = os.path.join(ffmpeg_srcdir, '%s.zip' % windist_dir)
    with zipfile.ZipFile(zip_filename) as zf:
        out_dir = os.path.join('licenses', 'ffmpeg')
        out_filename = os.path.join(out_dir, 'index.html')
        license_prefix = '%s/licenses/' % windist_dir
        licenses = [n for n in zf.namelist() if n.startswith(license_prefix)]
        licenses.sort()
        zf.extractall(path=out_dir, members=licenses)
        with open(out_filename, 'w') as f:
            print("""<html>
 <head>
  <title> FFmpeg Embedded Licenses </title>
 </head
 <body>
 The FFmpeg binary incorporates some or all of the following libraries and their licenses:
  <ul>
""", file=f)
            for n in licenses:
                bn = os.path.basename(n)
                if not bn:
                    continue
                library = os.path.splitext(bn)[0]
                print('<li> <a href="%s">%s</a>' % (n, library), file=f)
            print("""
  </ul>
 </body>
</html>
""", file=f)


os.makedirs('licenses', exist_ok=True)

with open('embedded.html.in') as src:
    with open('embedded.html', 'w') as out:
        for line in src.readlines():
            if line == 'PYTHON_PKGS\n':
                print_pkgs(out)
            else:
                print(line, end='', file=out)

try:
    ffmpeg_licenses()
except:
    pass

raise SystemExit(0)
