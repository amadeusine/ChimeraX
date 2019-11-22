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


from . import _debug
from . import _TIMESTAMP
from . import ToolshedError


class InstalledBundleCache(list):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._help_directories = None

    def load(self, logger, cache_file=None, rebuild_cache=False, write_cache=True):
        """Load list of installed bundles.

        Bundles are ordered based on dependency with dependent
        bundles appearing later in the list."""

        #
        # Load bundle info.  If not rebuild_cache, try reading
        # it from a cache file.  If we cannot use the cache,
        # read the information from the data directory and
        # try to create the cache file.
        #
        _debug("InstalledBundleCache.load: rebuild_cache", rebuild_cache)
        if cache_file and not rebuild_cache:
            if self._read_cache(cache_file):
                _debug("InstalledBundleCache.load: using cached data")
                return
        #
        # Okay, no cache.  Go through all installed packages
        # and look for ChimeraX bundles
        #
        _debug("InstalledBundleCache.load: rebuilding cache")
        from pkg_resources import WorkingSet
        dist_bundle_map = {}
        for d in WorkingSet():
            _debug("InstalledBundleCache.load: package %s" % d)
            bi = _make_bundle_info(d, True, logger)
            if bi is not None:
                _debug("InstalledBundleCache.load: bundle %s" % bi)
                dist_bundle_map[d] = bi
        #
        # The ordering of the bundles is important because we want
        # to call the initialize() method in the correct order.
        #
        self.extend(self._order_bundles(dist_bundle_map, logger))

        #
        # Save all our hard work
        #
        if cache_file and write_cache:
            _debug("InstalledBundleCache.load: write_cache")
            self._write_cache(cache_file, logger)

    def register_all(self, logger, session, package_map):
        """Register all installed bundles.

        Returns dictionary of package name to bundle instance."""

        for bi in self:
            for p in bi.packages:
                package_map[p] = bi
            bi.register(logger)
            if session is not None:
                bi.initialize(session)
        return package_map

    def deregister_all(self, logger, session, package_map):
        """Deregister all installed bundles."""

        for bi in reversed(self):
            for p in bi.packages:
                try:
                    del package_map[p]
                except KeyError:
                    pass
            if session is not None:
                bi.finish(session)
            bi.deregister(logger)

    def set_install_timestamp(self, per_user=False):
        """Set last installed timestamp."""

        import os
        if per_user:
            from chimerax import app_dirs
            directory = app_dirs.user_data_dir
        else:
            from chimerax import app_data_dir as directory
        timestamp_file = os.path.join(directory, _TIMESTAMP)
        with open(timestamp_file, 'w') as f:
            # Contents of file are never read, see _is_cache_newer()
            import time
            print(time.ctime(), file=f)

    #
    # Methods below are internal
    #
    def _read_cache(self, cache_file):
        """Read installed bundle information from cache file.

        Returns boolean on whether cache file was read."""
        _debug("InstalledBundleCache._read_cache:", cache_file)
        import os.path
        if not os.path.exists(cache_file):
            return False
        import filelock, json, os, sys
        from .info import BundleInfo
        try:
            lock_file = cache_file + '.lock'
            lock = filelock.FileLock(lock_file)
            with lock.acquire():
                if not lock.is_locked:
                    # As of filelock==2.0.8:
                    # On Unix, failing to create the lock file results
                    # in an exception, but on Windows the acquire fails
                    # silently but leaves the lock unlocked
                    raise OSError("cannot create lock file %r" % lock_file)
                f = open(cache_file, "r", encoding='utf-8')
                try:
                    with f:
                        data = f.readline()
                        data = json.loads(data)
                        if not isinstance(data[0], str):
                            _debug("InstalledBundleCache._read_cache: obsolete cache")
                            return None  # obsolete cache format
                        executable, mtime = data
                        if executable != sys.executable:
                            _debug("InstalledBundleCache._read_cache: different executable")
                            return None
                        if mtime != os.path.getmtime(executable):
                            _debug("InstalledBundleCache._read_cache: changed executable")
                            return None
                        if not self._is_cache_newer(cache_file):
                            return None
                        data = json.load(f)
                    self.extend([BundleInfo.from_cache_data(x) for x in data])
                    _debug("InstalledBundleCache._read_cache: %d bundles" % len(self))
                    return True
                except Exception as e:
                    _debug("InstalledBundleCache._read_cache: failed:", e)
                    return False
        except OSError as e:
            _debug("InstalledBundleCache._read_cache: failed os:", str(e))
            return False

    def _is_cache_newer(self, cache_file):
        """Check if cache is newer than timestamps."""
        _debug("_is_cache_newer")
        from chimerax import app_dirs, app_data_dir
        import os
        files = (
            (os.path.join(app_data_dir, _TIMESTAMP), True),
            (os.path.join(app_dirs.user_data_dir, _TIMESTAMP), False),
        )
        try:
            cache_time = os.path.getmtime(cache_file)
        except FileNotFoundError:
            return False
        for filename, required in files:
            try:
                time = os.path.getmtime(filename)
                if time > cache_time:
                    return False
            except FileNotFoundError:
                if required:
                    return False
        return True

    def _write_cache(self, cache_file, logger):
        """Write current bundle information to cache file."""
        _debug("InstalledBundleCache._write_cache", cache_file)
        import os, os.path, filelock, json, sys
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        lock = filelock.FileLock(cache_file + '.lock')
        with lock.acquire():
            try:
                f = open(cache_file, 'w', encoding='utf-8')
            except IOError as e:
                logger.error("\"%s\": %s" % (cache_file, str(e)))
            else:
                with f:
                    data = [sys.executable, os.path.getmtime(sys.executable)]
                    json.dump(data, f, ensure_ascii=False)
                    print(file=f)
                    json.dump([bi.cache_data() for bi in self], f,
                              ensure_ascii=False, check_circular=False)

    @property
    def help_directories(self):
        if self._help_directories is None:
            hd = []
            for bi in self:
                try:
                    help_dir = bi.get_path('docs')
                except ToolshedError:
                    # ignore bundles that disappeared
                    continue
                if help_dir is not None:
                    hd.append(help_dir)
            self._help_directories = hd
        return self._help_directories

    def _order_bundles(self, dist_bundle_map, logger):
        # First we build a list of distribution names that
        # map to bundles.  This is so we can ignore dependencies
        # that are not bundles.
        dist_names = set([d.project_name for d in dist_bundle_map.keys()])
        # Then we build a dependency map where the key is a
        # distribution instance and the value is a list of
        # bundle distribution names that it depends on.
        # Non-bundle distributions are dropped here.
        dist_needs = {}
        for d in dist_bundle_map.keys():
            dist_needs[d] = needs = []
            for r in d.requires():
                if r.project_name in dist_names:
                    needs.append(r.key)
        # Now we start with all bundle distributions in the
        # "to_be_done" list and nothing in the "ready" list.
        # We then repeatedly move all to_be_done distributions
        # whose dependencies are all on the ready list
        # over to the ready list.  We are done when the
        # to_be_done list is empty or we could not move
        # any distributions (probably from circular dependency).
        ready = []
        seen = set()
        to_be_done = set(dist_bundle_map.keys())
        while to_be_done:
            can_move = []
            for d in to_be_done:
                for req in dist_needs[d]:
                    if req not in seen:
                        break
                else:
                    can_move.append(d)
            if can_move:
                ready.extend(can_move)
                to_be_done.difference_update(can_move)
                seen.update([d.key for d in can_move])
            else:
                logger.warning("Unexpected circular dependencies:",
                               ', '.join([str(d) for d in to_be_done]))
                ready.extend(to_be_done)
                to_be_done.clear()
        return [dist_bundle_map[d] for d in ready]


