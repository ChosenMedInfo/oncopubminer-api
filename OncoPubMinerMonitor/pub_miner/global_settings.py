# -*- coding: utf-8 -*-
# @Time : 2021/8/2 14:11
# @File : global_settings.py
# @Project : OncoPubMinerMonitor

import pub_miner
import yaml
import os
import sys
import codecs
import shutil


def loadYAML(yamlFilename):
    with open(yamlFilename, 'r') as f:
        try:
            yamlData = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            pub_miner.Config.Logger.error(exc)
            raise
    return yamlData


def prompt_user(prompt='> ', accepted=None):
    while True:
        pub_miner.Config.Logger.info(prompt, end='')
        sys.stdout.flush()
        user_input = sys.stdin.readline().strip()
        if accepted is None or user_input in accepted:
            break
        else:
            pub_miner.Config.Logger.info(f"Input not allowed. Must be one of {str(accepted)}")
    return user_input


def get_default_global_settings_path():
    defaultPath = os.path.join(pub_miner.__path__[0], 'PubMiner.settings.default.yml')
    assert os.path.isfile(defaultPath), "Unable to find default settings file"
    return defaultPath


def setup_default_global_settings_file(globalSettingsPath):
    defaultPath = get_default_global_settings_path()
    with codecs.open(defaultPath, 'r', 'utf-8') as f:
        defaultSettings = f.read()

    pub_miner.Config.Logger.info(
        f"No global settings file ({globalSettingsPath}) was found. Do you want to install the default one (below)?\n")
    pub_miner.Config.Logger.info(defaultSettings)

    user_input = prompt_user(prompt='(Y/N): ', accepted=['Y', 'N', 'y', 'n'])
    if user_input.lower() == 'y':
        shutil.copy(defaultPath, globalSettingsPath)

        pub_miner.Config.Logger.info("Default settings installed. Do you want to continue with this run?")
        user_input = prompt_user(prompt='(Y/N): ', accepted=['Y', 'N', 'y', 'n'])
        if user_input.lower() == 'n':
            pub_miner.Config.Logger.info("Exiting...")
            sys.exit(0)


globalSettings = None


def get_global_settings(useDefault=False):
    global globalSettings
    if globalSettings is None:
        if useDefault:
            globalSettingsPath = get_default_global_settings_path()
        else:
            homeDirectory = os.path.expanduser("~")
            globalSettingsPath = os.path.join(homeDirectory, '.PubMiner.settings.yml')
            if not os.path.isfile(globalSettingsPath):
                setup_default_global_settings_file(globalSettingsPath)
            assert os.path.isfile(globalSettingsPath), "Unable to find ~/.PubMiner.settings.yml file."

        globalSettings = loadYAML(globalSettingsPath)

    return globalSettings
