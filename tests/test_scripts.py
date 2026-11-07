"""Run with: uv run --with pytest --with pyyaml pytest tests/"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from render import render  # noqa: E402
from wgdlib import load_schema, load_yaml, split_frontmatter, validate_note  # noqa: E402


def run(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd)


def note(vault, rel, fm, body="body\n"):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    path.write_text(f"---\n{lines}\n---\n{body}")
    return rel


BASE = {"layer": "life", "visibility": "private", "source": "manual", "created": "2026-10-31T10:00"}


@pytest.fixture
def vault(tmp_path):
    assert run("init.py", tmp_path).returncode == 0
    return tmp_path


def test_init_creates_structure_and_is_idempotent(vault):
    for p in [".wgd/schema.yaml", "templates/note.md", "CONTRIBUTING.md", "CLAUDE.md", "notes", "people", "inbox"]:
        assert (vault / p).exists(), p
    before = {p: p.read_text() for p in vault.rglob("*.md")}
    assert render(vault) == []
    assert {p: p.read_text() for p in vault.rglob("*.md")} == before


def test_init_keeps_existing_claude_md_and_obsidian_settings(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# My vault\n\nmy rules\n")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian/app.json").write_text('{"vimMode": true}')
    (tmp_path / ".obsidian/core-plugins.json").write_text('["file-explorer"]')
    assert run("init.py", tmp_path, "--obsidian").returncode == 0
    claude = (tmp_path / "CLAUDE.md").read_text()
    assert claude.startswith("# My vault\n\nmy rules\n") and "<!-- wgd:start schema=1 -->" in claude
    app = json.loads((tmp_path / ".obsidian/app.json").read_text())
    assert app["vimMode"] is True and app["attachmentFolderPath"] == "attachments"
    assert json.loads((tmp_path / ".obsidian/core-plugins.json").read_text())[:2] == ["file-explorer", "templates"]


def test_validate_accepts_the_about_examples(vault):
    note(vault, "contexts/Ukraine war.md", {"type": "context", "start": "2022-02", "end": "ongoing", **BASE, "layer": "world"})
    note(vault, "notes/2022/2022-02-24 Ukraine war starts.md",
         {"type": "note", "start": "2022-02-24", **BASE, "layer": "world", "contexts": '["[[Ukraine war]]"]'})
    note(vault, "people/Valentina.md", {"type": "person", **BASE})
    note(vault, "notes/2019/Grandma in hospital.md",
         {"type": "note", "start": "2019-03", "end": "2019-06", "approx": "true", **BASE,
          "visibility": "shared", "shared_with": '["[[Valentina]]"]'})
    result = run("validate.py", vault)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("fm, expected", [
    ({"type": "recipe"}, "is not in the schema"),
    ({"type": "note", "start": "March 2020"}, "not a partial ISO date"),
    ({"type": "note", "start": "2020-03", "end": "2019"}, "end: before start"),
    ({"type": "note", "start": "2020", "visibility": "sealed"}, "not supported yet"),
    ({"type": "note", "start": "2020", "visibility": "shared"}, "shared_with: required"),
    ({"type": "note", "start": "2020", "people": '["[[Nobody]]"]'}, "does not resolve"),
    ({"type": "note", "start": "2021"}, "location: expected in notes/2021/"),
])
def test_validate_rejects(vault, fm, expected):
    rel = note(vault, "notes/2020/x.md", {**BASE, **fm})
    errors = validate_note(vault, load_schema(vault), rel)
    assert any(expected in e for e in errors), errors


def test_link_target_must_have_the_right_type(vault):
    note(vault, "contexts/Lisbon.md", {"type": "context", "start": "2023", **BASE})
    rel = note(vault, "notes/2023/x.md", {"type": "note", "start": "2023", **BASE, "people": '["[[Lisbon]]"]'})
    assert any("expected a person" in e for e in validate_note(vault, load_schema(vault), rel))


def test_added_type_renders_and_validates(vault):
    schema_path = vault / ".wgd/schema.yaml"
    schema_path.write_text(schema_path.read_text() + """  recipe:
    description: something cooked
    folder: recipes
    default_layer: life
    fields:
      servings:
        kind: text
        required: true