#
# Class-independent utility functions available to other modules in package
#


def _extract_extra_keywords(kwds):
    result = {}
    if isinstance(kwds, str):
        kwds = [k.strip() for k in kwds.split(',')]
    for k in kwds:
        temp = [t.strip() for t in k.split(':', maxsplit=2)]
        if len(temp) == 1:
            result[temp[0]] = ('no description', 'String')
        if len(temp) == 2:
            result[temp[0]] = ('no description', temp[1])
        else:
            print(temp)
            result[temp[0]] = (temp[1], temp[2])
    return result


def _report_difference(logger, before, after):
    bundles = {}
    for bi in before:
        bundles[bi.name] = [bi.version, None]
    for bi in after:
        try:
            versions = bundles[bi.name]
        except KeyError:
            bundles[bi.name] = [None, bi.version]
        else:
            versions[1] = bi.version
    changes = {}
    def add_change(kind, name, version):
        try:
            d = changes[kind]
        except KeyError:
            d = changes[kind] = {}
        d[name] = version
    messages = []
    for name in sorted(bundles.keys()):
        versions = bundles[name]
        if versions[0] is None:
            messages.append("Installed %s (%s)" % (name, versions[1]))
            add_change("installed", name, versions[1])
        elif versions[1] is None:
            messages.append("Removed %s (%s)" % (name, versions[0]))
            add_change("removed", name, versions[0])
        elif versions[0] != versions[1]:
            messages.append("Updated %s (from %s to %s)"
                            % (name, versions[0], versions[1]))
            add_change("updated", name, versions[1])
    if messages:
        logger.info('\n'.join(messages))
    else:
        logger.info("No change in list of installed bundles")
    return changes


