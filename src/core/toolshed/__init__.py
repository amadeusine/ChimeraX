# vim: set expandtab ts=4 sw=4:

"""shed - Chimera 2 Tool Shed

The Tool Shed provides an interface for querying available and
out-of-date packages, and for updating, installing and uninstalling
packages while handling inter-package dependencies.

The '''shed''' interface uses '''distlib''' heavily.
For example, '''Distribution''' instances from '''distlib'''
are tracked for both available and installed packages; the
'''distlib''' '''Locator''' class is used for finding
'''Distribution'''s.

Distribution metadata blocks contain descriptions for tools:
  '''Chimera-Tools''' is a list of name of tools (preferably single words)
      Example: '''Chimera-Tools: MAVOpen MAV'''
  ``Tool-DisplayName`` is the name of a tool for display to user
      Example: '''MAVOpen-Name: 'Open MultAlign Viewer''''
  ``Tool-MenuCategories`` is a list of categories where tool is applicable
      Example: '''MAVOpen-MenuCategories: Sequence'''
  ``Tool-Commands`` is a list of CLI command names provided
      Example: '''MAVOpen-Commands: mav'''

Modules referenced in distribution metadata must define:
  '''register_command(command_name)'''
      Called when delayed command line registration occurs.
  '''start_tool(session, ti, *args, **kw) '''
      Called to create a tool instance.
    ``session`` is a core.Session instance.
    ``ti`` is a toolshed.ToolInfo instance.
"""
def _hack_distlib(f):
    def hacked_f(*args, **kw):
        # distlib and wheel packages disagree on the name for
        # the metadata file in wheels.  (wheel uses PEP345 while
        # distlib uses PEP427.)  distlib is backwards compatible,
        # so we hack the file name when we get distributions.
        from distlib import metadata
        save = metadata.METADATA_FILENAME
        metadata.METADATA_FILENAME = "metadata.json"
        v = f(*args, **kw)
        # Restore hacked name
        metadata.METADATA_FILENAME = save
        return v
    return hacked_f

# Default URL of remote tool shed
_RemoteURL = "http://localhost:8080"
# Default name for toolshed cache and data directories
_ToolShed = "toolshed"

# Defaults names for installed chimera tools
_ChimeraBasePackage = "chimera"
_ChimeraCore = _ChimeraBasePackage + ".core"
_ChimeraToolboxPrefix = _ChimeraBasePackage + ".toolbox"

# Exceptions raised by ToolShed class
class ToolShedError(Exception):
    """Generic ToolShed error."""
class ToolShedUninstalledError(ToolShedError):
    """Uninstalled-tool error."""
class ToolShedInstalledError(ToolShedError):
    """Tool-already-installed error."""
class ToolShedUnavailbleError(ToolShedError):
    """Tool-not-found error."""