""")
    assert run("validate.py", vault, "--schema").returncode == 0
    render(vault)
    assert "servings:" in (vault / "templates/recipe.md").read_text()
    assert "`recipe`" in (vault / "CONTRIBUTING.md").read_text()
    assert (vault / "recipes").is_dir()
    base = load_yaml((vault / "views/Everything.base").read_text())
    recipe = next(v for v in base["views"] if v["name"] == "Recipe")
    assert recipe["filters"] == {"and": ['type == "recipe"']} and "servings" in recipe["order"]
    assert recipe["groupBy"]["property"] == "layer" and "tags" in recipe["order"]
    assert 'file.inFolder("templates")' in base["filters"]["and"][2]["not"]
    assert render(vault) == []
    obsidian_rewrite = (vault / "views/Everything.base").read_text().replace("'", "").split("\n", 2)[2]
    (vault / "views/Everything.base").write_text(obsidian_rewrite)
    assert render(vault) == []
    note(vault, "recipes/Ragu.md", {"type": "recipe", "start": "2024", **BASE, "servings": 4})
    assert run("validate.py", vault).returncode == 0


def test_inventory_reports_dates_and_keeps_birthtimes(vault):
    (vault / "old").mkdir()
    (vault / "old/2023-05-02 trip.md").write_text("see [[old/Marco]]\n")
    assert run("inventory.py", vault).returncode == 0
    inv_path = vault / ".wgd/cache/inventory.json"
    inv = json.loads(inv_path.read_text())
    assert inv["notes"][0]["filename_date"] == "2023-05-02"
    assert inv["path_links"] == {"old/2023-05-02 trip.md": ["old/Marco"]}
    inv["notes"][0]["birthtime"] = "2001-01-01T00:00"
    inv_path.write_text(json.dumps(inv))
    run("inventory.py", vault)
    assert json.loads(inv_path.read_text())["notes"][0]["birthtime"] == "2001-01-01T00:00"


def test_apply_moves_with_git_rewrites_path_links_and_keeps_body(vault):
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    (vault / "old").mkdir()
    (vault / "old/Marco.md").write_text("Marco from work\n")
    body = "# Offsite\nmet [[Marco]], see [[old/Marco|him]] and [[old/Marco.md]]\n"
    (vault / "old/trip.md").write_text(body)
    subprocess.run(["git", "add", "-A"], cwd=vault, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=vault, check=True)
    plan = [
        {"path": "old/Marco.md", "frontmatter": {"type": "person", **BASE}},
        {"path": "old/trip.md", "frontmatter": {"type": "note", "start": "2023-05-02", **BASE, "people": ["[[Marco]]"]}},
    ]
    (vault / "plan.json").write_text(json.dumps(plan))
    result = run("apply.py", vault, vault / "plan.json")
    assert result.returncode == 0, result.stdout
    fm, new_body = split_frontmatter((vault / "notes/2023/trip.md").read_text())
    assert fm["start"] == "2023-05-02" and fm["people"] == ["[[Marco]]"]
    assert new_body == "# Offsite\nmet [[Marco]], see [[people/Marco|him]] and [[people/Marco]]\n"
    status = subprocess.run(["git", "status", "--short"], cwd=vault, capture_output=True, text=True).stdout
    assert "RM old/Marco.md -> people/Marco.md" in status


def test_apply_refuses_to_overwrite(vault):
    note(vault, "people/Marco.md", {"type": "person", **BASE})
    (vault / "old").mkdir()
    (vault / "old/Marco.md").write_text("other Marco\n")
    (vault / "plan.json").write_text(json.dumps([{"path": "old/Marco.md", "frontmatter": {"type": "person", **BASE}}]))
    result = run("apply.py", vault, vault / "plan.json")
    assert result.returncode == 1 and "already exists" in result.stdout
    assert (vault / "old/Marco.md").read_text() == "other Marco\n"


def test_query_time_overlap_and_links(vault):
    note(vault, "people/Valentina.md", {"type": "person", **BASE})
    note(vault, "notes/2021/2021-09 Valentina new job.md",
         {"type": "note", "start": "2021-09", **BASE, "layer": "work", "people": '["[[Valentina]]"]'})
    note(vault, "notes/2021/2021-09-20 Maldives.md", {"type": "note", "start": "2021-09-14", "end": "2021-09-24", **BASE})
    note(vault, "notes/2020/2020 Lisbon.md", {"type": "note", "start": "2020", **BASE})
    note(vault, "contexts/Ukraine war.md", {"type": "context", "start": "2022-02", "end": "ongoing", **BASE})
    out = run("query.py", vault, "--overlaps", "notes/2021/2021-09-20 Maldives.md").stdout
    assert "Valentina new job" in out and "Lisbon" not in out and "Ukraine" not in out
    assert "Ukraine war" in run("query.py", vault, "--from", "2025").stdout
    out = run("query.py", vault, "--link", "Valentina").stdout
    assert out.strip().endswith("notes/2021/2021-09 Valentina new job.md") and out.count("\n") == 1


def test_survey_reports_type_signals(vault):
    for i in range(3):
        note(vault, f"Cooking/Dish {i}.md", {"category": "recipe", "tags": "[food]"},
             f"## Ingredients\n- x\n## Method\nwith [[Valentina]] #dinner\n")
    (vault / "Journal").mkdir()
    (vault / "Journal/2021-09-14.md").write_text("Flew to the Maldives with [[Valentina]]\n")
    (vault / "attachments/scan.pdf").write_bytes(b"%PDF")
    out = run("survey.py", vault).stdout
    assert "- Cooking/ — 3" in out and "- Journal/ — 1" in out
    assert "- category — 3: recipe (3)" in out
    assert "- food — 3" in out and "- dinner — 3" in out
    assert "- ingredients — 3" in out and "- method — 3" in out
    assert "- Valentina * — 4" in out
    assert "1 with a date in the filename" in out
    assert "- .pdf — 1" in out


def test_tidy_files_attachments_by_note_and_rewrites_links(vault):
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    (vault / "Clippings/assets").mkdir(parents=True)
    for name in ["photo.png", "chart.png", "logo.svg", "orphan.jpg"]:
        (vault / "Clippings/assets" / name).write_bytes(b"x")
    (vault / "attachments/image.png").write_bytes(b"a")
    (vault / "attachments/_unlinked").mkdir()
    (vault / "attachments/_unlinked/old.jpg").write_bytes(b"o")
    (vault / "Old/empty/deeper").mkdir(parents=True)
    (vault / "Old/empty/.DS_Store").write_bytes(b"")
    (vault / "Clippings/Article A.md").write_text(
        "![](assets/photo.png)\n![[chart.png|300]]\n![[logo.svg]]\n![[image.png]]\n![](gone/chart.png)\n")
    (vault / "Clippings/Article B.md").write_text("![Logo](<assets/logo.svg>)\n[[missing.pdf]]\n[[spatial.energy]]\n[[Dr. Smith]] [[v1.2 release|v1.2]]\n")
    (vault / "contexts/spatial.energy.md").write_text("a note whose name has a dot\n")
    assert run("tidy.py", vault).returncode == 0
    plan = json.loads((vault / ".wgd/cache/tidy.json").read_text())
    moves = {m["from"]: m["to"] for m in plan["moves"]}
    assert moves == {
        "Clippings/assets/photo.png": "attachments/Article A/photo.png",
        "Clippings/assets/chart.png": "attachments/Article A/chart.png",
        "Clippings/assets/logo.svg": "attachments/_shared/logo.svg",
        "attachments/image.png": "attachments/Article A/image.png",
    }
    assert plan["unlinked"] == ["Clippings/assets/orphan.jpg"]
    assert plan["empty_dirs"] == ["Old"]
    assert plan["repairs"] == 1 and plan["broken"] == [{"note": "Clippings/Article B.md", "link": "missing.pdf"}]

    assert run("tidy.py", vault, "--apply", vault / ".wgd/cache/tidy.json").returncode == 0
    assert (vault / "Clippings/Article A.md").read_text() == (
        "![](../attachments/Article%20A/photo.png)\n![[chart.png|300]]\n![[logo.svg]]\n![[image.png]]\n"
        "![](attachments/Article%20A/chart.png)\n")
    assert (vault / "Clippings/Article B.md").read_text() == "![Logo](<../attachments/_shared/logo.svg>)\n[[missing.pdf]]\n[[spatial.energy]]\n[[Dr. Smith]] [[v1.2 release|v1.2]]\n"
    assert not (vault / "Old").exists() and (vault / "Clippings/assets/orphan.jpg").exists()
    again = json.loads((run("tidy.py", vault), (vault / ".wgd/cache/tidy.json").read_text())[1])
    assert again["moves"] == [] and again["repairs"] == 0


def test_tidy_due_counts_captures_since_last_tidy(vault):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    for msg in ["capture: a", "wgd: tidy", "capture: b", "capture: c"]:
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", msg], cwd=vault, check=True)
    assert run("tidy.py", vault, "--due", "--every", "2").stdout.startswith("due (2 captures")
    assert run("tidy.py", vault, "--due").stdout.startswith("not due (2 captures")
