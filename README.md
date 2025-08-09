# textpress — Simple publishing for complex docs

Textpress is a command‑line tool (CLI) for turning rich documents (e.g., Google Docs/.docx,
PDFs, HTML, and Markdown) into clean Markdown and beautifully formatted HTML, and then
publishing them to the Textpress web app.

- Website: [textpress.md](https://textpress.md)
- App: `https://app.textpress.md`
- GitHub: `https://github.com/jlevy/textpress`

The CLI is available as `textpress` (full name) and `tp` (alias).

This project is early but usable; feedback is welcome. Please
[start a discussion](https://github.com/jlevy/textpress/discussions) with ideas and requests.

## Installation

Requires Python >= 3.11.

Pick one of the following:

- Using uv (recommended for one‑off runs):

  ```sh
  uvx textpress --version
  ```

- Install as a tool with uv:

  ```sh
  uv tool install textpress
  # then:
  tp --help
  ```

- Using pipx:

  ```sh
  pipx install textpress
  tp --help
  ```

- Using pip (inside a virtualenv):

  ```sh
  pip install textpress
  textpress --help
  ```

If you need help setting up Python or uv, see [installation.md](installation.md).

## Quick start

1. Configure your API key (opens the app to get one):

   ```sh
   tp setup
   ```

2. Convert a .docx (e.g., exported from Gemini Deep Research → Google Docs → Download as .docx)
   to clean Markdown:

   ```sh
   tp convert ~/Downloads/'Airspeed Velocity of Unladen Birds.docx'
   less textpress/workspace/docs/airspeed_velocity_of_unladen_birds_1.doc.md
   ```

3. Format the content to pretty HTML (and preview it locally):

   ```sh
   tp format ~/Downloads/'Airspeed Velocity of Unladen Birds.docx' --show
   ```

4. Optionally edit the generated Markdown, then publish:

   ```sh
   tp format textpress/workspace/docs/airspeed_velocity_of_unladen_birds_1.doc.md --show
   tp publish textpress/workspace/docs/airspeed_velocity_of_unladen_birds_1.doc.md --show
   ```

For an overview page with examples: `tp help`

## Command reference

Run `tp --help` for the latest options. General flags (`--debug`, `--verbose`, `--quiet`,
`--work_root <path>`) work on all commands. Action flags (`--rerun`, `--refetch`) control
workspace caching.

- **setup**: Interactive setup for your API key. Stores configuration at
  `~/.config/textpress/env`. Use `--show` to display current settings.

- **help**: Shows an extended help page with workflows and examples.

- **paste**: Saves your system clipboard into a workspace file.

  - **flags**: `--title <name>` (default `pasted_text`), `--plaintext` (treat input as plain text)

- **files**: Lists files in the workspace. Add `--all` to include hidden/ignored files.

- **convert INPUT**: Converts a URL/.docx/PDF/HTML/Markdown into clean Markdown.

  - **flags**: `--show` (view result in a pager)

- **format INPUT**: Converts to clean Markdown (if needed) and renders pretty, minified HTML
  using the Textpress template. Produces both Markdown and HTML outputs.

  - **flags**: `--show` (open HTML in browser), `--add_classes "class1 class2"`, `--no_minify`

- **publish INPUT**: Runs `format`, then uploads the Markdown/HTML (and any Sidematter assets)
  to Textpress. Returns public URLs for the published files.

  - **flags**: Same as `format`. `--show` opens the public HTML page in your browser.

- **export INPUT**: Exports a clean `.docx` and `.pdf` from the Markdown version of your input.

Notes:

- Inputs can be local files or URLs; format is auto‑detected where possible.
- `tp` is an alias for `textpress`.

## Workspace and outputs

Textpress maintains a workspace and cache under a work root (default: `./textpress`).

- Work root: `--work_root <dir>` (default `./textpress`)
- Workspace path: `<work_root>/workspace`
- Outputs from `convert`, `format`, and `export` are saved under the workspace and re‑used
  unless you pass `--rerun` or `--refetch`.

On successful runs, the CLI prints where results are saved and, for `publish`, the
public URLs. Published URLs look like:

```text
https://textpress.md/<username>/d/<filename>
```

If your account username isn’t configured yet, `publish` will prompt you to run setup.

## Configuration and environment

Environment variables (read automatically by the CLI; use `tp setup` to create the config file):

- `TEXTPRESS_API_KEY` (required): Your API key.
- `TEXTPRESS_API_ROOT` (default `https://app.textpress.md`): API base URL.
- `TEXTPRESS_PUBLISH_ROOT` (default `https://textpress.md`): Public site root used for URLs.

Where configuration is read from (in order):

1. Current environment variables.
2. `~/.config/textpress/env` (created by `tp setup`).
3. Any `.env` files discoverable via
   [clideps dotenv search](https://github.com/jlevy/clideps) conventions.

You can inspect current settings with:

```sh
tp setup --show
```

## Templating and theming

`tp format`/`tp publish` render with the bundled template `textpress_webpage.html.jinja` and
support adding custom CSS classes to the main content container via `--add_classes`.
The template is mobile‑friendly, dark‑mode aware, and TOC‑aware. HTML is minified by default;
use `--no_minify` to skip minification.

## Troubleshooting

- **Missing environment variable**: If you see a message about `TEXTPRESS_API_KEY`, run `tp setup`.
- **HTTP errors**: The CLI will print the status code and log path. Re‑run with `--debug` for more
  detail.
- **PDF conversions**: Converting PDFs to Markdown is less reliable than HTML or .docx. Inspect the
  output and make manual edits before publishing if needed.

## Development

- How to install Python/uv: see [installation.md](installation.md)
- Local workflows (sync, lint, test, build): see [development.md](development.md)
- Publishing to PyPI: see [publishing.md](publishing.md)

Contributions and issue reports are welcome! Please open a PR or start a discussion.

## License

AGPL-3.0-or-later. See `pyproject.toml` for metadata.

---

This project was scaffolded from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).
