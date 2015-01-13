# vim: set expandtab ts=4 sw=4:

class ToolUI:

    SIZE = (500, 25)

    def __init__(self, session):
        import weakref
        self._session = weakref.ref(session)
        from chimera.core.ui.tool_api import ToolWindow
        self.tool_window = ToolWindow("toolshed", "General",
                                        session, size=self.SIZE)
        parent = self.tool_window.ui_area
        # UI content code
        self.tool_window.manage(placement="bottom")

    def OnEnter(self, event):
        session = self._session()  # resolve back reference
        # Handle event
