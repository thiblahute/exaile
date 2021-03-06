# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from collections import namedtuple
import gio
import glib
import gtk
import os
import threading

from xl import event, settings, xdg
from xlgui import icons

# moved idle_add to common, useful for more than just GUI stuff :)
from xl.common import idle_add


def gtkrun(f):
    """
        A decorator that will make any function run in gtk threadsafe mode

        ALL CODE MODIFYING THE UI SHOULD BE WRAPPED IN THIS
    """
    raise DeprecationWarning('We no longer need to use this '
        'function for xl/event.')
    def wrapper(*args, **kwargs):
        # if we're already in the main thread and you try to run
        # threads_enter, stuff will break horribly, so test for the main
        # thread and if we're currently in it we simply run the function
        if threading.currentThread().getName() == 'MainThread':
            return f(*args, **kwargs)
        else:
            gtk.gdk.threads_enter()
            try:
                return f(*args, **kwargs)
            finally:
                gtk.gdk.threads_leave()

    wrapper.__name__ = f.__name__
    wrapper.__dict__ = f.__dict__
    wrapper.__doc__ = f.__doc__

    return wrapper

def get_workarea_size():
    """
        Returns the width and height of the work area
    """
    return get_workarea_dimensions()[2:4]

def get_workarea_dimensions():
    """
        Returns the x-offset, y-offset, width and height
        of the work area, falls back to the screen
        dimensions if not available

        :returns: Dimensions(offset_x, offset_y, width, height)
    """
    Dimensions = namedtuple('Dimensions', 'offset_x offset_y width height')

    rootwindow = gtk.gdk.get_default_root_window()
    workarea = rootwindow.property_get(gtk.gdk.atom_intern('_NET_WORKAREA'))

    try:
        return Dimensions(*workarea[2])
    except TypeError: # gtk.gdk.Window.property_get on Win32
        # Chopping off bit depth
        return Dimensions(*rootwindow.get_geometry()[:-1])

def gtk_widget_replace(widget, replacement):
    """
        Replaces one widget with another and
        places it exactly at the original position

        :param widget: The original widget
        :type widget: :class:`gtk.Widget`
        :param replacement: The new widget
        :type widget: :class:`gtk.Widget`
    """
    parent = widget.get_parent()

    try:
        position = parent.get_children().index(widget)
    except AttributeError: # None, not gtk.Container
        return
    else:
        try:
            packing = parent.query_child_packing(widget)
        except AttributeError: # Not gtk.Box
            pass

        try:
            tab_label = parent.get_tab_label(widget)
            tab_label_packing = parent.query_tab_label_packing(widget)
        except AttributeError: # Not gtk.Notebook
            pass

        parent.remove(widget)
        replacement.unparent()
        parent.add(replacement)

        try:
            parent.set_child_packing(replacement, *packing)
        except AttributeError: # Not gtk.Box
            pass

        try:
            parent.reorder_child(replacement, position)
        except AttributeError:
            pass

        try:
            parent.set_tab_label(replacement, tab_label)
            parent.set_tab_label_packing(replacement, *tab_label_packing)
        except AttributeError:
            pass

        replacement.show_all()

class ScalableImageWidget(gtk.Image):
    """
        Custom resizeable image widget
    """
    def __init__(self):
        """
            Initializes the image
        """
        gtk.Image.__init__(self)

    def set_image_size(self, width, height):
        """
            Scales the size of the image
        """
        self.size = (width, height)
        self.set_size_request(width, height)

    def set_image(self, location, fill=False):
        """
            Sets the image from a location

            :param location: the location to load the image from
            :type location: string
            :param fill: True to expand the image, False to keep its ratio
            :type fill: boolean
        """
        pixbuf = gtk.gdk.pixbuf_new_from_file(gio.File(location).get_path())
        self.set_image_pixbuf(pixbuf, fill)

    def set_image_data(self, data, fill=False):
        """
            Sets the image from binary data

            :param data: the binary data
            :type data: string
            :param fill: True to expand the image, False to keep its ratio
            :type fill: boolean
        """
        if not data:
            return
        pixbuf = icons.MANAGER.pixbuf_from_data(data)
        self.set_image_pixbuf(pixbuf, fill)

    def set_image_pixbuf(self, pixbuf, fill=False):
        """
            Sets the image from a pixbuf

            :param data: the pixbuf
            :type data: :class:`gtk.gdk.Pixbuf`
            :param fill: True to expand the image, False to keep its ratio
            :type fill: boolean
        """
        width, height = self.size
        if not fill:
            origw = float(pixbuf.get_width())
            origh = float(pixbuf.get_height())
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
        self.width = width
        self.height = height
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(scaled)

        scaled = pixbuf = None

