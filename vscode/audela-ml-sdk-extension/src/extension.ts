import * as vscode from "vscode";

const DOCS_URL = "https://audeladedonnees.fr/docs/ml-sdk";

function activeEditorOrWarn(): vscode.TextEditor | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    void vscode.window.showWarningMessage("Open a notebook/script editor first.");
  }
  return editor;
}

export function activate(context: vscode.ExtensionContext): void {
  const openDocs = vscode.commands.registerCommand("audelaMlSdk.openDocs", async () => {
    await vscode.env.openExternal(vscode.Uri.parse(DOCS_URL));
  });

  const insertBootstrap = vscode.commands.registerCommand("audelaMlSdk.insertNotebookBootstrap", async () => {
    const editor = activeEditorOrWarn();
    if (!editor) {
      return;
    }
    const snippet = new vscode.SnippetString(
      [
        "from pathlib import Path",
        "import sys, os",
        "",
        "sys.path.insert(0, str(Path.cwd().parent / \"src\"))",
        "from audela_sdk import AudelaNotebookSDK, MODEL_BUILDERS",
        "",
        "sdk = AudelaNotebookSDK(",
        "    base_url=\"https://audeladedonnees.fr\",",
        "    session_cookie=os.environ.get(\"AUDELA_SESSION_COOKIE\", \"\"),",
        ")",
        "",
        "sources = sdk.list_bi_sources()",
        "print(sources)",
        ""
      ].join("\n")
    );

    await editor.insertSnippet(snippet, editor.selection.active);
  });

  const insertTrainAndRegister = vscode.commands.registerCommand("audelaMlSdk.insertTrainAndRegister", async () => {
    const editor = activeEditorOrWarn();
    if (!editor) {
      return;
    }
    const snippet = new vscode.SnippetString(
      [
        "result = sdk.train_and_register(",
        "    model_name=\"$1\",",
        "    algorithm=\"linear_regression\",",
        "    source_id=$2,",
        "    sql_text=\"$3\",",
        "    x_column=\"$4\",",
        "    y_column=\"$5\",",
        "    builder_kwargs={\"slope\": $6, \"intercept\": $7},",
        "    metrics={\"r2\": $8},",
        "    params={\"origin\": \"vscode-extension\"}",
        ")",
        "print(result)",
        ""
      ].join("\n")
    );

    await editor.insertSnippet(snippet, editor.selection.active);
  });

  context.subscriptions.push(openDocs, insertBootstrap, insertTrainAndRegister);
}

export function deactivate(): void {
  // no-op
}
