import re
import ast
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class CodeChunk:
    content: str
    file_path: str
    chunk_type: str  # function, class, module, block
    name: str
    start_line: int
    end_line: int
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return f"{self.file_path}::{self.name}::{self.start_line}"


LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "shell",
    ".sql": "sql",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz", ".lock",
    ".min.js", ".min.css", ".map",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", "venv",
    ".venv", "env", "dist", "build", ".next", ".nuxt", "vendor",
    "coverage", ".coverage", "htmlcov", "eggs", ".eggs",
}

MAX_FILE_SIZE = 500_000  # 500KB
CHUNK_SIZE = 50  # lines for generic chunking
CHUNK_OVERLAP = 5  # line overlap between chunks


def detect_language(file_path: str) -> str:
    import os
    ext = os.path.splitext(file_path)[1].lower()
    # Handle compound extensions
    if file_path.endswith(".min.js"):
        return "javascript"
    return LANGUAGE_MAP.get(ext, "text")


def should_skip_file(file_path: str) -> bool:
    import os
    parts = file_path.replace("\\", "/").split("/")
    for part in parts:
        if part in SKIP_DIRS:
            return True
    ext = os.path.splitext(file_path)[1].lower()
    if ext in SKIP_EXTENSIONS:
        return True
    if file_path.endswith(".min.js") or file_path.endswith(".min.css"):
        return True
    return False


def chunk_python_file(content: str, file_path: str) -> List[CodeChunk]:
    chunks = []
    try:
        tree = ast.parse(content)
        lines = content.splitlines()
    except SyntaxError:
        return chunk_generic(content, file_path, "python")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno if hasattr(node, "end_lineno") else start + 20
            chunk_content = "\n".join(lines[start:end])
            if len(chunk_content.strip()) < 10:
                continue
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                chunk_type="function",
                name=node.name,
                start_line=start + 1,
                end_line=end,
                language="python",
                metadata={"is_async": isinstance(node, ast.AsyncFunctionDef)},
            ))
        elif isinstance(node, ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno if hasattr(node, "end_lineno") else start + 50
            chunk_content = "\n".join(lines[start:end])
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                chunk_type="class",
                name=node.name,
                start_line=start + 1,
                end_line=end,
                language="python",
            ))

    if not chunks:
        return chunk_generic(content, file_path, "python")
    return chunks


def chunk_js_ts_file(content: str, file_path: str, language: str) -> List[CodeChunk]:
    """Parse JS/TS using regex for function and class extraction."""
    chunks = []
    lines = content.splitlines()

    # Match function declarations and arrow functions assigned to const/let
    function_patterns = [
        r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(",
        r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(",
        r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function",
    ]
    class_pattern = re.compile(r"^(?:export\s+)?class\s+(\w+)", re.MULTILINE)

    def find_block_end(lines, start_idx):
        depth = 0
        for i, line in enumerate(lines[start_idx:], start_idx):
            depth += line.count("{") - line.count("}")
            if depth <= 0 and i > start_idx:
                return i
        return min(start_idx + 100, len(lines) - 1)

    combined_func = re.compile("|".join(f"({p})" for p in function_patterns), re.MULTILINE)

    for i, line in enumerate(lines):
        m = combined_func.match(line.strip())
        if m:
            name = next((g for g in m.groups() if g and re.match(r"^\w+$", g)), "anonymous")
            end_idx = find_block_end(lines, i)
            chunk_content = "\n".join(lines[i:end_idx + 1])
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                chunk_type="function",
                name=name,
                start_line=i + 1,
                end_line=end_idx + 1,
                language=language,
            ))

    for m in class_pattern.finditer(content):
        name = m.group(1)
        start_idx = content[:m.start()].count("\n")
        end_idx = find_block_end(lines, start_idx)
        chunk_content = "\n".join(lines[start_idx:end_idx + 1])
        chunks.append(CodeChunk(
            content=chunk_content,
            file_path=file_path,
            chunk_type="class",
            name=name,
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            language=language,
        ))

    return chunks if chunks else chunk_generic(content, file_path, language)


def chunk_generic(content: str, file_path: str, language: str) -> List[CodeChunk]:
    """Fall back to line-based chunking with overlap."""
    lines = content.splitlines()
    chunks = []
    i = 0
    chunk_num = 0
    while i < len(lines):
        end = min(i + CHUNK_SIZE, len(lines))
        chunk_content = "\n".join(lines[i:end])
        if chunk_content.strip():
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                chunk_type="block",
                name=f"block_{chunk_num}",
                start_line=i + 1,
                end_line=end,
                language=language,
            ))
        chunk_num += 1
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def chunk_file(content: str, file_path: str) -> List[CodeChunk]:
    """Main entry point: detect language and chunk accordingly."""
    language = detect_language(file_path)
    if len(content) > MAX_FILE_SIZE:
        return []

    if language == "python":
        return chunk_python_file(content, file_path)
    elif language in ("javascript", "typescript"):
        return chunk_js_ts_file(content, file_path, language)
    else:
        return chunk_generic(content, file_path, language)
