import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { marked } from 'marked';
import { applyPatchToText } from './patchUtils';

export class ChatPanel {
    private chatHistory: Array<{ role: string; content: string }> = [];
    private currentPatchSessionId: string | null = null;
    private sessionId: string;
    private agentType: string = 'react'; // Default to react

    constructor(
        private readonly webview: vscode.Webview,
        private readonly extensionUri: vscode.Uri,
        private readonly extensionPath?: string,
        private readonly outputChannel?: vscode.OutputChannel
    ) {
        // Don't update here, wait for webview to be ready
        this.sessionId = this.createSessionId();
    }

    public async sendMessage(userMessage: string) {
        if (!userMessage.trim()) {
            return;
        }

        // Add user message to history
        this.chatHistory.push({ role: 'user', content: userMessage });
        
        // Send user message to frontend directly (don't call update() to avoid clearing dynamic messages)
        this.webview.postMessage({
            command: 'addEvent',
            event: {
                type: 'user_message',
                message: userMessage
            }
        });

        try {
            // Call Python AI service (events will be streamed and displayed automatically)
            const aiResponse = await this.callPythonAI(userMessage);
            
            // Add final response to history (for future reference, but don't update HTML)
            this.chatHistory.push({ role: 'assistant', content: aiResponse });
            // Don't call update() - all events are added dynamically via addEvent
        } catch (error: any) {
            const errorMessage = error.message || 'Failed to get AI response';
            this.chatHistory.push({ 
                role: 'assistant', 
                content: `Error: ${errorMessage}` 
            });
            // Send error message to frontend
            this.webview.postMessage({
                command: 'addEvent',
                event: {
                    type: 'error',
                    message: `Error: ${errorMessage}`
                }
            });
        }
    }

    public clearChat() {
        this.chatHistory = [];
        this.currentPatchSessionId = null;
        this.sessionId = this.createSessionId();
        this.update();
    }

    public setAgentType(agentType: string) {
        this.agentType = agentType;
        if (this.outputChannel) {
            this.outputChannel.appendLine(`Agent type changed to: ${agentType}`);
        }
    }

    public hidePatchButtons() {
        this.currentPatchSessionId = null;
        this.webview.postMessage({
            command: 'hidePatchButtons'
        });
    }

    public dispose() {
        // Cleanup if needed
    }

    private async handleApplyPatchToolCall(msg: any): Promise<void> {
        try {
            const toolArgs = msg.tool_args || {};
            const patchContent = toolArgs.patch_content;
            const targetFilePath = toolArgs.target_file_path;

            if (!patchContent || !targetFilePath) {
                console.warn('apply_patch tool_call missing required parameters');
                return;
            }

            // Resolve target file URI
            let targetUri: vscode.Uri;
            if (path.isAbsolute(targetFilePath)) {
                targetUri = vscode.Uri.file(targetFilePath);
            } else {
                // Relative path - resolve from workspace
                const workspaceFolders = vscode.workspace.workspaceFolders;
                if (!workspaceFolders || workspaceFolders.length === 0) {
                    throw new Error('No workspace folder found');
                }
                const workspaceDir = workspaceFolders[0].uri.fsPath;
                targetUri = vscode.Uri.file(path.join(workspaceDir, targetFilePath));
            }

            // Read current file content as beforeText
            let beforeText: string;
            try {
                const doc = await vscode.workspace.openTextDocument(targetUri);
                beforeText = doc.getText();
            } catch (error: any) {
                // File might not exist yet - use empty string
                if (error.code === 'ENOENT' || error.message.includes('not found')) {
                    beforeText = '';
                } else {
                    throw error;
                }
            }

            // Apply patch to generate afterText
            const afterText = applyPatchToText(beforeText, patchContent, targetFilePath);

            // Generate session ID and store it
            const sessionId = String(Date.now());
            
            // Hide previous patch buttons if any (only if there was a previous patch)
            if (this.currentPatchSessionId) {
                this.hidePatchButtons();
            }
            
            // Update current patch session ID
            this.currentPatchSessionId = sessionId;
            
            // Store patch session
            const { patchSessions } = await import('./patchPreview');
            patchSessions.set(sessionId, {
                beforeText,
                afterText,
                targetUri,
                patchContent
            });

            // Automatically apply patch to code (preview mode)
            const { computeTextEdits } = await import('./patchUtils');
            const doc = await vscode.workspace.openTextDocument(targetUri);
            const currentText = doc.getText();
            const edits = computeTextEdits(currentText, afterText);
            const edit = new vscode.WorkspaceEdit();
            edit.set(targetUri, edits);
            await vscode.workspace.applyEdit(edit);

            // Show patch preview
            await vscode.commands.executeCommand(
                'aiChat.showPatchPreview',
                targetUri,
                beforeText,
                afterText,
                patchContent
            );

            // Notify frontend to show accept/reject buttons
            const relativePath = vscode.workspace.asRelativePath(targetUri, false);
            this.webview.postMessage({
                command: 'showPatchButtons',
                sessionId: sessionId,
                filePath: relativePath
            });
        } catch (error: any) {
            console.error('Error handling apply_patch tool_call:', error);
            if (this.outputChannel) {
                this.outputChannel.appendLine(`[ERROR] Failed to handle apply_patch: ${error.message}`);
            }
            vscode.window.showErrorMessage(`Failed to show patch preview: ${error.message}`);
        }
    }

