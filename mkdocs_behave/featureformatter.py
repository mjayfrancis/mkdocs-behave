# SPDX-FileCopyrightText: 2023 Matthew Francis <mjay.francis@gmail.com>
#
# SPDX-License-Identifier: MIT
"""A Behave formatter to generate markdown."""

from __future__ import annotations

import re
from io import StringIO
from typing import ClassVar

from behave.formatter.base import Formatter  # type: ignore
from behave.model import ScenarioOutline  # type: ignore


def _strip_dots(lines):
    # Remove leading dots protecting markdown in feature text
    return [line[2:] if line == '.' or line.startswith('. ') else line for line in lines]


class FeatureFormatter(Formatter):
    """A Behave formatter to generate markdown."""

    _step_highlight_regexes: ClassVar[dict[re.Pattern, str]] = {}
    _filename: str
    _output: StringIO

    rendered_features: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls, *, step_highlight_regexes: dict[re.Pattern, str], **kwargs):
        # The formatter needs to be configured by the MkDocs plugin, but must be
        # instantiated by behave, so a subclass is made to handle the initial
        # configuration
        super().__init_subclass__(**kwargs)
        cls._step_highlight_regexes = step_highlight_regexes

    def uri(self, filename):
        self._filename = filename
        self._output = StringIO()
        self._output.write('<!-- Generated from ' + filename + ' -->\n')
        self._output.write('\n')

    def eof(self):
        self.rendered_features[self._filename] = self._output.getvalue()
        self._output.close()

    def feature(self, feature):
        self._output.write(f'# {feature.name}\n')
        if feature.tags:
            self._output.write('!!! note\n')
            self._output.write('    ' + ' '.join('@' + tag for tag in feature.tags) + '\n')
            self._output.write('\n')
        description_lines = _strip_dots(feature.description)
        for _, line in enumerate(description_lines):
            self._output.write(line + '\n')
        self._output.write('\n')

        if feature.background:
            self.format_background(feature.background)

        self._output.write('## Scenarios\n')

        for scenario in feature.scenarios:
            self.format_scenario(scenario)

    def format_background(self, background):
        self._output.write('## Background\n')
        self._output.write('\n')
        for step in background.steps:
            self.format_step(step)

    def format_scenario(self, scenario):
        self._output.write(f'### {scenario.name}\n')
        if scenario.tags:
            self._output.write('!!! note\n')
            self._output.write('    ' + ' '.join('@' + tag for tag in scenario.tags) + '\n')
            self._output.write('\n')

        for step in scenario.steps:
            self.format_step(step)
        self._output.write('\n')

        if isinstance(scenario, ScenarioOutline):
            for examples in scenario.examples:
                self._output.write(('#### Examples' + f': {examples.name}' if examples.name else '') + '\n')
                self._output.write(f'|{"|".join(examples.table.headings)}|\n')
                self._output.write('|--' * len(examples.table.headings) + '|\n')
                for row in examples.table:
                    self._output.write(f'|{"|".join(f"`{cell}`" for cell in row)}|\n')
                self._output.write('\n')

    def _guess_code_language(self, step_name: str) -> str:
        for pattern, language in self._step_highlight_regexes.items():
            if pattern.search(step_name):
                return language
        return ''

    def format_step(self, step):
        name = re.sub(r'"([^"]*)"', r'"`\1`"', step.name)  # Render double-quoted text as pre-formatted (code)

        self._output.write(f'**{step.keyword}** {name}  \n')
        if step.text:
            block_format = self._guess_code_language(step.name)
            self._output.write('\n')
            self._output.write(f'```{block_format}\n')
            self._output.write(step.text + '\n')
            self._output.write('```\n')
