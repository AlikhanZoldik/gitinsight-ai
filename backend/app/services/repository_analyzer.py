import base64
import os
import re
from pathlib import PurePosixPath
from urllib.parse import quote

from backend.app.models.audit import Preview, Rule
from backend.app.utils.errors import GitHubError

CODE = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".hpp", ".cs", ".go"}
MANIFEST = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "go.mod",
    "cmakelists.txt",
    "build.gradle",
}
SKIP = {
    "vendor",
    "node_modules",
    "target",
    "dist",
    "build",
    "obj",
    "bin",
    "generated",
    "third_party",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
}
SECRET = re.compile(
    r"(?i)(-----begin [\w ]*private key|github_pat_|gh[pousr]_[a-z0-9]{12}|akia[a-z0-9]{16}|AIza[\w-]{22}|sk-[\w-]{16}|bearer\s+[\w.-]{12}|(?:token|key|password|passwd|secret|credential)[\w-]*[\"']?\s*[:=]\s*[\"']?[^\s\"']{5,}|://[^/\s:]+:[^/\s@]+@)"
)


def limit(name, default, ceiling):
    return min(ceiling, max(1, int(os.getenv(name, str(default)))))


def priority(path):
    p = PurePosixPath(path.lower())
    if (
        SKIP.intersection(p.parts)
        or any(x.startswith(".env") for x in p.parts)
        or re.search(
            r"secret|credential|password|private.key|\.min\.|\.lock$|\.generated\.|\.g\.cs$",
            path,
            re.I,
        )
    ):
        return 99
    if p.name in {"readme", "readme.md", "readme.rst"}:
        return 0
    if (
        p.name in MANIFEST
        or p.suffix == ".csproj"
        or (".github/workflows/" in path and p.suffix in {".yaml", ".yml"})
    ):
        return 1
    if p.suffix in CODE:
        if p.stem in {"app", "main", "index", "program", "server"}:
            return 2
        if is_test(path):
            return 3
        return 4 if any(x in path for x in ("service", "route", "core")) else 5
    return 99


def is_test(path):
    return bool(
        re.search(
            r"(^|/)(tests?/|test_[^/]+\.py$)|(_test\.(go|py)|\.(spec|test)\.[jt]sx?|Tests?\.(java|cs))$",
            path,
            re.I,
        )
    )


def health(paths, files, meta, truncated):
    names = {PurePosixPath(p.lower()).name for p in paths}
    readmes = [
        p for p in paths if PurePosixPath(p.lower()).name in {"readme", "readme.md", "readme.rst"}
    ]
    doc = "\n".join(files[p] for p in readmes if p in files)

    def observed(value):
        return True if value else None if truncated else False

    def phrase(pattern):
        return bool(re.search(pattern, doc, re.I)) if doc else None

    checks = [
        ("README", 10, observed(readmes), "Add a project README."),
        (
            "Installation instructions",
            5,
            phrase(r"install|getting started|setup"),
            "Document installation steps.",
        ),
        (
            "Usage example",
            5,
            phrase(r"usage|example|quickstart"),
            "Include a runnable usage example.",
        ),
        (
            "Stack description",
            5,
            phrase(r"tech(nology)? stack|built with|dependencies"),
            "Describe the technology stack.",
        ),
        (
            "Test file conventions",
            20,
            observed(any(is_test(p) for p in paths)),
            "Document or add representative tests.",
        ),
        (
            "Dependency manifest",
            10,
            observed(bool(names & MANIFEST) or any(n.endswith(".csproj") for n in names)),
            "Document dependencies in a manifest.",
        ),
        (
            "Git ignore rules",
            5,
            observed(".gitignore" in names),
            "Review generated files and add ignore rules.",
        ),
        (
            "Configuration example",
            5,
            observed(".env.example" in names or "config.example.json" in names),
            "Document configuration with a sanitized example.",
        ),
        (
            "Actions workflow",
            15,
            observed(
                any(
                    p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
                    for p in paths
                )
            ),
            "Add or document CI checks.",
        ),
        ("Description", 4, bool(meta.get("description")), "Add a concise repository description."),
        ("Topics", 3, bool(meta.get("topics")), "Add relevant repository topics."),
        ("License", 4, bool(meta.get("license")), "Clarify licensing terms."),
        (
            "Screenshot file",
            3,
            observed(any(re.search(r"screenshot.*\.(png|jpg|webp)$", p, re.I) for p in paths)),
            "Add a screenshot for visitors.",
        ),
        (
            "Homepage link listed",
            2,
            bool(meta.get("homepage")),
            "List a project homepage if available.",
        ),
        (
            "Problem statement",
            4,
            phrase(r"problem|purpose|motivation|solves"),
            "Explain the problem this project addresses.",
        ),
    ]
    rules = [
        Rule(label=label, weight=weight, observed=value, action=action)
        for label, weight, value, action in checks
    ]
    possible = sum(r.weight for r in rules if r.observed is not None)
    return rules, round(
        100 * sum(r.weight for r in rules if r.observed) / possible
    ) if possible else None


