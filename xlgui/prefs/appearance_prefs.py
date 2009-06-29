# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from xlgui.prefs import widgets
from xl import xdg
from xlgui import commondialogs

name = "Appearance"
glade = xdg.get_data_path('glade/appearance_prefs_pane.glade')

class SplashPreference(widgets.CheckPrefsItem):
    default = True
    name = 'gui/use_splash'

class TrayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'gui/use_tray' 

class EnsureVisiblePreference(widgets.CheckPrefsItem):
    default = True
    name = 'gui/ensure_visible'

class ShowTabBarPreference(widgets.CheckPrefsItem):
    default = True
    name = 'gui/show_tabbar'

class TabPlacementPreference(widgets.ComboPrefsItem):
    default = 'top'
    name = 'gui/tab_placement'
    map = ['left', 'right', 'top', 'bottom']
    def __init__(self, prefs, widget):
        widgets.ComboPrefsItem.__init__(self, prefs, widget, use_map=True)