# AUDELA ML SDK Tools (VS Code Extension)

VS Code extension that helps AUDELA users bootstrap ML SDK notebooks quickly.

## Features

- `AUDELA: Open ML SDK Docs`
  - Opens: `https://audeladedonnees.fr/docs/ml-sdk`
- `AUDELA: Insert Notebook SDK Bootstrap`
  - Inserts Python imports and SDK initialization boilerplate.
- `AUDELA: Insert train_and_register Example`
  - Inserts a ready-to-edit model registration snippet.

## Development

```bash
npm install
npm run compile
```

Press `F5` in VS Code to launch an Extension Development Host.

## Package and publish

```bash
npm install
npm run compile
npx @vscode/vsce package
```

This creates a `.vsix` file in the extension folder.

Install locally in VS Code:

```bash
code --install-extension audela-ml-sdk-tools-0.1.0.vsix
```

To publish to Marketplace (after `vsce login <publisher>`):

```bash
npx @vscode/vsce publish
```

## Notes

- `publisher` is currently set to `audela` in `package.json`.
- Update `name`, `publisher`, and icon/assets before public release.

## Marketplace checklist

- Verify `publisher` ownership in Visual Studio Marketplace.
- Update `version` before each release (semver).
- Keep `CHANGELOG.md` aligned with released changes.
- Run full build before packaging: `npm run compile`.
- Test commands in Extension Development Host (`F5`).