class ToolShed:
    """ToolShed keeps track of the list of tool info.

    Tool info may be "installed", where their code
    is already downloaded from the remote shed and installed
    locally, or "available", where their code is not locally
    installed."""

    def __init__(self, logger, appdirs,
            rebuild_cache=False,
            check_remote=False,
            remote_url=None):
        """Initialize shed using data from 'appdirs'.
        
        - ``logger`` is a logging object where warning and
          error messages are sent.
        - ``appdirs`` is an instance of '''appdirs.AppDirs'''
          containing location information about Chimera data 
          and code directories.
        - ``rebuild_cache`` is a boolean indicating whether
          to ignore the local cache of installed tool
          information and rebuild it by scanning Python
          packages.
        - ``check_remote`` is a boolean indicating whether
          to check remote repository for updated information.
          If '''True''', the remote shed is queried;
          if '''False''', the check is not done;
          if '''None''', the check is done according to
          setting in '''preferences'''.
        - ``remote_url`` is a string with the URL of
          the remote toolshed.  If '''None''', a default
          URL is be used."""

        # Initialize with defaults
        _debug("__init__", appdirs, rebuild_cache,
                        check_remote, remote_url)
        if remote_url is None:
            self.remote_url = _RemoteURL
        else:
            self.remote_url = remote_url
        self._repo_locator = None
        self._inst_locator = None
        self._tool_info = []
        self._dist_ti_map = {}
        self._all_installed_distributions = None

        # Compute base directories
        import os.path
        self._cache_dir = os.path.join(appdirs.user_cache_dir, _ToolShed)
        _debug("cache dir: %s" % self._cache_dir)
        self._data_dir = os.path.join(appdirs.user_data_dir, _ToolShed)
        _debug("data dir: %s" % self._data_dir)

        # Add directories to sys.path
        import os.path
        self._site_dir = os.path.join(self._data_dir, "site-packages")
        _debug("site dir: %s" % self._site_dir)
        import os
        os.makedirs(self._site_dir, exist_ok=True)
        import site
        site.addsitedir(self._site_dir)

        # Reload the tool info list
        _debug("loading tools")
        self.reload(logger, check_remote=check_remote,
                    rebuild_cache=rebuild_cache)
        _debug("finished loading tools")

    def check_remote(self, logger):
        """Check remote shed for updated tool info.

        - ``logger`` is a logging object where warning and
          error messages are sent."""

        _debug("check_remote")
        if self._repo_locator is None:
            from .chimera_locator import ChimeraLocator
            self._repo_locator = ChimeraLocator(self._remote_url)
        distributions = self._repo_locator.get_distributions()
        # Replace old remote distribution information with current
        # Do not change self._tool_info unless there are no errors
        tool_info = [ ti for ti in self._tool_info if ti.installed ]
        for d in distributions:
            try:
                tool_info.extend(_make_tool_info(logger,
                                d, False))
                _debug("added remote distribution:", d)
            except _NotToolError:
                _debug("skipped remote distribution:", d)
        return tool_info

    def reload(self, logger, rebuild_cache=False, check_remote=False):
        """Discard and reread tool info.
        
        - ``logger``, ``check_remote`` and ``rebuild_cache``
          have the same meaning as in the constructor."""

        _debug("reload", rebuild_cache, check_remote)
        self._tool_info = []
        self._dist_ti_map = {}
        inst_ti_list = self._load_tool_info(logger,
                        rebuild_cache=rebuild_cache)
        for ti in inst_ti_list:
            self.add_tool_info(ti)
        if check_remote:
            remote_ti_list = self.check_remote(logger)
            for ti in remote_ti_list:
                self._add_tool_info(ti)

    def tool_info(self, installed=True, available=False):
        """Return list of tool info.

        - ``installed`` is a boolean indicating whether installed
          tools should be included in the returned list.
        - ``available`` is a boolean indicating whether available
          but uninstalled tools should be included."""

        _debug("tool_info", installed, available)
        if installed and available:
            return self._tool_info
        elif installed:
            return [ ti for ti in self._tool_info
                            if ti.installed ]
        elif available:
            return [ ti for ti in self._tool_info
                            if not ti.installed ]
        else:
            return []

    def add_tool_info(self, tool_info):
        """Add information for one tool.

        - ``tool_info`` is a constructed instance of '''ToolInfo''',
          i.e., not an instance returned by '''tool_info'''.
        A 'TOOLSHED_TOOL_INFO_ADDED' trigger is fired
        after the addition."""
        _debug("add_tool_info", tool_info)
        self._tool_info.append(tool_info)
        if tool_info._distribution_name is not None:
            self._dist_ti_map[tool_info._distribution_name] = tool_info
        # TODO: fire trigger

    def install_tool(self, tool_info, logger, system=False):
        """Install the tool by retrieving it from the remote shed.

        - ``tool_info`` should be from the available tool list.
          If the tool is already installed, a '''ToolShedError'''
          exception is raised.
        - ``system`` is a boolean that is False if the tool
          is installed for the current user (default), or
          True if installed for everyone.
        - ``logger`` is a logging object where warning and
          error messages are sent.
        A '''TOOLSHED_TOOL_INSTALLED''' trigger is fired
        after installation."""
        _debug("install_tool", tool_info)
        if tool_info.installed:
            raise ToolShedInstalledError(
                        "tool \"%s\" already installed"
                        % tool_info.name)
        self._install_tool(tool_info, system, logger)
        # TODO: implement self._install_tool
        # TODO: fire trigger

    def uninstall_tool(self, tool_info, logger):
        """Uninstall the tool by removing the corresponding
        Python package.

        - ``tool_info`` should be from the installed list.
          If the tool is not installed, a '''ValueError'''
          exception is raised.
        - ``logger`` is a logging object where warning and
          error messages are sent.
        A '''TOOLSHED_TOOL_UNINSTALLED''' trigger is fired
        after package removal."""
        _debug("uninstall_tool", tool_info)
        self._uninstall_tool(tool_info, logger)
        # TODO: fire trigger

    def startup_tools(self, sess):
        _debug("startup_tools")
        # TODO: implement
        return self.tool_info()

    #
    # End public API
    # All methods below are private
    #

    def _load_tool_info(self, logger, rebuild_cache=False):
        # Load tool info.  If not rebuild_cache, try reading
        # it from a cache file.  If we cannot use the cache,
        # read the information from the data directory and
        # try to create the cache file.
        _debug("_load_tool_info", rebuild_cache)
        if not rebuild_cache:
            tool_info = self._read_cache()
            if tool_info is not None:
                return tool_info
        self._scan_installed(logger)
        tool_info = []
        for d in self._inst_tools:
            tool_info.extend(_make_tool_info(logger, d, True))
        # NOTE: need to do something with toolboxes
        self._write_cache(tool_info, logger)
        return tool_info

    @_hack_distlib
    def _scan_installed(self, logger):
        # Scan installed packages for Chimera tools

        # Initialize distlib paths and locators
        _debug("_scan_installed")
        if self._inst_locator is None:
            from distlib.database import DistributionPath
            self._inst_path = DistributionPath()
            from distlib.locators import DistPathLocator
            self._inst_locator = DistPathLocator(self._inst_path)
        _debug("_inst_path", self._inst_path)
        _debug("_inst_locator", self._inst_locator)

        # Keep only wheels

        all_distributions = []
        for d in self._inst_path.get_distributions():
            try:
                d.run_requires
                _debug("_scan_installed distribution", d)
            except:
                continue
            else:
                all_distributions.append(d)

        # Look for core package
        core = self._inst_locator.locate(_ChimeraCore)
        if core is None:
            self._inst_core = set()
            self._inst_tools = set()
            self._inst_toolboxes = set()
            logger.warning("\"%s\" distribution not found"
                            % _ChimeraCore)
            return

        # Partition packages into core, tools and toolboxes
        from distlib.database import make_graph
        dg = make_graph(all_distributions)
        known_dists = set([ core ])
        self._inst_chimera_core = core
        self._inst_core = set([core])
        self._inst_tools = set()
        self._inst_toolboxes = set()
        self._all_installed_distributions = {}
        for d, label in dg.adjacency_list[core]:
            self._inst_core.add(d)
            self._all_installed_distributions[d.name] = d
        check_list = [ core ]
        while check_list:
            dist = check_list.pop()
            _debug("checking", dist)
            for d in dg.reverse_list[dist]:
                if d in known_dists:
                    continue
                known_dists.add(d)
                check_list.append(d)
                name = d.name
                if name.startswith(_ChimeraToolboxPrefix):
                    self._inst_toolboxes.add(d)
                else:
                    self._inst_tools.add(d)
                self._all_installed_distributions[d.name] = d

    def _tool_cache(self, must_exist):
        """Return path to tool cache file."""
        _debug("_tool_cache", must_exist)
        if must_exist:
            import os
            os.makedirs(self._cache_dir, exist_ok=True)
        import os.path
        return os.path.join(self._cache_dir, "tool_info.cache")

    def _read_cache(self):
        """Read installed tool information from cache file.
        
        Returns boolean on whether cache file was read."""
        _debug("_read_cache")
        cache_file = self._tool_cache(False)
        if not self._is_cache_current(cache_file):
            return None
        import shelve, dbm
        try:
            s = shelve.open(cache_file, "r")
        except dbm.error:
            return None
        try:
            tool_info = [ ToolInfo(*args, **kw)
                    for args, kw in s["tool_info"] ]
        except:
            return None
        finally:
            s.close()
        return tool_info

    def _is_cache_current(self, cache_file):
        """Check if cache is up to date."""
        _debug("_is_cache_current")
        import sys, os.path
        try:
            sys_timestamp = os.path.getmtime(os.path.join(sys.prefix, "timestamp"))
            cache_timestamp = os.path.getmtime(cache_file + ".timestamp")
        except FileNotFoundError:
            return False
        # TODO: check against user timestamp as well
        return cache_timestamp > sys_timestamp

    def _write_cache(self, tool_info, logger):
        """Write current tool information to cache file."""
        _debug("_write_cache", tool_info)
        cache_file = self._tool_cache(True)
        import shelve
        try:
            s = shelve.open(cache_file)
        except IOError as e:
            logger.error("\"%s\": %s" % (cache_file, str(e)))
        else:
            try:
                s["tool_info"] = [ ti.cache_data()
                            for ti in tool_info ]
            finally:
                s.close()
        timestamp_file = cache_file + ".timestamp"
        with open(timestamp_file, "w") as f:
            import time
            print(time.ctime(), file=f)
    
    # Following methods are used for installing and removing
    # distributions

    def _install_tool(self, tool_info, system, logger):
        # Install a tool.  This entails:
        #  - finding all distributions that this one depends on
        #  - making sure things will be compatible if installed
        #  - installing all the distributions
        #  - updating any tool installation status
        _debug("_install_tool")
        want_update = []
        need_update = []
        self._install_dist_tool(tool_info, want_update, logger)
        self._install_cascade(want_update, need_update, logger)
        incompatible = self._install_check_incompatible(need_update,
                                logger)
        if incompatible and not always:
            return
        self._install_wheels(need_update, system, logger)
        # update tool installation status
        for dist_name in need_update:
            for ti in self._tool_info:
                if ti._distribution_name == dist_name:
                    ti.installed = True

    def _install_dist_core(self, want, logger):
        # Add Chimera core distribution to update list
        _debug("_install_dist_core")
        d = _install_distribution(_ChimeraCore, logger)
        if d:
            want.append(d)

    def _install_dist_tool(self, tool_info, want, logger):
        # Add the distribution that provides the
        # given tool to update list
        _debug("_install_dist_tool", tool_info)
        if tool_info._distribution_name is None:
            raise ToolShedUnavailableError(
                        "no distribution information "
                        "available for tool \"%s\""
                        % tool_info.name)
        d = _install_distribution(tool_info._distribution_name, logger)
        if d:
            want.append(d)

    def _install_distribution(self, name, logger):
        # Return either a distribution that needs to be
        # installed/updated or None if it is already
        # installed and up-to-date
        _debug("_install_distribution", name)
        repo_dist = self._repo_locator.locate(name)
        if repo_dist is None:
            raise ToolShedUnavailableError(
                        "cannot find new distribution "
                        "named \"%s\"" % name)
        inst_dist = self._inst_locator.locate(name)
        if inst_dist is None:
            return repo_dist
        else:
            from distlib.version import NormalizedVersion as Version
            repo_version = Version(repo_dist.version)
            inst_version = Version(inst_dist.version)
            if inst_version < repo_version:
                return repo_dist
            elif inst_version > repo_version:
                logger.warning("installed \"%s\" is "
                        "newer than latest: %s > %s"
                        % (name, inst_dist.version,
                        repo_dist.version))
        return None

    def _install_cascade(self, want, need, logger):
        # Find all distributions that need to be installed
        # in order for distributions on the ``want`` list to work
        _debug("_install_cascade", want)
        seen = set()
        check = set(want)
        while check:
            d = check.pop()
            seen.add(d)
            need.append(d)
            for req in d.run_requires:
                nd = _install_distribution(req, logger)
                if nd and nd not in seen:
                    check.add(nd)

    def _get_all_installed_distributions(self, logger):
        _debug("_get_all_installed_distributions")
        if self._all_installed_distributions is None:
            self._scan_installed(logger)
        return self._all_installed_distributions

    def _install_check_incompatible(self, need, logger):
        # Make sure everything is compatible (no missing or
        # conflicting distribution requirements)
        _debug("_install_check_incompatible", need)
        all = dict(self._get_all_installed_distributions().items())
        all.update([ (d.name, d) for d in need ])
        from distlib.database import make_graph
        graph = make_graph(all.values())
        if graph.missing:
            for d, req_list in graph.missing:
                if len(req_list) == 1:
                    s = repr(req_list[0])
                else:
                    s = " and ".join(", ".
                        join([ repr(r)
                        for r in req_list[:-1] ]),
                        repr(req_list[-1]))
                logger.warning("\"%s\" needs %s" % (d.name, s))
            return True
        else:
            return False

    def _install_wheels(self, need, system, logger):
        # Find all packages that should be deleted
        _debug("_install_wheels", need, system)
        all = self._get_all_installed_distributions()
        from distlib.database import make_graph
        import itertools
        graph = make_graph(itertools.chain(all.values(), need))
        l = need[:]    # what we started with
        ordered = []    # ordered by least dependency
        depend = {}    # dependency relationship cache
        while l:
            for d in l:
                for d2 in l:
                    if d2 is d:
                        continue
                    try:
                        dep = depend[(d, d2)]
                    except KeyError:
                        dep = _depends_on(graph, d, d2)
                        depend[(d, d2)] = dep
                    if dep:
                        break
                else:
                    ordered.append(d)
                    l.remove(d)
                    break
            else:
                # This can only happen if there is
                # circular dependencies in which case
                # we just process the distributions in
                # given order since its no worse than
                # anything else
                ordered.extend(l)
                break
        remove_list = []
        check = set()
        for d in ordered:
            if d in remove_list:
                continue
            try:
                rd = all[d.name]
            except KeyError:
                pass
            else:
                remove_list.append(rd)
                al = graph.adjacency_list[rd]
                if al:
                    check.update([ sd for sd, l in al ])
        # Repeatedly go through the list of distributions to
        # see whether they can be removed.  It must be iterative.
        # Suppose A and B need to be removed; C depends on A;
        # D depends on B and C; if we check D first, it will not
        # be removable since C is not marked for removal
        # yet; but a second pass will show that D is removable.
        # Iteration ends when no new packages are marked as removable.
        while check:
            any_deletion = False
            new_check = set()
            for d in check:
                for pd in graph.reverse_list[d]:
                    if pd not in remove_list:
                        new_check.add(d)
                        break
                else:
                    any_deletion = True
                    remove_list.append(d)
                    for sd, l in graph.adjacency_list[d]:
                        if (sd not in remove_list
                        and sd not in check):
                            new_check.add(sd)
            if not any_deletion:
                break
            check = new_check

        # If a package is being updated, it should be
        # installed in the same location as before, so we
        # need to keep track.
        old_location = {}
        for d in remove_list:
            old_location[d.name] = _remove_distribution(d, logger)

        # Now we (re)install the needed distributions
        dl = download_location()
        default_paths = _install_make_paths(system)
        from distlib.scripts import ScriptMaker
        maker = ScriptMaker(None, None)
        import os.path
        try:
            from urllib.request import urlretrieve, URLError
        except ImportError:
            from urllib import urlretrieve, URLError
        from distlib.wheel import Wheel
        from distlib import DistlibException
        for d in need:
            try:
                old_site = old_location[d.name]
            except KeyError:
                paths = default_paths
            else:
                paths = _install_make_paths(system, old_site)
            url = d.source_url
            filename = url.split('/')[-1]
            dloc = os.path.join(dl, filename)
            if not os.path.isfile(dloc):
                try:
                    fn, headers = urlretrieve(url, dloc)
                except URLError as e:
                    logger.warning("cannot fetch %s: %s"
                            % (url, str(e)))
                    continue
            w = Wheel(dloc)
            try:
                w.verify()
            except DistlibExecption as e:
                logger.warning("cannot verify %s: %s"
                        % (d.name, str(e)))
                continue
            logger.info("installing %s (%s)" % (w.name, w.version))
            w.install(paths, maker)

    def _install_make_paths(self, system, sitepackages=None):
        # Create path associated with either only-this-user
        # or system distributions
        _debug("_install_make_paths", system)
        import site, sys, os.path
        if system:
            base = sys.prefix
        else:
            base = self._data_dir
        if sitepackages is None:
            if system:
                sitepackages = site.getsitepackages()[-1]
            else:
                sitepackages = self._site_dir
        paths = {
            "prefix": sys.prefix,
            "purelib": sitepackages,
            "platlib": sitepackages,
            "headers": os.path.join(base, "include"),
            "scripts": os.path.join(base, "bin"),
            "data": os.path.join(base, "lib"),
        }
        return paths

    def _depends_on(self, graph, da, db):
        # Returns whether distribution "da" depends on "db"
        # "graph" is a distlib.depgraph.DependencyGraph instance
        # Do depth-first search
        for depa, label in graph.adjacency_list[da]:
            if depa is db or _depends_on(graph, depa, db):
                return True
        return False

    def _remove_distribution(self, d, logger):
        _debug("_remove_distribution", d)
        from distlib.database import InstalledDistribution
        if not isinstance(d, InstalledDistribution):
            raise ToolShedUninstalledError("trying to remove "
                    "uninstalled distribution: %s (%s)"
                    % (d.name, d.version))
        # HACK ALERT: since there is no API for uninstalling
        # a distribution (as of distlib 0.1.9), here's my hack:
        #   assume that d.list_installed_files() returns paths
        #     relative to undocumented dirname(d.path)
        #   remove all listed installed files while keeping track of
        #     directories from which we removed files
        #   try removing the directories, longest first (this will
        #     remove children directories before parents)
        import os.path
        basedir = os.path.dirname(d.path)
        dircache = set()
        try:
            for path, hash, size in d.list_installed_files():
                p = os.path.join(basedir, path)
                os.remove(p)
                dircache.add(os.path.dirname(p))
        except OSError as e:
            logger.warning("cannot remove distribution: %s" % str(e))
            return basedir
        try:
            # Do not try to remove the base directory (probably
            # "site-packages somewhere)
            dircache.remove(basedir)
        except KeyError:
            pass
        for d in reversed(sorted(dircache, key=len)):
            try:
                os.rmdir(d)
            except OSError as e:
                # If directory not empty, just ignore
                pass
        return basedir

    # End methods for installing and removing distributions

