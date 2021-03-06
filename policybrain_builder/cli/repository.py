import os
import shutil

import click

from . import utils as u


class Repository(object):
    def __init__(self, url):
        self._url = url
        self._path = "."

    @property
    def url(self):
        return self._url

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = value

    def is_valid(self):
        if not os.path.exists(self.path):
            return False
        if not os.path.exists(os.path.join(self.path, ".git")):
            return False
        with u.change_working_directory(self.path):
            git_cmd = "git rev-parse --is-inside-work-tree"
            is_git = u.check_output(git_cmd).strip()
            if is_git != "true":
                return False
            url = u.check_output("git ls-remote --get-url").strip()
            if url != self.url:
                return False
        return True

    def remove(self):
        click.echo("removing {}".format(self.path))
        if os.path.exists(self.path):
            shutil.rmtree(self.path)

    def reset(self):
        with u.change_working_directory(self.path):
            u.call("git checkout .")

    def clone(self):
        click.echo("cloning {} to {}".format(self.url, self.path))
        u.call("git clone {} {}".format(self.url, self.path))

    def latest_tag(self):
        tags = None
        with u.change_working_directory(self.path):
            output = u.check_output("git tag")
            tags = sorted(output.splitlines())
        return tags[-1] if tags else None

    def fetch(self):
        with u.change_working_directory(self.path):
            click.echo("fetching origin/tags for {}".format(self.path))
            u.call("git fetch origin")
            u.call("git fetch origin --tags")

    def pull(self):
        with u.change_working_directory(self.path):
            u.call("git pull origin master")

    def checkout(self, branch="master", tag=None):
        with u.change_working_directory(self.path):
            if tag:
                click.echo("checking-out tag {}".format(tag))
                u.call("git checkout " + tag)
            else:
                click.echo("checking-out branch {}".format(branch))
                u.call("git checkout " + branch)

    def archive(self, name, tag, archive_path):
        with u.change_working_directory(self.path):
            click.echo("archiving {}".format(self.path))
            u.ensure_directory_exists(archive_path)
            git_cmd = "git archive --prefix={0}-{1}/ -o {2}/{0}-{1}.tar {1}"
            u.call(git_cmd.format(name, tag, archive_path))