async def snapshot(gh, owner, repo):
    try:
        return await read_snapshot(gh, owner, repo)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise GitHubError(502, "GitHub returned incomplete snapshot metadata.") from None


async def read_snapshot(gh, owner, repo):
    if repo in {".", ".."}:
        raise GitHubError(422, "Invalid repository name.")
    root = f"/repos/{owner}/{repo}"
    meta = (await gh.fresh(root)).json()
    if (
        meta.get("visibility") != "public"
        or meta.get("private") is not False
        or meta.get("full_name", "").lower() != f"{owner}/{repo}".lower()
    ):
        raise GitHubError(404, "Public repository unavailable.")
    commit = (await gh.fresh(root + "/commits/" + quote(meta["default_branch"], safe=""))).json()
    sha = commit["sha"]
    tree = (
        await gh.request(root + "/git/trees/" + commit["commit"]["tree"]["sha"], recursive=1)
    ).json()
    rows = [
        r for r in tree["tree"] if r.get("type") == "blob" and r.get("mode") in {"100644", "100755"}
    ]
    files = {}
    total = 0
    max_files = limit("AUDIT_MAX_FILES", 8, 20)
    per = limit("AUDIT_FILE_BYTES", 16000, 32000)
    budget = limit("AUDIT_TOTAL_BYTES", 48000, 100000)
    notes = [
        "Checks cover sampled UTF-8 files. Filename and README conventions can miss valid alternatives. Homepage reachability is unverified."
    ]
    candidates = sorted(
        (r for r in rows if priority(r["path"]) < 99 and 0 < r.get("size", 0) <= per),
        key=lambda r: (priority(r["path"]), len(r["path"]), r["path"]),
    )
    for r in candidates[: max_files * 2]:
        if len(files) >= max_files:
            break
        if total + r["size"] > budget:
            continue
        try:
            blob = (await gh.request(root + "/git/blobs/" + r["sha"])).json()
            raw = base64.b64decode(blob["content"])
            content = raw.decode("utf-8")
        except (UnicodeError, ValueError, KeyError):
            continue
        except GitHubError as exc:
            if exc.status != 404:
                raise
            continue
        if (
            len(raw) > min(per, budget - total)
            or "\x00" in content
            or SECRET.search(content)
            or SECRET.search(r["path"])
        ):
            continue
        files[r["path"]] = content
        total += len(raw)
    truncated = tree.get("truncated", False)
    if truncated:
        notes.append("GitHub truncated the tree. Missing paths are not evaluated.")
    rules, score = health([r["path"] for r in rows], files, meta, truncated)
    return Preview(
        repository=meta["full_name"],
        commit=sha,
        files=list(files),
        bytes=total,
        score=score,
        rules=rules,
        limitations=notes,
    ), files
