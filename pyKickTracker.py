#!/usr/bin/env python
from datetime import datetime, timedelta
import locale
import os.path
import sys

if sys.version_info.major == 2:
    from urllib2 import urlopen
else:
    from urllib.request import urlopen

from bs4 import BeautifulSoup

from gi.repository import Gtk, GdkPixbuf, GLib

import config

class TrackerWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_default_size(400, 250)
        icon_path = os.path.join(os.path.split(__file__)[0], 'favicon.ico')
        self.set_default_icon(GdkPixbuf.Pixbuf.new_from_file(icon_path))

        notebook = Gtk.Notebook()
        active_scroll = Gtk.ScrolledWindow()
        complete_scroll = Gtk.ScrolledWindow()
        self.active = Gtk.VBox()
        self.complete = Gtk.VBox()

        self.settings_page = SettingsPage()

        active_scroll.add_with_viewport(self.active)
        complete_scroll.add_with_viewport(self.complete)
        notebook.append_page(active_scroll, Gtk.Label('Acive Projects'))
        notebook.append_page(complete_scroll, Gtk.Label('Completed Projects'))
        notebook.append_page(self.settings_page, Gtk.Label('Settings'))
        self.add(notebook)

        self.loaded_projects = dict()

    def load_projects(self):
        # Build a list of backed projects
        url = 'http://www.kickstarter.com/profile/{0}' \
            .format(self.settings_page.settings['user']['profile'])
        soup = BeautifulSoup(urlopen(url)).findAll('a', 'project_item')
        projects = set(map(lambda x: x['href'], soup)).union(set(filter(bool,
            self.settings_page.settings['projects']['other'].split(', '))))

        # Remove projects no longer visible
        to_remove = set(self.loaded_projects.keys()).difference(projects)
        for project in to_remove:
            widget = self.loaded_projects.pop(project)
            widget.get_parent().remove(widget)

        now = datetime.utcnow()
        # Filter out the projects that don't need to be replaced
        projects.difference_update(set(self.loaded_projects.keys()))
        for project in projects:
            url = 'http://www.kickstarter.com{0}'.format(project)
            proj_box = ProjectBox(url)
            try:
                timeout = int(self.settings_page.settings['projects']['hide_after'])
                if proj_box.end_date + timedelta(days=timeout) < now:
                    # For simplicity, hide projects older than a certain time
                    continue
            except ValueError:
                pass
            if proj_box.end_date > now:
                self.active.pack_start(proj_box, False, False, 0)
            else:
                proj_box.left.set_text('Done!')
                self.complete.pack_start(proj_box, False, False, 0)

            self.loaded_projects[project] = proj_box

        for box in [self.active, self.complete]:
            box.show_all()

        GLib.timeout_add(30000, refresh, self.active)
        GLib.timeout_add(1000, refresh_time, self.active)


class ProjectBox(Gtk.VBox):
    def __init__(self, url):
        Gtk.VBox.__init__(self)
        metadata = project_scrape(url)
        linkbar = Gtk.HBox()

        self.title = Gtk.LinkButton(url, metadata['title'])
        linkbar.pack_start(self.title, True, True, 0)

        self.updates = Gtk.LinkButton(url + '/posts', metadata['updates'])
        linkbar.pack_start(self.updates, False, False, 0)
        self.add(linkbar)

        self.progress = Gtk.ProgressBar()
        self.progress.set_fraction(metadata['percent_raised'])
        self.add(self.progress)

        details = Gtk.HBox()

        self.pledged = Gtk.Label(metadata['pledged'])
        self.pledged.set_alignment(0, 0.5)
        self.pledged.set_width_chars(10)
        details.pack_start(self.pledged, False, False, 0)

        self.percent = Gtk.Label(metadata['pretty_percent'])
        self.percent.set_alignment(1, 0.5)
        details.add(self.percent)

        self.end_date = metadata['end_date']
        now = datetime.utcnow().replace(microsecond=0)
        self.left = Gtk.Label(str(self.end_date - now))
        self.left.set_alignment(1, 0.5)
        details.add(self.left)

        self.add(details)