class ToolInfo:
    """ToolInfo manages how to create an ToolInstance.

    An ToolInfo knows about the properties about a class
    of tools and can create an tool instance."""

    def __init__(self, name, installed,
                distribution_name=None,
                display_name=None,
                module_name=None,
                menu_categories=(),
                command_names=()):
        """Initialize tool info named 'name'.

        Supported keywords include:
        - ``distribution_name``: name of distribution that
          provided this tool (string)
        - ``display_name``: name to display in user interface
          for this tool (string)
        - ``module_name``: Name of module implementing the tool.
          Must be a dotted Python name.  (See module doc string.)
        - ``menu_categories``: list of categories (strings)
          in which tool belongs
        - ``command_names``: list of names of command (strings) in CLI
        """

        # Public attributes
        self.name = name
        self.installed = installed
        self.display_name = display_name
        self.menu_categories = menu_categories

        # Private attributes
        self._distribution_name = distribution_name
        self._module_name = module_name
        self._command_names = command_names

        from chimera.core import cli
        _debug("command_names", command_names)
        for command_name in command_names:
            def cb(s=self, n=command_name):
                s._register_cmd(n)
            cli.delay_registration(command_name, cb)

    def cache_data(self):
        # Return two tuple of (args, kw) that can be used
        # to recreate with ToolInfo(*args, **kw)
        args = (self.name, self.installed)
        kw = {
            "display_name": self.display_name,
            "menu_categories": self.menu_categories,
            "distribution_name": self._distribution_name,
            "module_name": self._module_name,
            "command_names": self._command_names,
        }
        return args, kw

    def _register_cmd(self, command_name):
        """Called when commands need to be really registered."""
        self._get_module().register_command(command_name)

    def _get_module(self):
        """Return module for this tool."""
        if not self._module_name:
            raise ToolShedError("no module specified for "
                        "tool \"%s\""
                        % self.name)
        import importlib
        m = importlib.import_module(self._module_name)
        _debug("_get_module", self._module_name, m)
        return m

    def start(self, session, *args, **kw):
        """Create and return an tool instance.

        ``session`` is a Session instance in which the tool will run.
        ``args`` and 'kw' are passed as positional and keyword
        arguments to the ToolInstance constructor.
        
        If the tool is not installed,
        '''ToolShedUninstalledError''' is raised.
        If the tool cannot be started,
        '''ToolShedError''' is raised."""
        if not self.installed:
            raise ToolShedUninstalledError("tool \"%s\" is "
                            "not installed"
                            % self.name)
        try:
            return self._get_module().start_tool(session, self,
                                *args, **kw)
        except (ImportError, AttributeError, TypeError):
            raise ToolShedError("bad start callable specified "
                        "for tool \"%s\"" % self.name)

