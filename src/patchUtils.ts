import * as vscode from 'vscode';

export interface ParsedPatch {
    targetFile: string;
    oldLines: string[];
    newLines: string[];
}

/**
 * Parse unified diff format patch content
 * Supports both standard unified diff and simplified format
 */
export function parsePatch(patchContent: string): ParsedPatch[] {
    const patches: ParsedPatch[] = [];
    const lines = patchContent.split('\n');

    // Check for simplified format
    if (patchContent.includes('*** Begin Patch') || patchContent.includes('*** Update File:')) {
        return parseSimplifiedPatch(patchContent);
    }

    // Parse standard unified diff format
    let currentTargetFile: string | null = null;
    let allOldLines: string[] = [];
    let allNewLines: string[] = [];
    let inHunk = false;
    let oldLineNum = 0;
    let newLineNum = 0;
    let oldLineCount = 0;
    let newLineCount = 0;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Look for patch header: --- file_path
        if (line.startsWith('--- ')) {
            // Save previous patch if exists
            if (currentTargetFile && (allOldLines.length > 0 || allNewLines.length > 0)) {
                patches.push({
                    targetFile: currentTargetFile,
                    oldLines: allOldLines,
                    newLines: allNewLines
                });
            }

            // Extract target file path
            const match = line.match(/^---\s+(.+)$/);
            if (match) {
                currentTargetFile = match[1].trim();
                // Remove leading a/ or b/ if present (git diff format)
                if (currentTargetFile.startsWith('a/')) {
                    currentTargetFile = currentTargetFile.substring(2);
                } else if (currentTargetFile.startsWith('b/')) {
                    currentTargetFile = currentTargetFile.substring(2);
                }
            }
            allOldLines = [];
            allNewLines = [];
            inHunk = false;
            continue;
        }

        // Look for +++ file_path (optional, can be different from ---)
        if (line.startsWith('+++ ')) {
            const match = line.match(/^\+\+\+\s+(.+)$/);
            if (match && !currentTargetFile) {
                currentTargetFile = match[1].trim();
                if (currentTargetFile.startsWith('b/')) {
                    currentTargetFile = currentTargetFile.substring(2);
                }
            }
            continue;
        }

        // Look for hunk header: @@ -old_start,old_count +new_start,new_count @@
        if (line.startsWith('@@')) {
            const hunkMatch = line.match(/^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@/);
            if (hunkMatch) {
                oldLineNum = parseInt(hunkMatch[1], 10);
                oldLineCount = parseInt(hunkMatch[2] || '1', 10);
                newLineNum = parseInt(hunkMatch[3], 10);
                newLineCount = parseInt(hunkMatch[4] || '1', 10);
                inHunk = true;
                continue;
            }
        }

        // Process hunk lines
        if (inHunk && currentTargetFile) {
            if (line.startsWith('-') && !line.startsWith('--')) {
                // Removed line
                allOldLines.push(line.substring(1));
            } else if (line.startsWith('+') && !line.startsWith('++')) {
                // Added line
                allNewLines.push(line.substring(1));
            } else if (line.startsWith(' ')) {
                // Context line (unchanged)
                const contextLine = line.substring(1);
                allOldLines.push(contextLine);
                allNewLines.push(contextLine);
            }
        }
    }

    // Add last patch if exists
    if (currentTargetFile && (allOldLines.length > 0 || allNewLines.length > 0)) {
        patches.push({
            targetFile: currentTargetFile,
            oldLines: allOldLines,
            newLines: allNewLines
        });
    }

    return patches;
}

/**
 * Parse simplified patch format:
 * *** Begin Patch
 * *** Update File: file_path
 * +line
 * -line
 * *** End Patch
 */
