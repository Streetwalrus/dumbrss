#!/usr/bin/env python3

import os
from flask import Flask
from time import ctime, tzset, mktime
import feedparser
from flask.ext.script import Manager
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Default config
app.config.update(dict(
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(app.root_path, "dumbrss.db")
))
if os.getenv("DRSS_CONFIG") == None:
    os.environ["DRSS_CONFIG"] = os.path.join(app.root_path, "config.py")
app.config.from_envvar("DRSS_CONFIG", silent = True)

if app.config["SECRET_KEY"] == None:
    f = open(os.environ["DRSS_CONFIG"], "a")
    app.config["SECRET_KEY"] = os.urandom(32)
    f.write("SECRET_KEY = " + str(app.config["SECRET_KEY"]) + "\n")
    f.close()

db = SQLAlchemy(app)
manager = Manager(app)

# Set the timezone to UTC for consistent time stamps
os.environ["TZ"] = "UTC"
tzset()

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feed.id"))
    feed = db.relationship("Feed", backref = db.backref("entries", lazy = "dynamic"))
    link = db.Column(db.Text)
    title = db.Column(db.Text)
    summary = db.Column(db.Text)
    author = db.Column(db.Text)
    date = db.Column(db.Integer)
    read = db.Column(db.Integer)
    starred = db.Column(db.Integer)

    def __init__(self, feed, link, title, summary, author, date):
        self.feed = feed
        self.link = link
        self.title = title
        self.summary = summary
        self.author = author
        self.date = date
        self.read = 0
        self.starred = 0

    def __repr__(self):
        return "<Entry {0} ({1})>".format(self.id, self.title)

class Feed(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    owner = db.relationship("User", backref = db.backref("feeds", lazy = "dynamic"))
    folder_id = db.Column(db.Integer, db.ForeignKey("folder.id"))
    folder = db.relationship("Folder", backref = db.backref("feeds", lazy = "dynamic"))
    name = db.Column(db.Text)
    icon = db.Column(db.Text)
    link = db.Column(db.Text)
    url = db.Column(db.Text)

    def __init__(self, owner, folder, name, icon, link, url):
        self.owner = owner
        self.folder = folder
        self.name = name
        self.icon = icon
        self.link = link
        self.url = url

    def __repr__(self):
        return "<Feed {0} ({1})>".format(self.id, self.name)

    def fetch(self, commit = True):
        app.logger.info("Fetching " + str(self))
        d = feedparser.parse(self.url)

        for entry in d.entries:
            if self.entries.filter_by(link = entry.link).count() == 0:
                if not(hasattr(entry, "author")):
                    entry.author = None
                date = int(mktime(entry.published_parsed))
                dbentry = Entry(self, entry.link, entry.title, entry.summary, entry.author, date)
                db.session.add(dbentry)

        if commit:
            db.session.commit()

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    owner = db.relationship("User", backref = db.backref("folders", lazy = "dynamic"))
    name = db.Column(db.Text)

    def __init__(self, owner, name):
        self.owner = owner
        self.name = name

    def __repr__():
        return "<Folder {0} ({1})>".format(self.id, self.name)

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.Text, unique = True)
    password = db.Column(db.Text)
    admin = db.Column(db.Integer)

    def __init__(self, name, password, admin):
        self.name = name
        self.password = password
        self.admin = admin

    def __repr__():
        return "<User {0} ({1})>".format(self.id, self.name)

@app.route("/")
def root():
    asdf = Entry.query.order_by(Entry.date.desc()).all()
    hjkl = ""
    for stuff in asdf:
        hjkl += str(stuff.feed.name) + ": <a href=\"" + stuff.link + "\">" + stuff.title + "</a>"
        if stuff.author != None:
            hjkl += " by " + stuff.author
        hjkl += " on " + ctime(stuff.date) + "<br />"
    return hjkl

def fetch_feeds():
    for feed in Feed.query.yield_per(1000):
        feed.fetch(commit = False)
    db.session.commit()

def fetch_feed(id):
    f = Feed.query.filter_by(id = id).first().fetch()

@app.route("/fetch")
@app.route("/fetch/<int:id>")
def webfetch(id = None):
    if id == None:
        fetch_feeds()
    else:
        try:
            fetch_feed(id)
        except AttributeError:
            return "No feed with ID " + str(id)
    return ""

@manager.option("-f", "--feed", dest = "id", default = None)
def fetch(id):
    "Fetch feed updates"
    if id == None:
        fetch_feeds()
    else:
        try:
            id = int(id)
        except ValueError:
            print("Feed ID must be an integer")
            return

        try:
            fetch_feed(id)
        except AttributeError:
            print("No feed with ID", id)

@manager.command
def initdb():
    "Initialize the database"
    db.create_all()

if __name__ == "__main__":
    manager.run()