from .. import session
class ToolInstance(session.State):
    """ToolInstance is the abstract base class for 
    tool instance classes that implement actual functionality,
    in particular the '''session.State''' API.

    All session-related data are stored in ToolInstance instances,
    not in any ToolShed or ToolInfo instances."""

    def __init__(self, session, *args, **kw):
        """Initialize an ToolInstance.

        Supported keyword include:
        - ``session_data``: data read from session file; if present,
          this data overrides information from all other arguments
        """

#
# Code in remainder of file are for internal use only
#

class _NotToolError(Exception):
    pass

def _make_tool_info(logger, d, installed):
    name = d.name
    version = d.version
    md = d.metadata

    tools = []
    for classifier in md.dictionary["classifiers"]:
        parts = [ v.strip() for v in classifier.split("::") ]
        if parts[0] != "Chimera-Tool":
            continue
        kw = { "distribution_name": name }
        try:
            # Name of tool
            tool_name = parts[1]
        except IndexError:
            logger.error("no name specified for Chimera tool")
            # No module means there is no way to start
            # this tool, so we do not even treat it as a tool
            continue
        try:
            # Name of module implementing tool
            kw["module_name"] = parts[2]
        except IndexError:
            logger.error("no module specified for \"%s\"" % tool_name)
            # No module means there is no way to start
            # this tool, so we do not even treat it as a tool
            continue
        try:
            # Display name of tool
            kw["display_name"] = parts[3]
        except IndexError:
            pass
        try:
            # CLI command names (just the first word)
            commands = parts[4]
            if commands:
                kw["command_names"] = [ v.strip()
                        for v in commands.split(',') ]
        except IndexError:
            pass
        try:
            # Menu categories in which tool should appear
            categories = parts[5]
            if categories:
                kw["menu_categories"] = [ v.strip()
                        for v in categories.split(',') ]
        except IndexError:
            pass
        tools.append(ToolInfo(tool_name, installed, **kw))
    return tools

def init(*args, debug=False, **kw):
    """Initialize toolshed.

    This function accepts all the arguments for the ``Toolshed``
    initializer.  In addition:

    - ``debug`` is a boolean value.  If true, debugging messages
      are sent to standard output.  Default value is false."""
    global _debug
    if debug:
        def _debug(*args, **kw):
            import sys
            print("Toolshed:", *args, file=sys.stderr, **kw)
    else:
        def _debug(*args, **kw):
            return
    return ToolShed(*args, **kw)
