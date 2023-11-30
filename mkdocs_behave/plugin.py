# SPDX-FileCopyrightText: 2023 Matthew Francis <mjay.francis@gmail.com>
#
# SPDX-License-Identifier: MIT
"""
Behave feature file plugin for MkDocs
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from runpy import run_module
from types import MappingProxyType
from typing import Dict, List, Literal, Sequence, Union

from mkdocs.config import config_options
from mkdocs.config.base import Config
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files, InclusionLevel
from mkdocs.structure.pages import Page

from mkdocs_behave.featureformatter import FeatureFormatter

log = logging.getLogger('mkdocs.plugins.mkdocs_behave')


NavTree = List[Union[str, Dict[str, 'NavTree']]]

ConfiguredFeatureFormatter: type[FeatureFormatter]


class BehavePluginConfig(Config):
    features_dir = config_options.Dir(exists=True, default='features')
    nav_heading = config_options.Type(str, default='Features')
    populate = config_options.Type(bool, default=True)
    warn_missing = config_options.Type(bool, default=True)
    step_highlight = config_options.DictOfItems(option_type=config_options.Type(str), default=MappingProxyType({}))


class BehavePlugin(BasePlugin[BehavePluginConfig]):
    """Behave feature file plugin for MkDocs."""

    _step_highlight_regexes: dict[re.Pattern, str]
    _handled_feature_files: set[str]

    def on_startup(self, *, command: Literal['build', 'gh-deploy', 'serve'], dirty: bool) -> None:
        # Necessary as an API marker
        pass

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig | None:
        # Pre-compile syntax highlighting regexes
        self._step_highlight_regexes = {re.compile(regex): value for regex, value in self.config.step_highlight.items()}

        # Watch for changes to features when running 'mkdocs serve'
        config.watch.append(self.config.features_dir)
        return config

    def _run_behave(self) -> None:
        # Have your fainting couch ready while we run an external command in-process
        # (repeatedly, in the case of 'mkdocs serve')
        global ConfiguredFeatureFormatter  # noqa: PLW0603
        ConfiguredFeatureFormatter = type(
            'ConfiguredFeatureFormatter', (FeatureFormatter,), {}, step_highlight_regexes=self._step_highlight_regexes
        )

        saved_argv = sys.argv
        try:
            sys.argv = [
                '',
                '--dry-run',
                '--no-summary',
                '--format',
                'mkdocs_behave.plugin:ConfiguredFeatureFormatter',
            ]
            run_module('behave.__main__', run_name='__main__')
        except SystemExit as e:
            if e.code:
                log.warning('Behave did not complete successfully. Some features may not have been processed.')
        finally:
            sys.argv = saved_argv

    @staticmethod
    def _build_feature_tree(feature_paths: Sequence[Path]) -> NavTree:
        # Build a tree containing the features that mirrors the nav
        feature_tree: NavTree = []
        for feature_path in feature_paths:
            working_tree = feature_tree
            for part in feature_path.parent.parts[1:]:
                sub_tree = next((x[part] for x in working_tree if isinstance(x, dict) and part in x), None)
                if sub_tree is None:
                    sub_tree = []
                    working_tree.append({part: sub_tree})
                working_tree = sub_tree
            working_tree.append(str(feature_path))
        return feature_tree

    @staticmethod
    def _build_feature_files(site_dir, feature_paths: Sequence[Path]):
        # Construct a MkDocs File to mirror each feature file.
        # These virtual files are required because markdown processing is skipped if the extension
        # is not ".md". They do not (should not) exist on disk, but are consumed by
        # on_page_read_source() which fills in the converted markdown for the feature.
        cwd = str(Path.cwd())
        feature_files = [
            File(
                path=str(feature_path.with_suffix('.md')),
                src_dir=cwd,
                dest_dir=site_dir,
                use_directory_urls=True,
                dest_uri=f'{feature_path.parent / feature_path.stem}/index.html',
                inclusion=InclusionLevel.INCLUDED,
            )
            for feature_path in feature_paths
        ]
        return feature_files

    @staticmethod
    def _merge_features_into_nav(nav_tree: NavTree, feature_tree: NavTree):
        # Merge the tree of features into the nav
        def merge(nav_entry, feature_entry):
            for element in feature_entry:
                if isinstance(element, str):
                    if element not in nav_entry:
                        nav_entry.append(element)
                else:
                    name, sub_feature_entry = next(iter(element.items()))
                    name = name.replace('_', ' ').capitalize()
                    sub_nav_entry = next(
                        (entry[name] for entry in nav_entry if isinstance(entry, dict) and name in entry), None
                    )
                    if sub_nav_entry is None:
                        sub_tree: NavTree = []
                        nav_entry.append({name: sub_tree})
                        sub_nav_entry = sub_tree

                    merge(sub_nav_entry, sub_feature_entry)

        merge(nav_tree, feature_tree)

    @staticmethod
    def _get_feature_paths_in_nav(nav_tree: NavTree) -> list[Path]:
        # Get the Paths of every file in the nav ending in '.feature'
        paths = []

        def find(nav_entry):
            for element in nav_entry:
                if isinstance(element, str):
                    if element.endswith('.feature'):
                        paths.append(Path(element))
                else:
                    sub_nav_entry = next(iter(element.values()))
                    find(sub_nav_entry)

        find(nav_tree)
        return paths

    @staticmethod
    def _rename_features_in_nav(nav_tree: NavTree) -> None:
        # Rename files in the nav ending in '.feature' to '.md'
        def process(nav_entry):
            for index, element in enumerate(nav_entry):
                if isinstance(element, str):
                    if element.endswith('.feature'):
                        nav_entry[index] = str(Path(element).with_suffix('.md'))
                else:
                    sub_nav_entry = next(iter(element.values()))
                    process(sub_nav_entry)

        process(nav_tree)

    @staticmethod
    def _ensure_features_entry(nav_tree: NavTree, heading: str) -> NavTree:
        # Ensure the top-level nav heading for the features is present, and return its entry
        features_entry = next(
            (entry[heading] for entry in nav_tree if isinstance(entry, dict) and heading in entry), None
        )
        if features_entry is None:
            features_entry = []
            nav_tree.append({heading: features_entry})

        return features_entry

    def on_files(self, files: Files, *, config: MkDocsConfig) -> Files | None:
        # During each build, run behave to build and capture markdown for features, then merge
        # entries for the features into the nav
        self._run_behave()

        nav_tree: NavTree
        nav_tree = config.nav  # type: ignore
        features_entry = self._ensure_features_entry(nav_tree, self.config.nav_heading)

        features_dir = Path(self.config.features_dir).relative_to(Path.cwd())
        all_feature_paths = sorted(Path().rglob(f'{features_dir}/**/*.feature'))

        if self.config.populate:
            feature_paths = all_feature_paths
            feature_tree = self._build_feature_tree(feature_paths)
            self._merge_features_into_nav(features_entry, feature_tree)
        else:
            feature_paths = self._get_feature_paths_in_nav(features_entry)
            if self.config.warn_missing:
                for missing in sorted(set(all_feature_paths) - set(feature_paths)):
                    log.warning(
                        f"Feature file '{missing}' is present on disk, but is not included in the 'nav' configuration."
                    )

        self._rename_features_in_nav(features_entry)
        if self._get_feature_paths_in_nav(nav_tree):
            log.warning("Feature files are present in the 'nav' configuration outside the configured heading.")

        feature_files = self._build_feature_files(config.site_dir, feature_paths)
        self._handled_feature_files = {str(path.with_suffix('.md')) for path in feature_paths}

        for file in feature_files:
            files.append(file)

        return files

    def on_page_read_source(self, *, page: Page, config: MkDocsConfig) -> str | None:  # noqa: ARG002
        # If the page corresponds to a feature, return the converted markdown.
        # Otherwise, leave it to the default handling.
        if page.file.src_uri in self._handled_feature_files:
            feature_path = str(Path(page.file.src_uri).with_suffix('.feature'))
            return ConfiguredFeatureFormatter.rendered_features[feature_path]

        return None
