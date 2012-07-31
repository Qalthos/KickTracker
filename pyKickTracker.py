#!/usr/bin/env python
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
            md = project_scrape(project)

            proj_vbox = Gtk.VBox()

            proj_name = Gtk.Label()
            proj_name.set_text(md['title'])
            proj_vbox.add(proj_name)

            progress = Gtk.ProgressBar()
            progress.set_fraction(md['percent_raised'])
            proj_vbox.add(progress)

            details = Gtk.HBox()
            pledged = Gtk.Label()
            pledged.set_text(md['pledged'])
            details.add(pledged)
            percent = Gtk.Label()
            percent.set_text(md['pretty_percent'])
            details.add(percent)
            left = Gtk.Label()
            left.set_text(md['time_left'])
            details.add(left)
            proj_vbox.add(details)

            collect.add(proj_vbox)
        GLib.timeout_add(30000, refresh, collect)
        scrolly_pane.add_with_viewport(collect)
        self.add(scrolly_pane)



def project_scrape(project_id):
    url = 'http://www.kickstarter.com/projects/{0}'.format(project_id)
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
        metadata = project_scrape(tracked_projects[index])
        children = widget.get_children()
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
