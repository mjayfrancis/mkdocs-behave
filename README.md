# MkDocs Behave Plugin

[![PyPI - Version](https://img.shields.io/pypi/v/mkdocs-behave.svg)](https://pypi.org/project/mkdocs-behave)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mkdocs-behave.svg)](https://pypi.org/project/mkdocs-behave)

A [MkDocs](https://www.mkdocs.org/) plugin to render [behave](https://behave.readthedocs.io/) feature files.

## Installation

```console
pip install mkdocs-behave
```

## Usage

Add the following to `mkdocs.yml`:
```yaml
plugins:
  - behave
```

Feature files in `features/` in the project root will be converted to Markdown
and included in MkDocs navigation under the heading `Features`.

### Live preview

While previewing documentation using `mkdocs serve`, feature files will be
watched for changes in the same manner as Markdown files under `docs/`

### Markdown in feature files

Markdown can be used in the description text of features. However, behave does
not preserve leading whitespace in descriptions.

To protect Markdown in descriptions, prepend dots to a block:

```gherkin
Feature: My feature

  . - A multi-level list
  .   - with indentation
  .     - that would otherwise be lost

Scenario: ...
```

Specifically, the following are stripped at the beginning of a line of
description before it is processed as Markdown:
- A dot followed by a space
- A dot followed by a newline (i.e. no further text)

(Leading whitespace before the dots is stripped by behave)

### Configuration

Configuration options can be set beneath the plugin entry in `mkdocs.yml`.

```yaml
plugins:
  - behave:
      <option>: <value>
      # ...
```

The following options are available:

| Option           | Default    | Effect                                                                              |
|------------------|------------|-------------------------------------------------------------------------------------|
| `features_dir`   | `features` | Where feature files are read from disk (relative to the project root)               |
| `nav_heading`    | `Features` | The top-level MkDocs navigation heading under which features are displayed          |
| `populate`       | `true`     | Whether to automatically populate features under `nav_heading`                      |
| `warn_missing`   | `true`     | Whether to warn about features on disk that are not present in navigation           |
| `step_highlight` | `{}`       | A mapping of `regexp:language` to syntax highlight step text based on the step name |

Example of syntax highlighting configuration:
```yaml
plugins:
  - behave:
      step_highlight: {
        'file named ".*\.py"': python,
        'webpage containing': html,
      }
```

### Modes of operation

#### 1. Fully automatic feature population

This is the default. All feature files are populated into the navigation, sorted
alphanumerically.

Subdirectories under the features directory are turned into subheadings under
the main navigation heading. Directory names are processed as follows:
- Underscores (_) are replaced with spaces
- The first character is capitalised

#### 2. Partly manual feature population

To explicitly order features and subheadings, add suitable entries into
the navigation in `mkdocs.yml`. You can also insert additional Markdown files.

```yaml
nav:
  - Features:
      - features/index.md
      - features/first.feature
      - Sub heading:
          - features/sub_heading/second.feature
      - ...
```

Note that in this example, `features/index.md` is read from under `docs` as
normal, but the entries ending in `.feature` are read from the `features`
directory in the project root.

Any features that are not explicitly listed in the expected heading are
populated at the end of the heading.

To control the placement of the top-level features heading without otherwise adjusting
its contents, insert it into the navigation as a blank heading:
```yaml
nav:
  - A heading:
    - ...
  - Features: []
  - Another heading:
    - ...
```

#### 3. Fully manual feature population

Set `populate: false` to lay out features in the navigation entirely manually.
A warning will be issued if feature files present on disk are missing from the
navigation, mirroring the behaviour of MkDocs for Markdown files.

To disable this and allow only a subset of features to be included, set
`warn_missing: false`


## Licence

`mkdocs-behave` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) licence.
