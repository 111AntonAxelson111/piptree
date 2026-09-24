#!/usr/bin/env python3
"""
piptree_paths.py

Print package contents as space-separated path lines:
  root
  root member
  root member submember

Each line ends with:  — kind — signature/short — origin

Usage:
  python piptree_paths.py <package> [--depth N] [--show-docs] [--no-color] [--max N]
"""
from __future__ import annotations
import sys
import argparse
import importlib
import inspect
import pkgutil
from typing import List, Tuple, Optional
try:
    from importlib import metadata as importlib_metadata
except Exception:
    import importlib_metadata  # type: ignore

# ANSI colors
ANSI = {"reset":"\033[0m","red":"\033[31m","green":"\033[32m","blue":"\033[34m","yellow":"\033[33m","magenta":"\033[35m","cyan":"\033[36m"}
LEVEL_COLORS = ["red","green","blue","yellow","magenta","cyan"]

def colorize(enabled: bool, level: int, text: str) -> str:
    if not enabled or not text:
        return text
    col = LEVEL_COLORS[level % len(LEVEL_COLORS)]
    return f"{ANSI[col]}{text}{ANSI['reset']}"

def safe_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

def one_line(s: Optional[str], width: int = 70) -> str:
    if not s:
        return ""
    s = s.strip().splitlines()[0]
    return (s[:width-1] + "…") if len(s) > width else s

def kind_of(obj) -> str:
    if inspect.ismodule(obj): return "module"
    if inspect.isclass(obj): return "class"
    if inspect.isfunction(obj): return "function"
    if inspect.ismethod(obj): return "method"
    tname = type(obj).__name__
    if tname in ("type","GenericAlias","UnionType"): return "type"
    return "value"

def safe_signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except Exception:
        return "(...)"

def distribution_for_module(mod_name: str) -> Optional[Tuple[str,str]]:
    top = mod_name.split(".")[0]
    try:
        try:
            d = importlib_metadata.distribution(top)
            return (d.metadata.get("Name", top), d.version)
        except Exception:
            pass
        for dist in importlib_metadata.distributions():
            try:
                tl = dist.read_text("top_level.txt")
            except Exception:
                tl = None
            if not tl:
                continue
            tops = [t.strip() for t in tl.splitlines() if t.strip()]
            if top in tops:
                return (dist.metadata.get("Name", top), dist.version)
    except Exception:
        pass
    return None

def origin_info(obj, pkg_name: str) -> str:
    mod = getattr(obj, "__module__", None)
    try:
        if mod and mod.startswith(pkg_name):
            try:
                src = inspect.getsourcefile(obj) or inspect.getfile(obj)
                return f"defined in {src}"
            except Exception:
                return f"module:{mod}"
        if mod:
            dist = distribution_for_module(mod)
            if dist:
                return f"external:{dist[0]} {dist[1]}"
            return f"external:{mod}"
    except Exception:
        pass
    return ""

def gather_top_level(module) -> List[Tuple[str,object,str]]:
    out = []
    for name, obj in inspect.getmembers(module):
        if name.startswith("__") and name.endswith("__"):
            continue
        out.append((name, obj, getattr(obj,"__module__", "") or ""))
    return out

def walk_submodules(module, limit=200) -> List[Tuple[str,bool]]:
    if not hasattr(module, "__path__"):
        return []
    found=[]
    for finder,name,ispkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        found.append((name,ispkg))
        if len(found)>=limit: break
    return found

def build_paths(pkg_name: str, depth: int=3, max_items:int=500, show_docs: bool=False) -> List[Tuple[List[str], str, str, str]]:
    """
    Returns list of tuples:
      (path_components, kind, detail, origin)
    Each path_components is a list like ['icecream','ic'] or ['icecream','IceCreamDebugger','__call__']
    """
    rows = []
    root = safe_import(pkg_name)
    if not root:
        raise SystemExit(f"Package '{pkg_name}' not installed or failed to import.")
    # root alone
    rows.append(([pkg_name], "package", one_line(getattr(root,"__doc__","")), root.__name__))

    members = gather_top_level(root)
    shown = 0
    for name, obj, origin_mod in sorted(members, key=lambda x: x[0]):
        if shown >= max_items:
            break
        shown += 1
        path = [pkg_name, name]
        k = kind_of(obj)
        detail = ""
        if k in ("function","class","method"):
            if k == "class":
                init = getattr(obj, "__init__", None)
                detail = safe_signature(init) if init else ""
            else:
                detail = safe_signature(obj)
            if show_docs:
                doc = one_line(inspect.getdoc(obj) or "")
                if doc:
                    detail = f"{detail}  {doc}"
        elif k == "module":
            dist = distribution_for_module(obj.__name__)
            detail = f"ver={dist[1]}" if dist else ""
        else:
            try:
                detail = one_line(repr(obj), 70)
            except Exception:
                detail = ""
        origin = origin_info(obj, pkg_name)
        rows.append((path, k, detail, origin))

        # class methods (one deeper)
        if depth >= 3 and inspect.isclass(obj):
            mcount = 0
            for mname, mobj in inspect.getmembers(obj):
                if mcount >= 200:
                    break
                if mname.startswith("__") and mname.endswith("__"):
                    continue
                if inspect.isfunction(mobj) or inspect.ismethod(mobj):
                    if getattr(mobj, "__module__", "").startswith(pkg_name):
                        rows.append(([pkg_name, name, mname], "method", safe_signature(mobj) + (("  " + one_line(inspect.getdoc(mobj) or "")) if show_docs else ""), origin_info(mobj, pkg_name)))
                        mcount += 1

        # module submembers (one deeper)
        if depth >= 3 and inspect.ismodule(obj):
            sub = safe_import(obj.__name__)
            if sub:
                scount = 0
                for sname, sobj, sorigin in gather_top_level(sub):
                    if scount >= 200:
                        break
                    sk = kind_of(sobj)
                    sdetail = ""
                    if sk in ("function","class"):
                        sdetail = safe_signature(sobj)
                        if show_docs:
                            doc3 = one_line(inspect.getdoc(sobj) or "")
                            if doc3:
                                sdetail = f"{sdetail}  {doc3}"
                    else:
                        try:
                            sdetail = one_line(repr(sobj), 70)
                        except Exception:
                            sdetail = ""
                    rows.append(([pkg_name, name, sname], sk, sdetail, origin_info(sobj, pkg_name)))
                    scount += 1

    # include submodules of package itself (shallow)
    subs = walk_submodules(root, limit=200)
    for name, ispkg in subs:
        if name == pkg_name:
            continue
        rows.append(([pkg_name, name.split(".",1)[1]], "submodule", "", name))

    return rows