class SettingsPage(Gtk.VBox):
    def __init__(self):
        Gtk.VBox.__init__(self)

        self.add(Gtk.Label("Kickstarter profile"))
        self.profile = Gtk.Entry()
        self.add(self.profile)

        self.add(Gtk.Label("Manually tracked projects"))
        self.projects = Gtk.TextView()
        self.add(self.projects)

        self.add(Gtk.Label("Don't show me projects that have closed more than this many days ago"))
        self.timeout = Gtk.Entry()
        self.add(self.timeout)

        button_box = Gtk.HButtonBox()

        self.rescan = Gtk.Button('Rescan Projects')
        button_box.add(self.rescan)

        self.cancel = Gtk.Button('Reset')
        button_box.add(self.cancel)

        self.add(button_box)

        self.settings = config.get_config()

        # Connect signals to buttons
        self.rescan.connect("clicked", self.save_or_reset)
        self.cancel.connect("clicked", self.save_or_reset)

        self.save_or_reset()

    def save_or_reset(self, button=None, event=None):
        if button == self.rescan:
            self.settings['user']['profile'] = self.profile.get_text()
            self.settings['projects']['other'] = ', '.join(
                self.projects.get_buffer().get_text(
                    self.projects.get_buffer().get_start_iter(),
                    self.projects.get_buffer().get_end_iter(),
                    False).split('\n'))
            self.settings['projects']['hide_after'] = self.timeout.get_text()
            config.write_config(self.settings)
            win.load_projects()
        else:
            self.profile.set_text(self.settings['user']['profile'])
            self.projects.get_buffer().set_text('\n'.join(
                self.settings['projects']['other'].split(', ')))
            self.timeout.set_text(self.settings['projects']['hide_after'])


def project_scrape(url):
    raw_html = urlopen(url)
    soup = BeautifulSoup(raw_html)
    pledge_div = soup.find('div', {'id': 'pledged'})
    time_div = soup.find('span', {'id': 'project_duration_data'})

    metadata = dict()
    metadata['title'] = soup.find('h1', {'id': 'title'}).a.string
    percent_raised = float(pledge_div['data-percent-raised'])
    metadata['percent_raised'] = min(percent_raised, 1.0)
    metadata['pretty_percent'] = '%.2f%%' % (percent_raised * 100)
    metadata['pledged'] = locale.currency(float(pledge_div['data-pledged']),
                                          grouping=True)
    # Cut the timezone info off the string so we don't have to deal with it.
    time_string = time_div['data-end_time'].rsplit(' ', 1)[0]
    metadata['end_date'] = datetime.strptime(time_string,
                                             '%a, %d %b %Y %H:%M:%S')
    updates = soup.find('span', {'id': 'updates_count'})
    metadata['updates'] = updates['data-updates-count']

    return metadata


def refresh(container):
    """
    Refresh the contents of the projects.

    @param container: The VBox full of ProjBox to update.

    @return True.  This is to keep timeout rescheduling the callback.
    """

    for widget in container.get_children():
        metadata = project_scrape(widget.title.get_uri())
        widget.progress.set_fraction(min(1.0, metadata['percent_raised']))
        widget.pledged.set_text(metadata['pledged'])
        widget.percent.set_text(metadata['pretty_percent'])
        widget.updates.set_label(metadata['updates'])

    return True


def refresh_time(container):
    """
    Refresh the project countdown for each project.  If the project has
    expired, move the ProjBox to the completed tab.

    @param container: The VBox full of ProjBox to update.

    @return True.  This is to keep timeout rescheduling the callback.
    """

    now = datetime.utcnow().replace(microsecond=0)
    for widget in container.get_children():
        if widget.end_date > now:
            widget.left.set_text(str(widget.end_date - now))
        else:
            widget.left.set_text('Done!')
            win.complete.pack_start(widget, False, False, 0)
            container.remove(widget)

    return True


def save_and_quit(window, event):
    config.write_config(window.settings_page.settings)
    Gtk.main_quit()


if __name__ == '__main__':
    win = TrackerWindow()
    win.connect("delete-event", save_and_quit)
    win.show_all()
    win.load_projects()
    Gtk.main()
