#!/usr/bin/env python3
"""Generate `reference/3.3.5a-globals.tsv` from a build-12340 runtime capture and UI MPQs.

    scripts/gen-reference-wotlk-globals.py --capture FILE --data DIR [--mpqcat FILE]

The capture is the addon-visible in-world `_G`. The hash-pinned enUS locale MPQs supply the
shipped FrameXML and Blizzard LoadOnDemand addons, so definitions absent from one live session are
still represented. No client file or captured value is copied into the repository: the output is
only global names, Lua types and origin classifications.
"""

import argparse
import collections
import hashlib
import os
import re
import shutil
import subprocess
import sys


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE = os.path.join(REPO, "reference")

BUILD = "12340"
VERSION = "3.3.5"
TOC = "30300"
SHIPPED_ADDON_COUNT = 23

# Mounted low to high. These are the only build-12340 enUS archives that contain the in-world
# FrameXML or Blizzard_* addon corpus. Hashes prevent a private-server patch from becoming the
# reference client by accident.
UI_ARCHIVES = (
    (
        "locale-enUS.MPQ",
        "45f02a3bf3964b169f397cea58113cdce5fa7bdf58d4b63f68e46255bb3bd3ea",
        338,
    ),
    (
        "patch-enUS.MPQ",
        "c1c06b0d0c34c331b21df7cdd25cc422a650efbd477e42b80849ba30b2e5fc99",
        339,
    ),
    (
        "patch-enUS-2.MPQ",
        "ab9af8457f0d7b99a562f26b7d1651bbf68ebc37ddb249d01ac860ccc8746ff4",
        185,
    ),
    (
        "patch-enUS-3.MPQ",
        "d61a60297af9044d926754d997cd5aa630500cd003d41983a9ccb5b324d61299",
        92,
    ),
)
AVAILABLE_UI_FILES = 399

INSTRUMENT_GLOBALS = {
    "BenillaReferenceCapture",
    "SLASH_BENILLAREFERENCECAPTURE1",
}

# Lua 5.1 globals actually present in the build-12340 world state. The member functions of bit,
# coroutine, math, string and table are not globals; they are recorded as members in shapes.tsv.
LUA_5_1 = {
    "_G",
    "_VERSION",
    "assert",
    "bit",
    "collectgarbage",
    "coroutine",
    "error",
    "foreach",
    "foreachi",
    "gcinfo",
    "getfenv",
    "getmetatable",
    "getn",
    "ipairs",
    "loadstring",
    "math",
    "next",
    "newproxy",
    "pairs",
    "pcall",
    "print",
    "rawequal",
    "rawget",
    "rawset",
    "select",
    "setfenv",
    "setmetatable",
    "string",
    "sqrt",
    "table",
    "tonumber",
    "tostring",
    "type",
    "unpack",
    "xpcall",
}

UI_PATH = re.compile(
    r"^Interface\\(?:FrameXML\\|AddOns\\Blizzard_[^\\]+\\).+\.(?:lua|xml|toc)$",
    re.IGNORECASE,
)
XML_REF = re.compile(rb'<(?:Script|Include)\s+file\s*=\s*"([^"]+)"', re.IGNORECASE)

LUA_ASSIGN = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*=[^=]", re.MULTILINE)
LUA_AFTER_SEMICOLON = re.compile(r";[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*=[^=]")
LUA_FUNC = re.compile(
    r"^[ \t]*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE
)
LUA_MULTI = re.compile(
    r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)+)\s*=[^=]",
    re.MULTILINE,
)
LUA_SETGLOBAL = re.compile(
    r"\bsetglobal\s*\(\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]\s*,"
)
LUA_G_ASSIGN = re.compile(
    r"\b_G\s*\[\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]\s*\]\s*="
)
LUA_G_DOT_ASSIGN = re.compile(r"\b_G\.([A-Za-z_][A-Za-z0-9_]*)\s*=")
LUA_CREATE_FRAME = re.compile(
    r"\bCreateFrame\s*\(\s*[^,\n]+,\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]"
)
LUA_CREATE_FONT = re.compile(
    r"\bCreateFont\s*\(\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]"
)
LUA_DYNAMIC_PREFIX = re.compile(
    r"(?:_G\s*\[|getglobal\s*\(|setglobal\s*\(|"
    r"CreateFrame\s*\(\s*[^,\n]+,|(?:[A-Za-z_][A-Za-z0-9_]*:)?CreateTexture\s*\()"
    r"\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]\s*\.\."
)
LUA_GETNAME_SUFFIX = re.compile(
    r"\bGetName\s*\(\s*\)\s*\.\.\s*['\"]([A-Za-z0-9_-]+)['\"]"
)
LUA_VARIABLE_SUFFIX = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\.\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]"
)
LUA_STRING_CONSTANT = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]\s*;?"
)