class SearchEntry(object):
    """
        A gtk.Entry that emits the "activated" signal when something has
        changed after the specified timeout
    """
    def __init__(self, entry=None, timeout=500):
        """
            Initializes the entry
        """
        self.entry = entry
        self.timeout = timeout
        self.change_id = None

        if entry is None:
            self.entry = entry = gtk.Entry()
            
        self._last_text = entry.get_text()

        entry.connect('changed', self.on_entry_changed)
        entry.connect('icon-press', self.on_entry_icon_press)
        entry.connect('activate', self.on_entry_activated)

    def on_entry_changed(self, entry):
        """
            Called when the entry changes
        """
        empty_search = (entry.get_text() == '')
        entry.props.secondary_icon_sensitive = not empty_search

        if self.change_id:
            glib.source_remove(self.change_id)
        self.change_id = glib.timeout_add(self.timeout,
            self.entry_activate)

    def on_entry_icon_press(self, entry, icon_pos, event):
        """
            Clears the entry
        """
        self.entry.set_text('')
        self.entry_activate()

    def on_entry_activated(self, entry):
        self._last_text = entry.get_text()

    def entry_activate(self, *e):
        """
            Emit the activate signal
        """
        if self.entry.get_text() != self._last_text:
            self.entry.activate()

    def __getattr__(self, attr):
        """
            Tries to pass attribute requests
            to the internal entry item
        """
        return getattr(self.entry, attr)

class Menu(gtk.Menu):
    """
        A proxy for making it easier to add icons to menu items
    """
    def __init__(self):
        """
            Initializes the menu
        """
        gtk.Menu.__init__(self)
        self._dynamic_builders = []    # list of (callback, args, kwargs)
        self._destroy_dynamic = []     # list of children added by dynamic
                                       # builders. Will be destroyed and
                                       # recreated at each map()
        self.connect('map', self._check_dynamic)

        self.show()

    def append_image(self, pixbuf, callback, data=None):
        """
            Appends a graphic as a menu item
        """
        item = gtk.MenuItem()
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        item.add(image)

        if callback: item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

    def _insert(self, label=None, callback=None, stock_id=None, data=None, prepend=False):
        """
            Inserts a menu item (append by default)
        """
        if stock_id:
            if label:
                item = gtk.ImageMenuItem(label)
                image = gtk.image_new_from_stock(stock_id,
                    gtk.ICON_SIZE_MENU)
                item.set_image(image)
            else:
                item = gtk.ImageMenuItem(stock_id=stock_id)
        else:
            item = gtk.MenuItem(label)

        if callback: item.connect('activate', callback, data)

        if prepend:
            gtk.Menu.prepend(self, item)
        else:
            gtk.Menu.append(self, item)

        item.show_all()
        return item

    def append(self, label=None, callback=None, stock_id=None, data=None):
        """
            Appends a menu item
        """
        return self._insert(label, callback, stock_id, data)

    def prepend(self, label=None, callback=None, stock_id=None, data=None):
        """
            Prepends a menu item
        """
        return self._insert(label, callback, stock_id, data, prepend=True)

    def append_item(self, item):
        """
            Appends a menu item
        """
        gtk.Menu.append(self, item)
        item.show_all()

    def append_menu(self, label, menu, stock_id=None):
        """
            Appends a submenu
        """
        if stock_id:
            item = self.append(label, None, stock_id)
            item.set_submenu(menu)
            return item

        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.append(self, item)

        return item

    def insert_menu(self, index, label, menu):
        """
            Inserts a menu at the specified index
        """
        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.insert(self, item, index)

        return item

    def append_separator(self):
        """
            Adds a separator
        """
        item = gtk.SeparatorMenuItem()
        item.show()
        gtk.Menu.append(self, item)

    def add_dynamic_builder(self, callback, *args, **kwargs):
        """
            Adds a callback that will be run every time the menu is mapped,
            to add any items that change frequently. The items they add are
            destroyed and re-created with each map event.

        """
        self._dynamic_builders.append((callback, args, kwargs))

    def remove_dynamic_builder(self, callback):
        """
            Removes the given dynamic builder callback.
        """
        self._dynamic_builders = [ tuple for tuple in self._dynamic_builders
                                   if tuple[0] != callback ]

    def _check_dynamic(self, *args):
        """
           Deletes and builds again items added by the last batch of
           dynamic builder callbacks.
        """
        if self._destroy_dynamic:
            for child in self._destroy_dynamic:
                self.remove(child)
            self._destroy_dynamic = []

        if self._dynamic_builders:
            children_before = set(self.get_children())
            for callback, args, kwargs in self._dynamic_builders:
                callback(*args, **kwargs)
            self._destroy_dynamic = [ child for child in self.get_children()
                                      if child not in children_before ]

    def popup(self, *e):
        """
            Shows the menu
        """
        if len(e) == 1:
            event = e[0]
            gtk.Menu.popup(self, None, None, None, event.button, event.time)
        else:
            gtk.Menu.popup(self, *e)

            
