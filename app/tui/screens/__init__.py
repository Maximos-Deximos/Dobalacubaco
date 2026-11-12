# Telas da interface de terminal.

from app.tui.screens.chat import ChatPane
from app.tui.screens.help import HelpScreen
from app.tui.screens.home import HomeScreen
from app.tui.screens.profile import ProfileEditScreen, ProfileScreen
from app.tui.screens.proposals import ProposalScreen, ProposalsPane, ProposalsScreen
from app.tui.screens.sources import SourceDetailScreen, SourcesPane
from app.tui.screens.tools import DoctorPane, InspectPane, ToolsScreen
from app.tui.screens.workspaces import WorkspaceScreen, WorkspacesScreen

__all__ = [
    "ChatPane",
    "DoctorPane",
    "HelpScreen",
    "HomeScreen",
    "InspectPane",
    "ProfileEditScreen",
    "ProfileScreen",
    "ProposalScreen",
    "ProposalsPane",
    "ProposalsScreen",
    "SourceDetailScreen",
    "SourcesPane",
    "ToolsScreen",
    "WorkspaceScreen",
    "WorkspacesScreen",
]