    private async handleSearchReplaceToolCall(msg: any): Promise<void> {
        try {
            const toolArgs = msg.tool_args || {};
            const filePath = toolArgs.file_path;
            const startLineContent = toolArgs.start_line_content;
            const endLineContent = toolArgs.end_line_content;
            const newString = toolArgs.new_string;

            if (!filePath || startLineContent === undefined || endLineContent === undefined || newString === undefined) {
                console.warn('search_replace tool_call missing required parameters');
                return;
            }

            // Resolve target file URI
            let targetUri: vscode.Uri;
            if (path.isAbsolute(filePath)) {
                targetUri = vscode.Uri.file(filePath);
            } else {
                // Relative path - resolve from workspace
                const workspaceFolders = vscode.workspace.workspaceFolders;
                if (!workspaceFolders || workspaceFolders.length === 0) {
                    throw new Error('No workspace folder found');
                }
                const workspaceDir = workspaceFolders[0].uri.fsPath;
                targetUri = vscode.Uri.file(path.join(workspaceDir, filePath));
            }

            // Read current file content as beforeText
            let beforeText: string;
            try {
                const doc = await vscode.workspace.openTextDocument(targetUri);
                beforeText = doc.getText();
            } catch (error: any) {
                // File might not exist yet - use empty string
                if (error.code === 'ENOENT' || error.message.includes('not found')) {
                    beforeText = '';
                } else {
                    throw error;
                }
            }

            // Apply search_replace to generate afterText
            // Find lines matching start_line_content and end_line_content
            const lines = beforeText.split('\n');
            const normalizeLine = (line: string) => line.replace(/\s+$/, ''); // Remove trailing whitespace
            
            let startLineIdx = -1;
            let endLineIdx = -1;
            
            // Find start line
            for (let i = 0; i < lines.length; i++) {
                if (normalizeLine(lines[i]) === normalizeLine(startLineContent)) {
                    startLineIdx = i;
                    break;
                }
            }
            
            if (startLineIdx === -1) {
                console.warn(`search_replace: start_line_content not found in file ${filePath}`);
                return;
            }
            
            // Find end line (must be after start line)
            for (let i = startLineIdx; i < lines.length; i++) {
                if (normalizeLine(lines[i]) === normalizeLine(endLineContent)) {
                    endLineIdx = i;
                    break;
                }
            }
            
            if (endLineIdx === -1) {
                console.warn(`search_replace: end_line_content not found after start line in file ${filePath}`);
                return;
            }
            
            // Generate afterText by replacing lines from startLineIdx to endLineIdx
            const linesBefore = lines.slice(0, startLineIdx);
            const newLines = newString.split('\n');
            const linesAfter = lines.slice(endLineIdx + 1);
            const afterText = [...linesBefore, ...newLines, ...linesAfter].join('\n');

            // Generate session ID and store it
            const sessionId = String(Date.now());
            
            // Hide previous patch buttons if any (only if there was a previous patch)
            if (this.currentPatchSessionId) {
                this.hidePatchButtons();
            }
            
            // Update current patch session ID
            this.currentPatchSessionId = sessionId;
            
            // Store patch session (reuse patch preview infrastructure)
            const { patchSessions } = await import('./patchPreview');
            patchSessions.set(sessionId, {
                beforeText,
                afterText,
                targetUri,
                patchContent: `search_replace: ${filePath}`
            });

            // Automatically apply changes to code (preview mode)
            const { computeTextEdits } = await import('./patchUtils');
            const doc = await vscode.workspace.openTextDocument(targetUri);
            const currentText = doc.getText();
            const edits = computeTextEdits(currentText, afterText);
            const edit = new vscode.WorkspaceEdit();
            edit.set(targetUri, edits);
            await vscode.workspace.applyEdit(edit);

            // Show patch preview
            await vscode.commands.executeCommand(
                'aiChat.showPatchPreview',
                targetUri,
                beforeText,
                afterText,
                `search_replace: ${filePath}`
            );

            // Notify frontend to show accept/reject buttons
            const relativePath = vscode.workspace.asRelativePath(targetUri, false);
            this.webview.postMessage({
                command: 'showPatchButtons',
                sessionId: sessionId,
                filePath: relativePath
            });
        } catch (error: any) {
            console.error('Error handling search_replace tool_call:', error);
            if (this.outputChannel) {
                this.outputChannel.appendLine(`[ERROR] Failed to handle search_replace: ${error.message}`);
            }
            vscode.window.showErrorMessage(`Failed to show search_replace preview: ${error.message}`);
        }
    }