XML_ELEM = re.compile(r"<(\w+)([^>]*?)/?>", re.DOTALL)
XML_NAME = re.compile(r"\bname\s*=\s*(['\"])(.*?)\1", re.DOTALL)
PARENT_SUFFIX = re.compile(r"\bname\s*=\s*(['\"])\$parent([A-Za-z0-9_-]*)\1")
XML_SCRIPT = re.compile(
    r"<((?:On|Pre|Post)\w+|Script)\b(?![^>]*\bfile\s*=)[^>]*>(.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_mpqcat(mpqcat, archive, member, required=True):
    try:
        result = subprocess.run(
            [mpqcat, archive, member], check=True, capture_output=True
        )
    except OSError as error:
        sys.exit(f"could not run {mpqcat}: {error}")
    except subprocess.CalledProcessError as error:
        if not required:
            return None
        detail = getattr(error, "stderr", b"").decode("utf-8", "replace")
        sys.exit(f"could not read {member!r} from {archive}: {error}\n{detail}")
    return result.stdout


def normal_path(path):
    parts = []
    for part in path.replace("/", "\\").split("\\"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "\\".join(parts)


def join_ref(base, reference):
    reference = reference.strip().replace("/", "\\")
    if reference.startswith("\\"):
        return normal_path(reference)
    directory = base.rsplit("\\", 1)[0] if "\\" in base else ""
    return normal_path(directory + "\\" + reference)


def ui_index(data, mpqcat):
    """Return the highest-priority archive owner of every relevant shipped UI file."""
    owners = {}
    locale = os.path.join(data, "enUS")
    for filename, expected_hash, expected_count in UI_ARCHIVES:
        archive = os.path.join(locale, filename)
        if not os.path.isfile(archive):
            sys.exit(f"missing build-12340 UI archive: {archive}")
        actual_hash = sha256(archive)
        if actual_hash != expected_hash:
            sys.exit(
                f"{archive} is not the verified build-12340 enUS archive\n"
                f"  expected sha256 {expected_hash}\n"
                f"       got sha256 {actual_hash}"
            )
        listing = run_mpqcat(mpqcat, archive, "(listfile)").decode(
            "utf-8", "replace"
        )
        relevant = []
        for raw_path in listing.splitlines():
            path = normal_path(raw_path.strip())
            if UI_PATH.fullmatch(path):
                relevant.append(path)
                key = path.lower()
                if key not in owners:
                    owners[key] = (path, [])
                owners[key][1].append(archive)
        if len(relevant) != expected_count:
            sys.exit(
                f"{filename} exposes {len(relevant)} relevant UI files, "
                f"expected {expected_count}"
            )
    if len(owners) != AVAILABLE_UI_FILES:
        sys.exit(f"UI archive overlay has {len(owners)} files, expected {AVAILABLE_UI_FILES}")
    return owners


def shipped_corpus(owners, mpqcat):
    """Follow the current FrameXML and Blizzard-addon TOC/XML include graph."""
    cache = {}

    def read(path):
        key = path.lower()
        if key not in owners:
            raise KeyError(path)
        if key not in cache:
            canonical, archives = owners[key]
            for archive in reversed(archives):
                content = run_mpqcat(mpqcat, archive, canonical, required=False)
                if content is not None:
                    cache[key] = content
                    break
            else:
                sys.exit(f"no UI archive contains listed member {canonical!r}")
        return cache[key]

    roots = ["Interface\\FrameXML\\FrameXML.toc"]
    roots.extend(
        canonical
        for canonical, _archives in owners.values()
        if re.fullmatch(
            r"Interface\\AddOns\\Blizzard_[^\\]+\\[^\\]+\.toc",
            canonical,
            re.IGNORECASE,
        )
    )

    queue = list(sorted(roots, key=str.lower))
    seen = set()
    missing = set()
    corpus = {}
    while queue:
        path = normal_path(queue.pop(0))
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        if key not in owners:
            missing.add(path)
            continue
        canonical, _archives = owners[key]
        raw = read(canonical)
        corpus[canonical] = raw.decode("utf-8", "replace")

        lower = canonical.lower()
        references = []
        if lower.endswith(".toc"):
            for line in corpus[canonical].splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    references.append(line)
        elif lower.endswith(".xml"):
            references.extend(
                match.decode("utf-8", "replace") for match in XML_REF.findall(raw)
            )
        for reference in references:
            child = join_ref(canonical, reference)
            if child.lower() in owners:
                queue.append(child)
                continue
            # The stock InspectPVPFrame uses `PVPFrameTemplates.xml` without its FrameXML path;
            # FrameScript's include lookup finds that unique shipped basename globally.
            basename = normal_path(reference).rsplit("\\", 1)[-1].lower()
            basename_matches = [
                candidate
                for candidate, _archives in owners.values()
                if candidate.rsplit("\\", 1)[-1].lower() == basename
            ]
            if len(basename_matches) == 1:
                queue.append(basename_matches[0])
            elif child.lower().endswith((".lua", ".xml")):
                missing.add(child)

    if missing:
        sys.exit("shipped UI graph has missing references: " + ", ".join(sorted(missing)))
    return corpus


def lua_unescape(value):
    """Decode the small escape set WoW's SavedVariables writer uses for string keys."""
    escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}

    def replace(match):
        token = match.group(1)
        if token.isdigit():
            return chr(int(token, 10))
        return escapes.get(token, token)

    return re.sub(r"\\(\d{1,3}|.)", replace, value)


def captured_globals(path):
    """Parse and validate BenillaReferenceCapture's sorted in-world `_G` snapshot."""
    text = open(path, encoding="utf-8", errors="strict").read()
    expected_meta = {
        "version": VERSION,
        "build": BUILD,
        "toc": TOC,
    }
    for key, expected in expected_meta.items():
        match = re.search(rf'\["{key}"\]\s*=\s*(?:"([^"]+)"|(\d+))', text)
        actual = next((value for value in match.groups() if value is not None), None) if match else None
        if actual != expected:
            sys.exit(f"capture {key} is {actual!r}, expected {expected!r}")
    if not re.search(r'\["shipped_addons_complete"\]\s*=\s*true', text):
        sys.exit(
            "capture did not load every shipped Blizzard_* addon; install the current "
            "reference-global-capture addon, run /brcapture out of combat, then /reload"
        )
    for key in ("shipped_addon_count", "shipped_addon_loaded"):
        match = re.search(rf'\["{key}"\]\s*=\s*(\d+)', text)
        actual = int(match.group(1)) if match else None
        if actual != SHIPPED_ADDON_COUNT:
            sys.exit(f"capture {key} is {actual}, expected {SHIPPED_ADDON_COUNT}")

    globals_start = text.find('["globals"] = {')
    if globals_start < 0:
        sys.exit("capture has no globals table")
    count_match = re.search(r'\["count"\]\s*=\s*(\d+)', text[globals_start:])
    if not count_match:
        sys.exit("capture globals table has no count")
    globals_body = text[globals_start : globals_start + count_match.start()]

    rows = []
    blocks = re.findall(r"\{(.*?)\},\s*--\s*\[(\d+)\]", globals_body, re.DOTALL)
    for expected_index, (body, stored_index) in enumerate(blocks, 1):
        if int(stored_index) != expected_index:
            sys.exit(f"capture index {stored_index} appears at row {expected_index}")
        name_match = re.search(r'\["name"\]\s*=\s*"((?:[^"\\]|\\.)*)"', body)
        type_match = re.search(r'\["t"\]\s*=\s*"([a-z]+)"', body)
        if not name_match or not type_match:
            sys.exit(f"capture row {expected_index} has no name/type pair")
        name = lua_unescape(name_match.group(1))
        value_type = type_match.group(1)
        if any(character in name for character in "\t\r\n"):
            sys.exit(f"capture row {expected_index} has a non-TSV-safe name {name!r}")
        rows.append((name, value_type))

    stored_count = int(count_match.group(1))
    if stored_count != len(rows):
        sys.exit(f"capture count is {stored_count}, parsed {len(rows)} rows")
    names = [name for name, _value_type in rows]
    if names != sorted(names):
        sys.exit("capture global names are not in bytewise sorted order")
    duplicates = [name for name, count in collections.Counter(names).items() if count > 1]
    if duplicates:
        sys.exit(f"capture repeats global names: {duplicates}")
    missing_instrument = INSTRUMENT_GLOBALS - set(names)
    if missing_instrument:
        sys.exit(f"capture is missing its instrument globals: {sorted(missing_instrument)}")
    return rows


def lua_defs(text, names):
    names.update(LUA_ASSIGN.findall(text))
    names.update(LUA_AFTER_SEMICOLON.findall(text))
    names.update(LUA_FUNC.findall(text))
    for group in LUA_MULTI.findall(text):
        names.update(name.strip() for name in group.split(","))
    names.update(LUA_SETGLOBAL.findall(text))
    names.update(LUA_G_ASSIGN.findall(text))
    names.update(LUA_G_DOT_ASSIGN.findall(text))
    names.update(LUA_CREATE_FRAME.findall(text))
    names.update(LUA_CREATE_FONT.findall(text))


def shipped_names(corpus):
    names = set()
    suffixes = set()
    dynamic_prefixes = set()
    for path, text in corpus.items():
        if path.lower().endswith(".lua"):
            lua_defs(text, names)
            dynamic_prefixes.update(LUA_DYNAMIC_PREFIX.findall(text))
            suffixes.update(LUA_GETNAME_SUFFIX.findall(text))
            suffixes.update(LUA_VARIABLE_SUFFIX.findall(text))
            for variable, value in LUA_STRING_CONSTANT.findall(text):
                if re.search(rf"\b{re.escape(variable)}\s*\.\.", text):
                    dynamic_prefixes.add(value)
            continue
        if not path.lower().endswith(".xml"):
            continue
        uncommented = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        for _handler, body in XML_SCRIPT.findall(uncommented):
            lua_defs(body, names)
            dynamic_prefixes.update(LUA_DYNAMIC_PREFIX.findall(body))
            suffixes.update(LUA_GETNAME_SUFFIX.findall(body))
            suffixes.update(LUA_VARIABLE_SUFFIX.findall(body))
            for variable, value in LUA_STRING_CONSTANT.findall(body):
                if re.search(rf"\b{re.escape(variable)}\s*\.\.", body):
                    dynamic_prefixes.add(value)
        suffixes.update(match[1] for match in PARENT_SUFFIX.findall(uncommented))
        for tag, attributes in XML_ELEM.findall(uncommented):
            if tag.lower() == "binding":
                continue
            match = XML_NAME.search(attributes)
            if match and "$parent" not in match.group(2):
                names.add(match.group(2))
    names.discard("")
    dynamic_prefixes.discard("")
    return names, suffixes, dynamic_prefixes


def dynamic_root(name, prefixes):
    for prefix in prefixes:
        if name.startswith(prefix) and re.fullmatch(r"\d+(?:_\d+)*", name[len(prefix) :]):
            return True
    return False


def composed(name, roots, suffixes, dynamic_prefixes, depth=0):
    """Whether a captured name is a shipped root plus one or more `$parent` suffixes."""
    if depth > 8:
        return False
    for position in range(1, len(name)):
        head, tail = name[:position], name[position:]
        if tail not in suffixes and tail.rstrip("0123456789") not in suffixes:
            continue
        if (
            head in roots
            or head.rstrip("0123456789") in roots
            or dynamic_root(head, dynamic_prefixes)
        ):
            return True
        if composed(head, roots, suffixes, dynamic_prefixes, depth + 1):
            return True
    return False


def write_globals(path, capture_rows, corpus):
    defined, suffixes, dynamic_prefixes = shipped_names(corpus)
    captured_names = {name for name, _value_type in capture_rows}
    rows = []
    tally = collections.Counter()
    for name, value_type in capture_rows:
        if name in INSTRUMENT_GLOBALS:
            continue
        if name in LUA_5_1:
            origin = "lua"
        elif (
            name in defined
            or dynamic_root(name, dynamic_prefixes)
            or composed(name, defined, suffixes, dynamic_prefixes)
        ):
            origin = "framexml"
        else:
            origin = "engine"
        rows.append((name, value_type, origin))
        tally[(origin, value_type)] += 1

    lod_names = defined - captured_names
    for name in lod_names:
        rows.append((name, "lod", "framexml"))
        tally[("framexml", "lod")] += 1

    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write(
            "# The 3.3.5a build-12340 enUS client's global namespace. Generated by\n"
            "# scripts/gen-reference-wotlk-globals.py from a sorted in-world `_G` capture and\n"
            "# the exact hash-pinned shipped FrameXML/Blizzard-addon corpus.\n"
            "#\n"
            f"# {len(capture_rows)} captured names minus {len(INSTRUMENT_GLOBALS)} instrument "
            f"globals, plus {len(lod_names)}\n"
            "# shipped-UI definitions absent from that session as type `lod`. Origins describe\n"
            "# Lua 5.1, the C engine, or a definition/composed frame in the shipped UI.\n"
            "name\ttype\torigin\n"
        )
        for row in rows:
            out.write("\t".join(row) + "\n")
    return (
        len(rows),
        len(defined),
        len(suffixes),
        len(dynamic_prefixes),
        len(lod_names),
        tally,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True, help="BenillaReferenceCapture.lua")
    parser.add_argument("--data", required=True, help="the build-12340 client's Data directory")
    parser.add_argument(
        "--mpqcat",
        default=shutil.which("mpqcat")
        or os.path.join(REPO, "target", "debug", "examples", "mpqcat.exe"),
        help="benilla-mpq's mpqcat example",
    )
    parser.add_argument(
        "--out", default=os.path.join(REFERENCE, "3.3.5a-globals.tsv")
    )
    args = parser.parse_args()

    if not os.path.isfile(args.capture):
        parser.error(f"capture does not exist: {args.capture}")
    if not os.path.isfile(args.mpqcat):
        parser.error(f"mpqcat does not exist: {args.mpqcat}")

    capture_rows = captured_globals(args.capture)
    print(f"validated capture: {len(capture_rows)} sorted build-{BUILD} globals")
    owners = ui_index(args.data, args.mpqcat)
    print(f"validated UI archives: {len(owners)} overlaid files")
    corpus = shipped_corpus(owners, args.mpqcat)
    print(f"followed shipped UI graph: {len(corpus)} files")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    (
        row_count,
        definition_count,
        suffix_count,
        dynamic_prefix_count,
        lod_count,
        tally,
    ) = write_globals(args.out, capture_rows, corpus)
    print(
        f"wrote {args.out}: {row_count} names; {definition_count} direct UI definitions, "
        f"{suffix_count} composed suffixes, {dynamic_prefix_count} dynamic prefixes, "
        f"{lod_count} absent-session UI names"
    )
    for (origin, value_type), count in sorted(tally.items()):
        print(f"  {origin:8s} {value_type:8s} {count}")


if __name__ == "__main__":
    main()
