import logging
import os

import click

from . import utils as u

logger = logging.getLogger(__name__)

PLATFORMS = ("osx-64", "linux-64", "win-32", "win-64")


def conda_build():
    lasttoken = u.check_output("conda build -V").split()[-1]
    major_version = int(lasttoken.split(".")[0])
    if major_version >= 3:
        return "conda build --old-build-string"
    return "conda build"


def conda_build_directory():
    conda_path = u.check_output("which conda").strip()
    anaconda_path = os.path.dirname(os.path.dirname(conda_path))
    if "envs" in anaconda_path:
        anaconda_path = os.path.dirname(os.path.dirname(anaconda_path))
    return os.path.join(anaconda_path, "conda-bld")


def py_int(s):
    return int("".join(s.split(".")[:2]))


class Package(object):
    def __init__(self, name, repo, cachedir,
                 supported_versions, dependencies=[]):
        self._name = name
        self._cachedir = cachedir
        self._dependencies = dependencies
        self._supported_versions = supported_versions
        self._tag = None
        repo.path = os.path.join(self.pull_cachedir, name)
        self._repo = repo

    @property
    def name(self):
        return self._name

    @property
    def repo(self):
        return self._repo

    @property
    def supported_versions(self):
        return self._supported_versions

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def cachedir(self):
        return self._cachedir

    @property
    def pull_cachedir(self):
        return os.path.join(self.cachedir, "pull")

    @property
    def build_cachedir(self):
        return os.path.join(self.cachedir, "build")

    @property
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self, value):
        self._tag = value

    @property
    def header(self):
        return click.style(self.name, fg="cyan")

    def pull(self):
        if self.repo.is_valid():
            click.echo("[{}] {}".format(self.header,
                                        click.style("resetting", fg="green")))
            self.repo.reset()

            click.echo("[{}] {}".format(self.header,
                                        click.style("pulling", fg="green")))
            self.repo.pull()
        else:
            click.echo("[{}] {}".format(self.header,
                                        click.style("removing", fg="green")))
            self.repo.remove()

            click.echo("[{}] {}".format(self.header,
                                        click.style("cloning", fg="green")))
            self.repo.clone()

        click.echo("[{}] {}".format(self.header,
                                    click.style("fetching", fg="green")))
        self.repo.fetch()

        if not self.tag:
            self.tag = self.repo.latest_tag()

        chkout = click.style("checking-out {}".format(self.tag), fg="green")
        click.echo("[{}] {}".format(self.header, chkout))
        self.repo.checkout(tag=self.tag)

        click.echo("[{}] {}".format(self.header,
                                    click.style("archiving", fg="green")))
        self.repo.archive(self.name, self.tag, self.build_cachedir)

    def build(self, channel, py_versions):
        with u.change_working_directory(self.build_cachedir):
            u.call("tar xvf {}-{}.tar".format(self.name, self.tag))

        archivedir = os.path.join(self.build_cachedir,
                                  "{}-{}".format(self.name, self.tag))
        cmd = conda_build()
        conda_recipe = u.find_first_filename(archivedir,
                                             "conda.recipe",
                                             "Python/conda.recipe")
        conda_meta = os.path.join(archivedir, conda_recipe, "meta.yaml")

        u.replace_all(conda_meta, r"version: .*", "version: " + self.tag)
        for pkg in self.dependencies:
            u.replace_all(conda_meta,
                          "- {}.*".format(pkg.name),
                          "- {} >={}".format(pkg.name, pkg.tag))

        with u.change_working_directory(archivedir):
            for py_version in (tuple(set(py_versions) &
                                     set(self.supported_versions))):
                bld = click.style("building {}".format(py_version), fg="green")
                click.echo("[{}] {}".format(self.header, bld))
                cmdstr = "{} -c {} --no-anaconda-upload --python {} {}"
                u.call(cmdstr.format(cmd, channel, py_version, conda_recipe))
                cmdstr = "{} --python {} {} --output"
                cmdall = cmdstr.format(cmd, py_version, conda_recipe)
                build_output = u.check_output(cmdall)
                build_file = build_output.split()[-1]
                build_dir = os.path.dirname(build_file)
                current_platform = os.path.basename(build_dir)
                package = os.path.basename(build_file)

                with u.change_working_directory(build_dir):
                    for platform in PLATFORMS:
                        if platform == current_platform:
                            continue
                        conv = click.style("converting-to {}".format(platform),
                                           fg="green")
                        click.echo("[{}] {}".format(self.header, conv))
                        cmdstr = "conda convert --platform {} {} -o ../"
                        u.call(cmdstr.format(platform, package))

    def upload(self, token, label, py_versions, user=None, force=False):
        cmd = "anaconda"

        if token:
            logger.info("config for anaconda upload: token was provided")
            cmd += " --token " + token
        else:
            logger.info("config for anaconda upload: token was not provided")

        cmd += " upload -t conda --no-progress"

        if force:
            logger.info("config for anaconda upload: force is enabled")
            cmd += " --force"
        else:
            logger.info("config for anaconda upload: force is disabled")

        logger.info("config for anaconda upload: label={}".format(label))
        if label:
            cmd += " --label " + label

        logger.info("config for anaconda upload: user={}".format(user))
        if user:
            cmd += " --user " + user

        build_dir = conda_build_directory()

        if not self.tag:
            self.tag = self.repo.latest_tag()

        with u.change_working_directory(build_dir):
            for platform in PLATFORMS:
                upstr = click.style("uploading {} packages".format(platform),
                                    fg="green")
                click.echo("[{}] {}".format(self.header, upstr))
                for py_version in (tuple(set(py_versions) &
                                         set(self.supported_versions))):
                    bld = "{0}-{1}-py{2}_0.tar.bz2"
                    build_pkg = bld.format(self.name, self.tag,
                                           py_int(py_version))
                    pkg = os.path.join(build_dir, platform, build_pkg)

                    logger.info("uploading " + pkg)
                    try:
                        u.call("{} {}".format(cmd, pkg))
                    except:
                        emsg = ("Failed on anaconda upload likely "
                                "because version already exists - continuing")
                        logger.error(emsg)
