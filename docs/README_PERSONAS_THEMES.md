# Katamari Themes & Persona Pack
**Updated**: 2025-10-19 JST

## Use a theme preset
```bash
# Choose one preset
cp themes/katamari-minty.theme.json public/theme.json
# or:
cp themes/katamari-classic.theme.json public/theme.json
cp themes/katamari-mocha.theme.json public/theme.json
cp themes/katamari-highcontrast.theme.json public/theme.json
```

If UI is not updated, clear browser cache.

## Optional CSS overrides
- Additional tweaks in `public/stylesheet.css`.
- Ensure `.chainlit/config.toml` contains:
```toml
[UI]
custom_css = "/public/stylesheet.css"
```

## Personas
- `personas/*.yaml` を Settings の `persona_yaml` に貼るだけで即適用可能。
- まずは `01_concise_engineer.yaml` or `12_minimal_assistant.yaml` が無難。