# Add these two helper functions near the top of your file
def should_we_printA(displayed_name: str, origin: str, *, public_only: bool = False, external_marker: str = "external:") -> bool:
    """
    displayed_name: the colored/root text as passed (may contain ANSI escapes)
    origin: the origin string produced by origin_info(...)
    Returns True to print immediately, False to collect as external.
    """
    import re
    # strip ANSI escapes to inspect the raw name
    plain = re.sub(r'\x1b\[[0-9;]*m', '', displayed_name or "")
    name = plain.strip()

    # if origin marks external, do not print in main
    if origin and external_marker in origin:
        return False

    # optional: hide private names when requested
    if public_only and name.startswith("_"):
        return False

    return True


def should_we_printB(line: str, origin: str, *, public_only: bool = False, external_marker: str = "external:") -> bool:
    """
    line: the full formatted line (may contain ANSI escapes)
    origin: the origin string produced by origin_info(...)
    Returns True to print immediately, False to collect as external.
    """
    import re
    # primary rule: external origins are collected
    if origin and external_marker in origin:
        return False

    # strip ANSI escapes to inspect the raw path and last token
    plain = re.sub(r'\x1b\[[0-9;]*m', '', line or "")
    # take the path portion before the first " —"
    path_part = plain.split(" —", 1)[0].strip()
    last_token = path_part.split()[-1] if path_part.split() else ""

    # optional: hide private members when requested
    if public_only and last_token.startswith("_"):
        return False

    return True




def print_paths(rows: List[Tuple[List[str], str, str, str]], color: bool=True):
    """
    Print each path as a single line:
      <level0_colored> <level1_colored> <level2_colored> ...  — kind — detail — origin
    Also print the root line once (first row) as a single token (no trailing annotation optional).
    """
    counter=0
    annat="\n\n\n\nhere we put things that should not be in the main print\n"
    printed_root = False
    for path, kind, detail, origin in rows:
        if counter>100:   #this so that we do not print to much at once
            counter=0
            input("-- More  --")
        else:
            counter+=1
        # print root alone once (first row)
        if not printed_root and len(path) == 1:
            root_txt = colorize(color, 0, path[0])
            if should_we_printA(root_txt, origin):
                print(root_txt)
            else:
                annat+=root_txt+"\n"
            printed_root = True
            # continue to next rows (we still want to print other rows)
            continue

        # build colored path tokens
        tokens = []
        for i, comp in enumerate(path):
            tokens.append(colorize(color, i, comp))
        path_text = " ".join(tokens)
        # annotation
        # build three separate annotated lines
        line_kind = f"{path_text} — {kind}"
        # normalize detail so signatures appear as "(...)" lines
        line_detail = None
        if detail:
            # if detail already looks like a signature (starts with "(") keep it,
            # otherwise print it as-is (docstring snippet or "ver=...")
            line_detail = f"{path_text} — {detail}"

        line_origin = f"{path_text} — {origin}" if origin else None

        # submodule separator
        is_submodule = (kind == "submodule")
        sep_line = f"{path_text} ---------------"

        # decide whether to print now or collect (use origin only)
        if should_we_printB(f"{path_text} — {kind}", origin):
            if is_submodule:
                print(sep_line)
            print(line_kind)
            if line_detail:
                print(line_detail)
            if line_origin:
                print(line_origin)
            if is_submodule:
                print(sep_line)
        else:
            if is_submodule:
                annat += sep_line + "\n"
            annat += line_kind + "\n"
            if line_detail:
                annat += line_detail + "\n"
            if line_origin:
                annat += line_origin + "\n"
            if is_submodule:
                annat += sep_line + "\n"


    print(annat)

def main(argv: List[str]):
    p = argparse.ArgumentParser(description="Print package contents as path lines (space-separated).")
    p.add_argument("package", help="Importable package name (e.g. icecream)")
    p.add_argument("--depth", type=int, default=3, help="Depth to traverse (default 3)")
    p.add_argument("--show-docs", action="store_true", help="Include one-line docstrings")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    p.add_argument("--max", type=int, default=500, help="Max top-level items to show")
    args = p.parse_args(argv)

    rows = build_paths(args.package, depth=args.depth, max_items=args.max, show_docs=args.show_docs)
    print_paths(rows, color=not args.no_color)

if __name__ == "__main__":
    main(sys.argv[1:])