#
# Class-independent utility functions only used in this module
#


def _make_bundle_info(d, installed, logger):
    """Convert distribution into a list of :py:class:`BundleInfo` instances."""
    from .info import BundleInfo, ToolInfo, CommandInfo, SelectorInfo, FormatInfo
    from ..commands import unescape
    import pkginfo
    name = d.project_name
    if not name[0].isalpha():
        # pip uninstall renames package ChimeraX-XXX to ~himeraX-XXX,
        # which we somehow translate to -himeraX-XXX.
        return None
    version = d.version
    metadata_file = "METADATA"
    if not d.has_metadata(metadata_file):
        _debug("InstalledBundleCache._make_bundle_info: "
               "no metadata in %s" % d)
        return None
    md = pkginfo.Distribution()
    md.parse(d.get_metadata(metadata_file))
    if not md.classifiers:
        _debug("InstalledBundleCache._make_bundle_info: "
               "no classifiers in %s" % d)
        return None

    bi = None
    kw = {"name": name, "version": version}
    try:
        kw['synopsis'] = md.summary
    except KeyError:
        _debug("InstalledBundleCache._make_bundle_info: no summary in %s" % d)
        return None
    kw['packages'] = _get_installed_packages(d, logger)
    for classifier in md.classifiers:
        parts = [v.strip() for v in classifier.split(" ::")]
        if parts[0] != 'ChimeraX':
            continue
        if parts[1] == 'Bundle':
            # ChimeraX :: Bundle :: categories :: session_versions :: module_name :: supercedes :: custom_init
            if bi is not None:
                logger.warning("Second ChimeraX :: Bundle line ignored.")
                break
            elif len(parts) != 7:
                logger.warning("Malformed ChimeraX :: Bundle line in %s skipped." % name)
                logger.warning("Expected 7 fields and got %d." % len(parts))
                continue
            categories, session_versions, module_name, supercedes, custom_init = parts[2:]
            kw["categories"] = [v.strip() for v in categories.split(',')]
            if session_versions:
                vs = [v.strip() for v in session_versions.split(',')]
                if len(vs) != 2:
                    logger.warning("Malformed ChimeraX :: Bundle line in %s skipped." % name)
                    logger.warning("Expected 2 version numbers and got %d." % len(vs))
                    continue
                try:
                    lo = int(vs[0])
                    hi = int(vs[1])
                except ValueError:
                    logger.warning("Malformed ChimeraX :: Bundle line in %s skipped." % name)
                    logger.warning("Found non-integer version numbers.")
                    continue
                if lo > hi:
                    logger.warning("Minimum version is greater than maximium.")
                    hi = lo
                kw["session_versions"] = range(lo, hi + 1)
            kw["api_package_name"] = module_name
            if supercedes:
                kw['supercedes'] = [v.strip() for v in supercedes.split(',')]
            if custom_init:
                kw["custom_init"] = (custom_init == "true")
            bi = BundleInfo(installed=installed, **kw)
            # Do we really need this?
            # bi.path = d.path
        elif parts[1] == 'Tool':
            # ChimeraX :: Tool :: tool_name :: categories :: synopsis
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) != 5:
                logger.warning("Malformed ChimeraX :: Tool line in %s skipped." % name)
                logger.warning("Expected 5 fields and got %d." % len(parts))
                continue
            # Menu categories in which tool should appear
            name, categories, synopsis = parts[2:]
            if not categories:
                logger.warning("Missing tool categories")
                continue
            categories = [v.strip() for v in categories.split(',')]
            ti = ToolInfo(name, categories, synopsis)
            bi.tools.append(ti)
        elif parts[1] == 'Command':
            # ChimeraX :: Command :: name :: categories :: synopsis
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) != 5:
                logger.warning("Malformed ChimeraX :: Command line in %s skipped." % name)
                logger.warning("Expected 5 fields and got %d." % len(parts))
                continue
            name, categories, synopsis = parts[2:]
            if not categories:
                logger.warning("Missing command categories")
                continue
            categories = [v.strip() for v in categories.split(',')]
            ci = CommandInfo(name, categories, synopsis)
            bi.commands.append(ci)
        elif parts[1] == 'Selector':
            # ChimeraX :: Selector :: name :: synopsis
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) != 4 and len(parts) != 5:
                logger.warning("Malformed ChimeraX :: Selector line in %s skipped." % name)
                logger.warning("Expected 4 or 5 fields and got %d." % len(parts))
                continue
            name = parts[2]
            synopsis = parts[3]
            if len(parts) == 5:
                atomic = parts[4].lower() != "false"
            else:
                atomic = True
            si = SelectorInfo(name, synopsis, atomic)
            bi.selectors.append(si)
        elif parts[1] == 'DataFormat':
            # ChimeraX :: DataFormat :: format_name :: nicknames :: category :: suffixes :: mime_types :: url :: dangerous :: icon :: synopsis :: encoding
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) not in [11, 12]:
                logger.warning("Malformed ChimeraX :: DataFormat line in %s skipped." % name)
                logger.warning("Expected 11 or 12 fields and got %d." % len(parts))
                continue
            if len(parts) == 12:
                name, nicknames, category, suffixes, mime_types, url, dangerous, icon, synopsis, encoding = parts[2:]
            else:
                encoding = None
                name, nicknames, category, suffixes, mime_types, url, dangerous, icon, synopsis = parts[2:]
            if not synopsis:
                logger.warning("Missing synopsis for %s data format" % name)
                synopsis = name
            nicknames = [v.strip() for v in nicknames.split(',')] if nicknames else None
            suffixes = [v.strip() for v in suffixes.split(',')] if suffixes else None
            mime_types = [v.strip() for v in mime_types.split(',')] if mime_types else None
            # construct absolute path name of icon by looking
            # in package directory
            if icon:
                icon = bi.get_path(icon)
            fi = FormatInfo(name=name, nicknames=nicknames,
                            category=category, suffixes=suffixes,
                            mime_types=mime_types, url=url, icon=icon,
                            dangerous=dangerous, synopsis=synopsis,
                            encoding=encoding)
            bi.formats.append(fi)
        elif parts[1] == 'Fetch':
            # ChimeraX :: Fetch :: database_name :: format_name :: prefixes :: example_id :: is_default
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) != 7:
                logger.warning("Malformed ChimeraX :: Fetch line in %s skipped." % name)
                logger.warning("Expected 7 fields and got %d." % len(parts))
                continue
            database_name, format_name, prefixes, example_id, is_default = parts[2:]
            prefixes = [v.strip() for v in prefixes.split(',')] if prefixes else ()
            is_default = (is_default == 'true')
            bi.fetches.append((database_name, format_name, prefixes, example_id, is_default))
        elif parts[1] == 'Open':
            # ChimeraX :: Open :: format_name :: tag :: is_default :: keyword_arguments
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) not in [5, 6]:
                logger.warning("Malformed ChimeraX :: Open line in %s skipped." % name)
                logger.warning("Expected 5 or 6 fields and got %d." % len(parts))
                continue
            if len(parts) == 6:
                name, tag, is_default, kwds = parts[2:]
                kwds = _extract_extra_keywords(kwds)
            else:
                name, tag, is_default = parts[2:]
                kwds = None
            is_default = (is_default == 'true')
            try:
                fi = [fi for fi in bi.formats if fi.name == name][0]
            except (KeyError, IndexError):
                logger.warning("Unknown format name: %r." % name)
                continue
            fi.has_open = True
            fi.open_kwds = kwds
        elif parts[1] == 'Save':
            # ChimeraX :: Save :: format_name :: tag :: is_default :: keyword_arguments
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) not in [5, 6]:
                logger.warning("Malformed ChimeraX :: Save line in %s skipped." % name)
                logger.warning("Expected 5 or 6 fields and got %d." % len(parts))
                continue
            if len(parts) == 6:
                name, tag, is_default, kwds = parts[2:]
                kwds = _extract_extra_keywords(kwds)
            else:
                name, tag, is_default = parts[2:]
                kwds = None
            is_default = (is_default == 'true')
            try:
                fi = [fi for fi in bi.formats if fi.name == name][0]
            except (KeyError, IndexError):
                logger.warning("Unknown format name: %r." % name)
                continue
            fi.has_save = True
            fi.save_kwds = kwds
        elif parts[1] == 'DataDir':
            bi.installed_data_dir = parts[2]
        elif parts[1] == 'IncludeDir':
            bi.installed_include_dir = parts[2]
        elif parts[1] == 'LibraryDir':
            bi.installed_library_dir = parts[2]
        elif parts[1] == 'ExecutableDir':
            bi.installed_executable_dir = parts[2]
        elif parts[1] == 'Manager':
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) < 3:
                logger.warning("Malformed ChimeraX :: Manager line in %s skipped." % name)
                logger.warning("Expected at least three fields and got %d." % len(parts))
                continue
            name = parts[2]
            kw = {}
            for p in parts[3:]:
                k, v = p.split(':', 1)
                if v[0] in '\'"':
                    v = unescape(v[1:-1])
                else:
                    v = unescape(v)
                kw[k] = v
            bi.managers[name] = kw
        elif parts[1] == 'Provider':
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) < 4:
                logger.warning("Malformed ChimeraX :: Provider line in %s skipped." % name)
                logger.warning("Expected at least four fields and got %d." % len(parts))
                continue
            name = parts[2]
            mgr = parts[3]
            kw = {}
            for p in parts[4:]:
                k, v = p.split(':', 1)
                if v[0] in '\'"':
                    v = unescape(v[1:-1])
                else:
                    v = unescape(v)
                kw[k] = v
            bi.providers[name] = (mgr, kw)
        elif parts[1] == 'InitAfter':
            if bi is None:
                logger.warning('ChimeraX :: Bundle entry must be first')
                return None
            if len(parts) < 4:
                logger.warning("Malformed ChimeraX :: InitAfter line in %s skipped." % name)
                logger.warning("Expected at least four fields and got %d." % len(parts))
                continue
            name = parts[2]
            bi.inits[name] = parts[3:]
    if bi is None:
        _debug("InstalledBundleCache._make_bundle_info: no ChimeraX bundle in %s" % d)
        return None
    try:
        description = md.description
        if description.startswith("UNKNOWN"):
            description = "Missing bundle description"
        bi.description = description
    except (KeyError, OSError):
        pass

    return bi


def _get_installed_packages(d, logger):
    """Return set of tuples representing the packages in the distribution.

    For example, 'foo.bar' from foo/bar/__init__.py becomes ('foo', 'bar')
    """
    record_file = "RECORD"
    if not d.has_metadata(record_file):
        logger.warning("cannot get installed file list for %r" % d.project_name)
        return []
    packages = []
    for line in d.get_metadata_lines(record_file):
        path, hash, size = line.split(',')
        if not path.endswith('/__init__.py'):
            continue
        parts = path.split('/')
        packages.append(tuple(parts[:-1]))
    return packages
