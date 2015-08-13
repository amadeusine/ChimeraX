# vi: set expandtab ts=4 sw=4:

from chimera.core.commands import EnumOf, CmdDesc, StringArg, BoolArg

_tool_types = EnumOf(["all", "installed", "available"])


def _display_tools(ti_list, logger):
    for ti in ti_list:
        logger.info(" %s (%s %s): %s" % (ti.display_name, ti.name,
                                         ti.version, ti.synopsis))


def ts_list(session, tool_type="installed"):
    ts = session.toolshed
    logger = session.logger
    if tool_type == "installed" or tool_type == "all":
        ti_list = ts.tool_info(installed=True, available=False)
        if ti_list:
            logger.info("List of installed tools:")
            _display_tools(ti_list, logger)
        else:
            logger.info("No installed tools found.")
    if tool_type == "available" or tool_type == "all":
        ti_list = ts.tool_info(installed=False, available=True)
        if ti_list:
            logger.info("List of available tools:")
            _display_tools(ti_list, logger)
        else:
            logger.info("No available tools found.")
ts_list_desc = CmdDesc(optional=[("tool_type", _tool_types)])


def ts_refresh(session, tool_type="installed"):
    ts = session.toolshed
    logger = session.logger
    if tool_type == "installed":
        ts.reload(logger, rebuild_cache=True, check_remote=False)
    elif tool_type == "available":
        ts.reload(logger, rebuild_cache=False, check_remote=True)
    elif tool_type == "all":
        ts.reload(logger, rebuild_cache=True, check_remote=True)
ts_refresh_desc = CmdDesc(optional=[("tool_type", _tool_types)])


def _tool_string(tool_name, version):
    if version is None:
        return tool_name
    else:
        return "%s (%s)" % (tool_name, version)


def ts_install(session, tool_name, user_only=True, version=None):
    ts = session.toolshed
    logger = session.logger
    ti = ts.find_tool(tool_name, installed=True, version=version)
    if ti:
        logger.error("\"%s\" is already installed" % tool_name)
        return
    ti = ts.find_tool(tool_name, installed=False, version=version)
    if ti is None:
        logger.error("\"%s\" does not match any tools"
                     % _tool_string(tool_name, version))
        return
    ts.install_tool(ti, logger, not user_only)
ts_install_desc = CmdDesc(required=[("tool_name", StringArg)],
                          optional=[("user_only", BoolArg),
                                    ("version", StringArg)])


def ts_remove(session, tool_name):
    ts = session.toolshed
    logger = session.logger
    ti = ts.find_tool(tool_name, installed=True)
    if ti is None:
        logger.error("\"%s\" does not match any tools" % tool_name)
        return
    ts.uninstall_tool(ti, logger)
ts_remove_desc = CmdDesc(required=[("tool_name", StringArg)])


def ts_start(session, tool_name, *args, **kw):
    ts = session.toolshed
    logger = session.logger
    ti = ts.find_tool(tool_name, installed=True)
    if ti is None:
        logger.error("\"%s\" does not match any tools" % tool_name)
        return
    ti.start(session, *args, **kw)
ts_start_desc = CmdDesc(required=[("tool_name", StringArg)])


def ts_update(session, tool_name, version=None):
    ts = session.toolshed
    logger = session.logger
    new_ti = ts.find_tool(tool_name, installed=False, version=version)
    if new_ti is None:
        logger.error("\"%s\" does not match any tools"
                     % _tool_string(tool_name, version))
        return
    ti = ts.find_tool(tool_name, installed=True)
    if ti is None:
        logger.error("\"%s\" does not match any installed tools" % tool_name)
        return
    if (version is None and not new_ti.newer_than(ti)
            or new_ti.version == ti.version):
        logger.info("\"%s\" is up to date" % tool_name)
        return
    ts.install_tool(new_ti, logger)
ts_update_desc = CmdDesc(required=[("tool_name", StringArg)],
                         optional=[("version", StringArg)])


#
# Commands that deal with GUI (singleton)
#


def get_singleton(session, create=False):
    if not session.ui.is_gui:
        return None
    from .gui import ToolshedUI
    running = session.tools.find_by_class(ToolshedUI)
    if len(running) > 1:
        raise RuntimeError("too many toolshed instances running")
    if not running:
        if create:
            tool_info = session.toolshed.find_tool('toolshed')
            return ToolshedUI(session, tool_info)
        else:
            return None
    else:
        return running[0]


def ts_hide(session):
    ts = get_singleton(session)
    if ts is not None:
        ts.display(False)
ts_hide_desc = CmdDesc()


def ts_show(session):
    ts = get_singleton(session, create=True)
    if ts is not None:
        ts.display(True)
ts_show_desc = CmdDesc()