def position_menu(menu, data):
    '''
        A function that will position a menu near a particular widget. This
        should be specified as the third argument to menu.popup(), with the
        user data being a tuple of (window, widget)
        
            menu.popup_menu(None, None, guiutil.position_menu, 
                            0, 0, (self.window, widget))
    '''
    
    window, widget = data
    window_x, window_y = window.get_position()
    widget_allocation = widget.get_allocation()
    menu_allocation = menu.get_allocation()
    position = (
        window_x + widget_allocation.x + 1,
        window_y + widget_allocation.y - menu_allocation.height - 1
    )

    return (position[0], position[1], True)

            

def finish(repeat=True):
    """
        Waits for current pending gtk events to finish
    """
    while gtk.events_pending():
        gtk.main_iteration()
        if not repeat: break
        
        

def initialize_from_xml(this, other=None):
    '''
        Initializes the widgets and signals from a GtkBuilder XML file. Looks 
        for the following attributes in the instance you pass:
        
        ui_filename = builder filename -- either an absolute path, or a tuple
                      with the path relative to the xdg data directory.
        ui_widgets = [list of widget names]
        ui_signals = [list of function names to connect to a signal]
        
        For each widget in ui_widgets, it will be retrieved from the builder
        object and set as an attribute on the object you pass in.
        
        other is a list of widgets to also initialize with the same file
        
        Returns the builder object when done
    '''
    builder = gtk.Builder()
    
    if isinstance(this.ui_filename, basestring) and os.path.exists(this.ui_filename):
        builder.add_from_file(this.ui_filename)
    else:
        builder.add_from_file(xdg.get_data_path(*this.ui_filename))
    
    objects = [this]
    if other is not None:
        objects.extend(other)
    
    for obj in objects:
        if hasattr(obj, 'ui_widgets') and obj.ui_widgets is not None:
            for widget_name in obj.ui_widgets:
                widget = builder.get_object(widget_name)
                if widget is None:
                    raise RuntimeError("Widget '%s' is not present in '%s'" % (widget_name, this.ui_filename))
                setattr(obj, widget_name, widget)
    
    signals = None
    
    for obj in objects:
        if hasattr(obj, 'ui_signals') and obj.ui_signals is not None:
            if signals is None:
                signals = {}
            for signal_name in obj.ui_signals:
                if not hasattr(obj, signal_name):
                    raise RuntimeError("Function '%s' is not present in '%s'" % (signal_name, obj))
                signals[signal_name] = getattr(obj, signal_name)
            
    if signals is not None:
        missing = builder.connect_signals(signals, None)
        if missing is not None:
            err = 'The following signals were found in %s but have no assigned handler: %s' % (this.ui_filename, str(missing))
            raise RuntimeError(err)
    
    return builder

def persist_selection(widget, key_col, setting_name):
    '''
        Given a widget that is using a gtk.ListStore, it will restore the
        selected index given the contents of a setting. When the widget
        changes, it will save the choice. 
        
        Call this on the widget after you have loaded data
        into the widget. 
    
        :param widget:         gtk.ComboBox or gtk.TreeView
        :param col:            Integer column with unique key
        :param setting_name:   Setting to save key to/from
    '''
    
    model = widget.get_model()
    
    key = settings.get_option(setting_name)
    if key is not None:
        for i in xrange(0, len(model)):
            if model[i][key_col] == key:
                if hasattr(widget, 'set_active'):
                    widget.set_active(i)
                else:
                    widget.set_cursor((i,))
                break
    
    if hasattr(widget, 'set_active'):
    
        def _on_changed(widget):
            active = widget.get_model()[widget.get_active()][key_col]
            settings.set_option(setting_name, active)
            
        widget.connect('changed', _on_changed)
        
    else:
        
        def _on_changed(widget):
            model, i = widget.get_selected()
            active = model[i][key_col]
            settings.set_option(setting_name, active)
        
        widget.get_selection().connect('changed', _on_changed)
    
# vim: et sts=4 sw=4
