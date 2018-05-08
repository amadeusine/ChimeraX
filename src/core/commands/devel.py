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

from . import CmdDesc, StringArg, OpenFolderNameArg, BoolArg

_aliases = {}


def devel_alias(session, name=None, path=None):
    '''Define an alias for a folder for use in other "devel" commands.

    Parameters
    ----------
    name : string
      Alias for bundle path.
    path : string
      Path to folder containing bundle source code.
    '''
    logger = session.logger

    def show_alias(name, path):
        logger.info("%s defined as %s" % (repr(name), repr(path)))

    if name is None:
        # No arguments, list all aliases
        if not _aliases:
            logger.info("No bundle aliases have been defined.")
        else:
            for name in sorted(_aliases.keys()):
                show_alias(name, _aliases[name])
        return
    elif path is None:
        # Name but no path, list alias for name
        try:
            path = _aliases[name]
        except KeyError:
            logger.info("No bundle alias %s has been defined." % repr(name))
        else:
            show_alias(name, path)
        return
    else:
        # Both name and path given, define/replace alias
        _aliases[name] = path
        show_alias(name, path)


devel_alias_desc = CmdDesc(optional=[("name", StringArg),
                                     ("path", OpenFolderNameArg)],
                           synopsis='Define alias for bundle path')


def devel_unalias(session, name):
    '''Remove a bundle alias.

    Parameters
    ----------
    name : string
      Alias for bundle path.
    '''
    logger = session.logger
    try:
        del _aliases[name]
    except KeyError:
        logger.info("No bundle alias %s has been defined." % repr(name))
    else:
        logger.info("Alias %s has been removed." % repr(name))


devel_unalias_desc = CmdDesc(required=[("name", StringArg)],
                             synopsis='Remove alias for bundle path')


def devel_build(session, path, test=True, debug=False, exit=False):
    '''Build a wheel in for the source code in bundle path.

    Parameters
    ----------
    path : string
      Path to folder containing bundle source code or bundle alias.
    test : bool
      Whether to run test after building wheel
    '''
    from ...bundle_builder import BundleBuilder
    _run(path, session.logger, exit, BundleBuilder.make_wheel, test=test, debug=debug)


devel_build_desc = CmdDesc(required=[("path", OpenFolderNameArg)],
                           optional=[("test", BoolArg),
                                     ("debug", BoolArg),
                                     ("exit", BoolArg)],
                           synopsis='Build a wheel for bundle')


def devel_install(session, path, test=True, user=None, debug=False, exit=False):
    '''Build and install a wheel in for the source code in bundle path.

    Parameters
    ----------
    path : string
      Path to folder containing bundle source code or bundle alias.
    test : bool
      Whether to run test after building wheel
    '''
    from ...bundle_builder import BundleBuilder
    _run(path, session.logger, exit, BundleBuilder.make_install,
         session, test=test, debug=debug, user=user)


devel_install_desc = CmdDesc(required=[("path", OpenFolderNameArg)],
                             optional=[("test", BoolArg),
                                       ("debug", BoolArg),
                                       ("user", BoolArg),
                                       ("exit", BoolArg)],
                             synopsis='Build and install wheel for bundle')


def devel_clean(session, path, exit=False):
    '''Remove build files from the source code in bundle path.

    Parameters
    ----------
    path : string
      Path to folder containing bundle source code or bundle alias.
    '''
    from ...bundle_builder import BundleBuilder
    _run(path, session.logger, exit, BundleBuilder.make_clean)


devel_clean_desc = CmdDesc(required=[("path", OpenFolderNameArg)],
                           optional=[("exit", BoolArg)],
                           synopsis='Remove build files from bundle path')


def _run(path, logger, exit, unbound_method, *args, **kw):
    from ..logger import StringPlainTextLog
    bb = _get_builder(path, logger)
    exit_status = 0
    if bb is not None:
        with StringPlainTextLog(logger) as log:
            try:
                unbound_method(bb, *args, **kw)
            except:
                import traceback
                logger.error(traceback.format_exc())
                exit_status = 1
            output = log.getvalue()
        logger.info(output)
    else:
        exit_status = 1
    if exit:
        raise SystemExit(exit_status)
    return exit_status


def devel_dump(session, path):
    '''Dump the bundle information for the source code in bundle path.

    Parameters
    ----------
    path : string
      Path to folder containing bundle source code or bundle alias.
    '''
    bb = _get_builder(path, session.logger)
    if bb is not None:
        bb.dump()


devel_dump_desc = CmdDesc(required=[("path", OpenFolderNameArg)],
                          synopsis='Dump bundle information in bundle path')


def _get_builder(path, logger):
    """Return BundleBuilder instance or None."""
    from ...bundle_builder import BundleBuilder
    try:
        path = _aliases[path]
    except KeyError:
        pass
    try:
        bb = BundleBuilder(logger, bundle_path=path)
    except IOError as e:
        logger.error(str(e))
        return None
    except ValueError as e:
        logger.error("%s: %s" % (path, str(e)))
        return None
    else:
        return bb


def register_command(session):
    from . import register

    register("devel alias", devel_alias_desc, devel_alias,
             logger=session.logger)
    register("devel unalias", devel_unalias_desc, devel_unalias,
             logger=session.logger)
    register("devel build", devel_build_desc, devel_build,
             logger=session.logger)
    register("devel install", devel_install_desc, devel_install,
             logger=session.logger)
    register("devel clean", devel_clean_desc, devel_clean,
             logger=session.logger)
    register("devel dump", devel_dump_desc, devel_dump,
             logger=session.logger)