    private async callPythonAI(message: string): Promise<string> {
        return new Promise((resolve, reject) => {
            let command;
            try {
                command = this.preparePythonCommand();
            } catch (error) {
                reject(error);
                return;
            }
            const { resolvedPythonPath, aiScriptPath, workspaceDir } = command;

            const pythonProcess = spawn(resolvedPythonPath, [aiScriptPath], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let output = '';
            let errorOutput = '';

            // Add separator to output channel for this request
            if (this.outputChannel) {
                const timestamp = new Date().toLocaleString();
                this.outputChannel.appendLine(`\n${'='.repeat(80)}`);
                this.outputChannel.appendLine(`[${timestamp}] Processing request: ${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`);
                this.outputChannel.appendLine('='.repeat(80));
            }

            const requestData: any = {
                message: message,
                session_id: this.sessionId,
                agent_type: this.agentType
            };
            if (workspaceDir) {
                requestData.workspace_dir = workspaceDir;
            }
            
            pythonProcess.stdin.write(JSON.stringify(requestData));
            pythonProcess.stdin.end();

            // Buffer for incomplete lines
            let buffer = '';
            let finalMessage = '';

            // Collect output line by line (streaming JSON)
            pythonProcess.stdout.on('data', (data: Buffer) => {
                buffer += data.toString();
                const lines = buffer.split('\n');
                // Keep the last incomplete line in buffer
                buffer = lines.pop() || '';

                // Process each complete line
                for (const line of lines) {
                    if (!line.trim()) continue;
                    
                    try {
                        const msg = JSON.parse(line);
                        // Directly pass the event to frontend, no transformation needed
                        this.webview.postMessage({
                            command: 'addEvent',
                            event: msg
                        });

                        // Handle apply_patch tool_call - show preview
                        if (msg.type === 'tool_call' && msg.tool_name === 'apply_patch') {
                            this.handleApplyPatchToolCall(msg).catch(error => {
                                console.error('Error handling apply_patch tool_call:', error);
                                if (this.outputChannel) {
                                    this.outputChannel.appendLine(`[ERROR] Failed to handle apply_patch: ${error.message}`);
                                }
                            });
                        }

                        // Handle search_replace tool_call - show preview
                        if (msg.type === 'tool_call' && msg.tool_name === 'search_replace') {
                            this.handleSearchReplaceToolCall(msg).catch(error => {
                                console.error('Error handling search_replace tool_call:', error);
                                if (this.outputChannel) {
                                    this.outputChannel.appendLine(`[ERROR] Failed to handle search_replace: ${error.message}`);
                                }
                            });
                        }

                        // Track final message for history
                        if (msg.type === 'final_message') {
                            finalMessage = msg.message || '';
                            // Don't clear patch buttons on final message - keep them visible
                        }
                    } catch (e) {
                        // If JSON parsing fails, log but continue
                        if (this.outputChannel) {
                            this.outputChannel.appendLine(`[WARN] Failed to parse message line: ${line}`);
                        }
                    }
                }
            });

            // Send stderr logs to OutputChannel
            pythonProcess.stderr.on('data', (data: Buffer) => {
                const logMessage = data.toString();
                errorOutput += logMessage;
                
                // Output to VS Code OutputChannel for better visibility
                if (this.outputChannel) {
                    this.outputChannel.append(logMessage);
                }
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code === 0) {
                    // Process any remaining buffer
                    if (buffer.trim()) {
                        try {
                            const msg = JSON.parse(buffer.trim());
                            this.webview.postMessage({
                                command: 'addEvent',
                                event: msg
                            });
                            if (msg.type === 'final_message' && msg.message) {
                                finalMessage = msg.message;
                            }
                        } catch (e) {
                            // Ignore parse errors for remaining buffer
                        }
                    }

                    if (this.outputChannel) {
                        this.outputChannel.appendLine(`[SUCCESS] Request completed successfully\n`);
                    }
                    
                    // Resolve with final message (or empty if none)
                    resolve(finalMessage || '');
                } else {
                    const errorMsg = errorOutput || `Python process exited with code ${code}`;
                    if (this.outputChannel) {
                        this.outputChannel.appendLine(`[ERROR] Python process error (exit code ${code}): ${errorMsg}\n`);
                        this.outputChannel.show(true); // Show output channel on error
                    }
                    reject(new Error(errorMsg));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                const errorMsg = `Failed to start Python process: ${error.message}`;
                if (this.outputChannel) {
                    this.outputChannel.appendLine(`ERROR: ${errorMsg}`);
                }
                reject(new Error(errorMsg));
            });

            // // Timeout after 30 seconds
            // setTimeout(() => {
            //     pythonProcess.kill();
            //     reject(new Error('AI request timed out'));
            // }, 30000);
        });
    }

    private preparePythonCommand() {
        const config = vscode.workspace.getConfiguration('aiChat');
        let pythonPath = config.get<string>('pythonPath', '.venv/bin/python');
        let extPath = this.extensionPath;
        if (!extPath) {
            if (this.extensionUri.scheme === 'file') {
                extPath = path.dirname(path.dirname(this.extensionUri.fsPath));
            } else {
                throw new Error('Extension path is not set and cannot be determined');
            }
        }

        const defaultScriptPath = path.join(extPath, 'python', 'ai_service.py');
        if (!fs.existsSync(defaultScriptPath)) {
            console.error('Python script not found at:', defaultScriptPath);
        }

        let aiScriptPath = config.get<string>('aiScriptPath');
        if (!aiScriptPath) {
            aiScriptPath = defaultScriptPath;
        }
        if (!path.isAbsolute(aiScriptPath)) {
            aiScriptPath = path.join(extPath, aiScriptPath);
        }

        let resolvedPythonPath = pythonPath;
        if (!path.isAbsolute(pythonPath)) {
            resolvedPythonPath = path.join(extPath, pythonPath);
        }

        const workspaceFolders = vscode.workspace.workspaceFolders;
        const workspaceDir = workspaceFolders && workspaceFolders.length > 0
            ? workspaceFolders[0].uri.fsPath
            : undefined;

        return { resolvedPythonPath, aiScriptPath, workspaceDir };
    }

    private requestHistory(): Promise<void> {
        return new Promise((resolve, reject) => {
            let command;
            try {
                command = this.preparePythonCommand();
            } catch (error) {
                reject(error);
                return;
            }

            const { resolvedPythonPath, aiScriptPath, workspaceDir } = command;
            const pythonProcess = spawn(resolvedPythonPath, [aiScriptPath], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data: Buffer) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data: Buffer) => {
                const log = data.toString();
                stderr += log;
                if (this.outputChannel) {
                    this.outputChannel.append(log);
                }
            });

            const requestData: any = {
                request_type: 'history',
                session_id: this.sessionId
            };
            if (workspaceDir) {
                requestData.workspace_dir = workspaceDir;
            }

            pythonProcess.stdin.write(JSON.stringify(requestData));
            pythonProcess.stdin.end();

            pythonProcess.on('close', (code: number | null) => {
                if (code === 0) {
                    const lines = stdout.split('\n').map(line => line.trim()).filter(Boolean);
                    for (const line of lines) {
                        try {
                            const msg = JSON.parse(line);
                            if (msg.type === 'history') {
                                this.webview.postMessage({
                                    command: 'loadHistory',
                                    history: Array.isArray(msg.history) ? msg.history : []
                                });
                                resolve();
                                return;
                            }
                        } catch (error) {
                            continue;
                        }
                    }
                    resolve();
                } else {
                    reject(new Error(stderr || `Python process exited with code ${code}`));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                reject(error);
            });
        });
    }

