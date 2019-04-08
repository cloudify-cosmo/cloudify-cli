import os

from .. import env
from ..config import config

env.CLOUDIFY_WORKDIR = '/tmp/.cloudify-test'
env.PROFILES_DIR = os.path.join(env.CLOUDIFY_WORKDIR, 'profiles')
env.ACTIVE_PROFILE = os.path.join(env.CLOUDIFY_WORKDIR, 'active.profile')

config.CLOUDIFY_CONFIG_PATH = os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')
