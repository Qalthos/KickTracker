#!/usr/bin/env python3
from datetime import datetime
import locale
import os.path
from urllib.request import urlopen

from bs4 import BeautifulSoup

from gi.repository import Gtk, GdkPixbuf, GLib

tracked_projects = ['playroom/killer-bunnies-quest-deluxe',
                    'hiddenpath/defense-grid-2',
                    'ouya/ouya-a-new-kind-of-video-game-console',
                    '597507018/pebble-e-paper-watch-for-iphone-and-android',
                   ]

class TrackerWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_default_size(400, 100)
        icon_path = os.path.join(os.path.split(__file__)[0], 'favicon.ico')
        self.set_default_icon(GdkPixbuf.Pixbuf.new_from_file(icon_path))

        scrolly_pane = Gtk.ScrolledWindow()
        collect = Gtk.VBox()
        for project in tracked_projects:
            url = 'http://www.kickstarter.com/projects/{0}'.format(project)
            proj_box = ProjectBox(url)
            collect.add(proj_box)

        GLib.timeout_add(30000, refresh, collect)
        scrolly_pane.add_with_viewport(collect)
        self.add(scrolly_pane)


class ProjectBox(Gtk.VBox):
    def __init__(self, url):
        Gtk.VBox.__init__(self)
        metadata = project_scrape(url)
        self.title = Gtk.LinkButton(url, metadata['title'])
        self.add(self.title)

        self.progress = Gtk.ProgressBar()
        self.progress.set_fraction(metadata['percent_raised'])
        self.add(self.progress)

        details = Gtk.HBox()

        self.pledged = Gtk.Label()
        self.pledged.set_text(metadata['pledged'])
        details.add(self.pledged)

        self.percent = Gtk.Label()
        self.percent.set_text(metadata['pretty_percent'])
        details.add(self.percent)

        self.left = Gtk.Label()
        self.left.set_text(metadata['time_left'])
        details.add(self.left)

        self.add(details)


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
    end_date = datetime.strptime(time_div['data-end_time'],
                                         '%a, %d %b %Y %H:%M:%S %z')
    now = datetime.now(end_date.tzinfo).replace(microsecond=0)
    metadata['time_left'] = str(end_date - now)

    return metadata

def refresh(container):
    """Refresh the contents of the projects."""
    for index, widget in enumerate(container.get_children()):
        children = widget.get_children()
        metadata = project_scrape(children[0].get_uri())
        children[1].set_fraction(min(1.0, metadata['percent_raised']))
        children[2].get_children()[0].set_text(metadata['pledged'])
        children[2].get_children()[1].set_text(metadata['pretty_percent'])
        children[2].get_children()[2].set_text(metadata['time_left'])

    # Keep going.
    return True

if __name__ == '__main__':
    win = TrackerWindow()
    win.connect("delete-event", Gtk.main_quit)
    win.show_all()
    Gtk.main()