    public async loadHistoryFromBackend(): Promise<void> {
        try {
            await this.requestHistory();
        } catch (error: any) {
            console.error('Failed to load history:', error);
            if (this.outputChannel) {
                this.outputChannel.appendLine(`[ERROR] Failed to load history: ${error.message}`);
            }
        }
    }

    public update() {
        const webview = this.webview;
        webview.html = this.getHtmlForWebview(webview);
        this.loadHistoryFromBackend().catch(() => {});
    }

    private getHtmlForWebview(webview: vscode.Webview) {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.extensionUri, 'media', 'chat.css')
        );

        const nonce = this.getNonce();

        // Configure marked options for better security and rendering
        marked.setOptions({
            breaks: true,
            gfm: true,
        });

        // Get marked library script content
        const markedScript = this.getMarkedScript(webview);

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="${styleUri}" rel="stylesheet">
                <title>AI Chat</title>
            </head>
            <body>
                <div class="chat-container">
                    <div class="chat-messages" id="chatMessages">
                        ${this.chatHistory.map(msg => `
                            <div class="message ${msg.role}">
                                <div class="message-content">${this.renderMarkdown(msg.content)}</div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="patch-buttons-container" id="patchButtonsContainer" style="display: none;">
                        <div class="patch-buttons-info">
                            <span id="patchFilePath"></span>
                        </div>
                        <div class="patch-buttons">
                            <button id="acceptPatchButton" class="patch-button accept">Accept</button>
                            <button id="rejectPatchButton" class="patch-button reject">Reject</button>
                        </div>
                    </div>
                    <div class="agent-selector-container">
                        <label for="agentTypeSelect">Agent Mode:</label>
                        <select id="agentTypeSelect">
                            <option value="react">ReAct (Fast, Reactive)</option>
                            <option value="planact">PlanAct (Planned, Complex Tasks)</option>
                        </select>
                    </div>
                    <div class="chat-input-container">
                        <textarea 
                            id="messageInput" 
                            placeholder="Type your message here..."
                            rows="2"
                        ></textarea>
                        <button id="sendButton">Send</button>
                    </div>
                </div>
                <script nonce="${nonce}">
                    ${markedScript}
                    
                    const vscode = acquireVsCodeApi();
                    const chatHistory = ${JSON.stringify(this.chatHistory)};
                    
                    const chatMessages = document.getElementById('chatMessages');
                    const messageInput = document.getElementById('messageInput');
                    const sendButton = document.getElementById('sendButton');
                    const agentTypeSelect = document.getElementById('agentTypeSelect');
                    const patchButtonsContainer = document.getElementById('patchButtonsContainer');
                    const patchFilePath = document.getElementById('patchFilePath');
                    const acceptPatchButton = document.getElementById('acceptPatchButton');
                    const rejectPatchButton = document.getElementById('rejectPatchButton');
                    let currentPatchSessionId = null;
                    let historyLoaded = false;
                    
                    // Markdown renderer function
                    function renderMarkdown(text) {
                        if (!text || typeof text !== 'string') {
                            return '';
                        }
                        try {
                            if (typeof marked !== 'undefined') {
                                return marked.parse(text);
                            } else {
                                // Fallback: simple markdown-like rendering
                                const backtick = String.fromCharCode(96);
                                return text
                                    .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
                                    .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
                                    .replace(new RegExp(backtick + '([^' + backtick + ']+)' + backtick, 'g'), '<code>$1</code>')
                                    .replace(/\\n/g, '<br>');
                            }
                        } catch (e) {
                            console.error('Markdown rendering error:', e);
                            return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\\n/g, '<br>');
                        }
                    }
                    
                    function scrollToBottom() {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    
                    function renderEvent(evt) {
                        const msgDiv = document.createElement('div');
                        let className = 'message';

                        if (evt.type === 'user_message') {
                            className += ' user';
                        } else {
                            className += ' assistant';
                        }

                        if (evt.type === 'tool_call') {
                            className += ' tool-call';
                        } else if (evt.type === 'tool_result') {
                            className += ' tool-result';
                        } else if (evt.type === 'error') {
                            className += ' error';
                        }

                        // Add agent color class based on is_parent and agent_index
                        if (evt.is_parent === true) {
                            className += ' agent-parent';
                        } else if (evt.is_parent === false && evt.agent_index !== null && evt.agent_index !== undefined) {
                            // Child agent: use agent_index % 8 to cycle through 8 colors
                            const colorIndex = evt.agent_index % 8;
                            className += ' agent-child-' + colorIndex;
                        }

                        msgDiv.className = className;

                        let contentHtml = '';
                        if (evt.type === 'tool_call' || evt.type === 'tool_result') {
                            const toolName = evt.tool_name || 'unknown';
                            let toolLabel;
                            if (evt.type === 'tool_call') {
                                toolLabel = '🔧 Calling Tool';
                            } else {
                                // For tool_result, check if execution was successful
                                const result = evt.result || {};
                                const returncode = result.returncode;
                                const success = result.success;
                                
                                // Determine if tool execution was successful:
                                // - If returncode exists, it must be 0 for success
                                // - If returncode doesn't exist, check success field
                                // - If error field exists, it's a failure
                                let isSuccessful = false;
                                if (result.error !== undefined) {
                                    // Has error field, definitely failed
                                    isSuccessful = false;
                                } else if (returncode !== undefined) {
                                    // Has returncode, check if it's 0
                                    isSuccessful = returncode === 0;
                                } else if (success !== undefined) {
                                    // No returncode, check success field
                                    isSuccessful = success === true;
                                } else {
                                    // No success indicators, assume successful (backward compatibility)
                                    isSuccessful = true;
                                }
                                
                                toolLabel = isSuccessful ? '✅ Tool Completed' : '⚠️ Tool Completed';
                            }
                            contentHtml = '<div class="tool-header"><strong>' + toolLabel + ':</strong> <code>' + toolName + '</code></div>';
                            if (evt.message) {
                                contentHtml += '<div class="tool-message">' + renderMarkdown(evt.message) + '</div>';
                            }
                        } else if (evt.type === 'user_message') {
                            contentHtml = renderMarkdown(evt.message || '');
                        } else if (evt.type === 'error') {
                            contentHtml = '<strong>Error:</strong> ' + renderMarkdown(evt.message || '');
                        } else {
                            if (evt.type === 'notification_message') {
                                contentHtml = '<em>' + (evt.message || 'Thinking...') + '</em>';
                            } else {
                                contentHtml = renderMarkdown(evt.message || '');
                            }
                        }

                        msgDiv.innerHTML = '<div class="message-content">' + contentHtml + '</div>';
                        chatMessages.appendChild(msgDiv);
                        scrollToBottom();
                    }
                    
                    function sendMessage() {
                        const text = messageInput.value.trim();
                        if (text) {
                            vscode.postMessage({
                                command: 'sendMessage',
                                text: text
                            });
                            messageInput.value = '';
                        }
                    }
                    
                    sendButton.addEventListener('click', sendMessage);
                    messageInput.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            sendMessage();
                        }
                    });
                    
                    // Handle agent type selection change
                    agentTypeSelect.addEventListener('change', (e) => {
                        const selectedType = e.target.value;
                        vscode.postMessage({
                            command: 'changeAgentType',
                            agentType: selectedType
                        });
                    });
                    
                    // Handle messages from extension
                    window.addEventListener('message', event => {
                        const data = event.data;
                        switch (data.command) {
                            case 'addEvent': {
                                renderEvent(data.event);
                                break;
                            }
                            case 'loadHistory': {
                                if (historyLoaded) {
                                    break;
                                }
                                historyLoaded = true;
                                if (chatMessages) {
                                    chatMessages.innerHTML = '';
                                }
                                const entries = Array.isArray(data.history) ? data.history : [];
                                entries.forEach(entry => {
                                    const evt = {
                                        type: entry.role === 'user' ? 'user_message' : 'notification_message',
                                        message: entry.content || '',
                                        role: entry.role
                                    };
                                    renderEvent(evt);
                                });
                                break;
                            }
                            case 'focusInput':
                                messageInput.focus();
                                break;
                            case 'clearMessages':
                                chatMessages.innerHTML = '';
                                break;
                            case 'showPatchButtons':
                                if (patchButtonsContainer && patchFilePath) {
                                    currentPatchSessionId = data.sessionId;
                                    patchFilePath.textContent = \`Patch ready for: \${data.filePath}\`;
                                    patchButtonsContainer.classList.add('show');
                                }
                                break;
                            case 'hidePatchButtons':
                                if (patchButtonsContainer) {
                                    patchButtonsContainer.classList.remove('show');
                                    currentPatchSessionId = null;
                                }
                                break;
                        }
                    });
                    
                    // Handle patch button clicks
                    if (acceptPatchButton) {
                        acceptPatchButton.addEventListener('click', () => {
                            if (currentPatchSessionId) {
                                // Save sessionId before clearing
                                const sessionIdToApply = currentPatchSessionId;
                                
                                // Hide buttons immediately
                                if (patchButtonsContainer) {
                                    patchButtonsContainer.classList.remove('show');
                                }
                                currentPatchSessionId = null;
                                
                                // Send apply command
                                vscode.postMessage({
                                    command: 'applyPatch',
                                    sessionId: sessionIdToApply
                                });
                            }
                        });
                    }
                    
                    if (rejectPatchButton) {
                        rejectPatchButton.addEventListener('click', () => {
                            if (currentPatchSessionId) {
                                // Save sessionId before clearing
                                const sessionIdToReject = currentPatchSessionId;
                                
                                // Hide buttons immediately
                                if (patchButtonsContainer) {
                                    patchButtonsContainer.classList.remove('show');
                                }
                                currentPatchSessionId = null;
                                
                                // Send reject command
                                vscode.postMessage({
                                    command: 'rejectPatch',
                                    sessionId: sessionIdToReject
                                });
                            }
                        });
                    }
                    
                    // Initial scroll
                    scrollToBottom();
                </script>
            </body>
            </html>`;
    }

    private renderMarkdown(text: string): string {
        if (!text) {
            return '';
        }
        try {
            // Configure marked for rendering
            marked.setOptions({
                breaks: true,
                gfm: true,
            });
            const result = marked.parse(text);
            // marked.parse can return string or Promise<string>
            // For our use case, we expect synchronous rendering
            return typeof result === 'string' ? result : String(result);
        } catch (error) {
            // Fallback to HTML escaping if markdown parsing fails
            return this.escapeHtml(text);
        }
    }

    private escapeHtml(text: string): string {
        const map: { [key: string]: string } = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]).replace(/\n/g, '<br>');
    }

    private getMarkedScript(webview: vscode.Webview): string {
        // Try to read marked from node_modules (different possible locations)
        const possiblePaths = [
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'lib', 'marked.esm.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'lib', 'marked.umd.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'marked.min.js'),
            path.join(this.extensionPath || '', 'node_modules', 'marked', 'marked.js'),
        ];
        
        for (const markedPath of possiblePaths) {
            try {
                if (fs.existsSync(markedPath)) {
                    const markedContent = fs.readFileSync(markedPath, 'utf-8');
                    // Wrap UMD/ESM code to work in webview context
                    if (markedPath.includes('.umd.js')) {
                        return markedContent;
                    } else if (markedPath.includes('.esm.js')) {
                        // For ESM, we need to create a simple wrapper
                        // Actually, let's use a simpler inline markdown parser for webviews
                        return this.getInlineMarkdownParser();
                    } else {
                        return markedContent;
                    }
                }
            } catch (error) {
                // Continue to next path
            }
        }
        
        // Fallback: use inline markdown parser
        return this.getInlineMarkdownParser();
    }

    private getInlineMarkdownParser(): string {
        // Simple but effective markdown parser for common cases
        // Use string concatenation to avoid template literal escaping issues
        return [
            '// Simple Markdown parser',
            '(function() {',
            '    const Marked = {};',
            '    ',
            '    Marked.parse = function(text) {',
            '        if (!text) return "";',
            '        ',
            '        let html = text;',
            '        ',
            '        // Store code blocks temporarily to avoid escaping them',
            '        const codeBlocks = [];',
            '        const inlineCodes = [];',
            '        const backtick = String.fromCharCode(96);',
            '        const backtick3 = backtick + backtick + backtick;',
            '        html = html.replace(new RegExp(backtick3 + \'([\\\\s\\\\S]*?)\' + backtick3, \'g\'), function(match, code) {',
            "            const placeholder = '___CODE_BLOCK_' + codeBlocks.length + '___';",
            "            codeBlocks.push('<pre><code>' + escapeHtml(code.trim()) + '</code></pre>');",
            '            return placeholder;',
            '        });',
            '        ',
            '        // Store inline code temporarily',
            '        html = html.replace(new RegExp(backtick + \'([^\' + backtick + \'\\\\n]+)\' + backtick, \'g\'), function(match, code) {',
            "            const placeholder = '___INLINE_CODE_' + inlineCodes.length + '___';",
            "            inlineCodes.push('<code>' + escapeHtml(code) + '</code>');",
            '            return placeholder;',
            '        });',
            '        ',
            '        // Now escape HTML to prevent XSS',
            '        html = escapeHtml(html);',
            '        ',
            '        // Restore code blocks and inline code',
            '        codeBlocks.forEach(function(block, index) {',
            "            html = html.replace('___CODE_BLOCK_' + index + '___', block);",
            '        });',
            '        inlineCodes.forEach(function(code, index) {',
            "            html = html.replace('___INLINE_CODE_' + index + '___', code);",
            '        });',
            '        ',
            '        // Headers (process before other formatting)',
            "        html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>');",
            "        html = html.replace(/^## (.*)$/gm, '<h2>$1</h2>');",
            "        html = html.replace(/^# (.*)$/gm, '<h1>$1</h1>');",
            '        ',
            '        // Horizontal rules',
            "        html = html.replace(/^---$/gm, '<hr>');",
            "        html = html.replace(/^\\*\\*\\*$/gm, '<hr>');",
            '        ',
            '        // Lists (unordered) - process line by line',
            '        const lines = html.split(\'\\n\');',
            '        const result = [];',
            '        let inList = false;',
            '        ',
            '        for (let i = 0; i < lines.length; i++) {',
            '            const line = lines[i];',
            "            const listMatch = line.match(/^(\\*|-)\\s+(.+)$/);",
            '            ',
            '            if (listMatch) {',
            "                if (!inList) {",
            "                    result.push('<ul>');",
            '                    inList = true;',
            '                }',
            "                result.push('<li>' + listMatch[2] + '</li>');",
            '            } else {',
            '                if (inList) {',
            "                    result.push('</ul>');",
            '                    inList = false;',
            '                }',
            '                result.push(line);',
            '            }',
            '        }',
            '        ',
            '        if (inList) {',
            "            result.push('</ul>');",
            '        }',
            '        ',
            '        html = result.join(\'\\n\');',
            '        ',
            '        // Bold (avoid conflicts with code)',
            "        html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');",
            "        html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');",
            '        ',
            '        // Italic (avoid conflicts with bold)',
            "        html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');",
            "        html = html.replace(/_([^_]+)_/g, '<em>$1</em>');",
            '        ',
            '        // Links [text](url)',
            "        html = html.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g, '<a href=\"$2\" target=\"_blank\" rel=\"noopener noreferrer\">$1</a>');",
            '        ',
            '        // Paragraphs and line breaks',
            "        html = html.replace(/\\n\\n+/g, '</p><p>');",
            "        html = '<p>' + html + '</p>';",
            "        html = html.replace(/\\n/g, '<br>');",
            '        ',
            '        // Clean up empty paragraphs and fix block elements',
            "        html = html.replace(/<p><\\/p>/g, '');",
            "        html = html.replace(/<p>(<[^>]+>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<h[1-6]>)/g, '$1');",
            "        html = html.replace(/(<\\/h[1-6]>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<pre>)/g, '$1');",
            "        html = html.replace(/(<\\/pre>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<ul>)/g, '$1');",
            "        html = html.replace(/(<\\/ul>)<\\/p>/g, '$1');",
            "        html = html.replace(/<p>(<hr>)/g, '$1');",
            "        html = html.replace(/(<hr>)<\\/p>/g, '$1');",
            '        ',
            '        return html;',
            '    };',
            '    ',
            '    function escapeHtml(text) {',
            '        const map = {',
            "            '&': '&amp;',",
            "            '<': '&lt;',",
            "            '>': '&gt;',",
            '            \'"\': \'&quot;\',',
            "            \"'\": '&#039;'",
            '        };',
            "        return text.replace(/[&<>\"']/g, function(m) { return map[m]; });",
            '    }',
            '    ',
            '    window.marked = Marked;',
            '})();'
        ].join('\n');
    }

    private getNonce() {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }

    private createSessionId(): string {
        return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }
}

