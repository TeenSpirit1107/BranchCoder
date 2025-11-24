import * as vscode from 'vscode';

export interface PatchSession {
    beforeText: string;
    afterText: string;
    targetUri: vscode.Uri;
    patchContent?: string;
}

export const patchSessions = new Map<string, PatchSession>();

export class PatchPreviewProvider implements vscode.TextDocumentContentProvider {
    private _onDidChange = new vscode.EventEmitter<vscode.Uri>();
    onDidChange = this._onDidChange.event;

    provideTextDocumentContent(uri: vscode.Uri): string {
        const sessionId = uri.path.replace(/^\//, ''); // Remove leading /
        const params = new URLSearchParams(uri.query);
        const state = params.get('state'); // before or after

        const session = patchSessions.get(sessionId);
        if (!session) {
            return `// No patch session found for id: ${sessionId}`;
        }

        if (state === 'before') {
            return session.beforeText;
        } else if (state === 'after') {
            return session.afterText;
        } else {
            return `// Unknown state: ${state}`;
        }
    }

    // Method to trigger content refresh (optional, for future use)
    refresh(uri: vscode.Uri): void {
        this._onDidChange.fire(uri);
    }
}