function parseSimplifiedPatch(patchContent: string): ParsedPatch[] {
    const patches: ParsedPatch[] = [];
    const lines = patchContent.split('\n');
    let currentFile: string | null = null;
    const oldLines: string[] = [];
    const newLines: string[] = [];
    let inPatch = false;

    for (const line of lines) {
        // Look for patch start
        if (line.includes('*** Begin Patch') || line.includes('*** Update File:')) {
            if (inPatch && currentFile && (oldLines.length > 0 || newLines.length > 0)) {
                patches.push({ targetFile: currentFile, oldLines: [...oldLines], newLines: [...newLines] });
                oldLines.length = 0;
                newLines.length = 0;
            }
            inPatch = true;
            const fileMatch = line.match(/\*\*\*\s+Update\s+File:\s*(.+)/);
            if (fileMatch) {
                currentFile = fileMatch[1].trim();
            }
            continue;
        }

        // Look for patch end
        if (line.includes('*** End Patch')) {
            if (inPatch && currentFile && (oldLines.length > 0 || newLines.length > 0)) {
                patches.push({ targetFile: currentFile, oldLines: [...oldLines], newLines: [...newLines] });
                oldLines.length = 0;
                newLines.length = 0;
            }
            inPatch = false;
            continue;
        }

        // Parse patch lines
        if (inPatch && currentFile) {
            if (line.startsWith('-') && !line.startsWith('--')) {
                oldLines.push(line.substring(1));
            } else if (line.startsWith('+') && !line.startsWith('++')) {
                newLines.push(line.substring(1));
            } else if (line.startsWith(' ')) {
                const contextLine = line.substring(1);
                oldLines.push(contextLine);
                newLines.push(contextLine);
            }
        }
    }

    // Handle case where patch doesn't end with "*** End Patch"
    if (inPatch && currentFile && (oldLines.length > 0 || newLines.length > 0)) {
        patches.push({ targetFile: currentFile, oldLines: [...oldLines], newLines: [...newLines] });
    }

    return patches;
}

/**
 * Apply patch to text content, generating afterText
 */
export function applyPatchToText(text: string, patchContent: string, targetFilePath?: string): string {
    const patches = parsePatch(patchContent);
    
    if (patches.length === 0) {
        throw new Error('No valid patches found in patch content');
    }

    // Use first patch (or match by targetFilePath if provided)
    let patch: ParsedPatch | undefined;
    if (targetFilePath && patches.length > 1) {
        patch = patches.find(p => p.targetFile === targetFilePath || p.targetFile.endsWith(targetFilePath));
    }
    if (!patch) {
        patch = patches[0];
    }

    const lines = text.split('\n');
    const oldLines = patch.oldLines;
    const newLines = patch.newLines;

    // If patch is pure addition (no old lines), append to end
    if (oldLines.length === 0 && newLines.length > 0) {
        return text + (text.endsWith('\n') ? '' : '\n') + newLines.join('\n');
    }

    // Find the location to apply the patch
    let patchStart = -1;

    // Try exact match first
    for (let i = 0; i <= lines.length - oldLines.length; i++) {
        let match = true;
        for (let j = 0; j < oldLines.length; j++) {
            if (lines[i + j] !== oldLines[j]) {
                match = false;
                break;
            }
        }
        if (match) {
            patchStart = i;
            break;
        }
    }

    // If exact match not found, try fuzzy match
    if (patchStart === -1) {
        let bestMatch = -1;
        let bestScore = 0;

        for (let i = 0; i <= lines.length - oldLines.length; i++) {
            let matchCount = 0;
            for (let j = 0; j < oldLines.length && i + j < lines.length; j++) {
                if (lines[i + j] === oldLines[j]) {
                    matchCount++;
                }
            }
            const score = matchCount / oldLines.length;
            if (score > bestScore && score >= 0.5) {
                bestScore = score;
                bestMatch = i;
            }
        }

        if (bestMatch >= 0) {
            patchStart = bestMatch;
        } else {
            throw new Error('Could not find patch location in file. Expected context not found.');
        }
    }

    // Apply the patch
    const result = [
        ...lines.slice(0, patchStart),
        ...newLines,
        ...lines.slice(patchStart + oldLines.length)
    ];

    return result.join('\n');
}

/**
 * Compute TextEdit array from two text contents
 * Uses a simple approach: replace the entire document if texts differ
 */
export function computeTextEdits(fromText: string, toText: string): vscode.TextEdit[] {
    // If texts are identical, no edits needed
    if (fromText === toText) {
        return [];
    }

    const fromLines = fromText.split('\n');
    const lastLine = fromLines.length - 1;
    const lastChar = fromLines[lastLine]?.length || 0;

    // Replace entire document with new content
    // This is simpler and more reliable than trying to compute minimal diffs
    return [
        new vscode.TextEdit(
            new vscode.Range(
                new vscode.Position(0, 0),
                new vscode.Position(lastLine, lastChar)
            ),
            toText
        )
    ];
}

