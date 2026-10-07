import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import summarize  # noqa: E402


def finding(check, impact, confidence="Medium", desc="Something bad\nsecond line", lines=(7, 8), dep=False, fname="src/A.sol"):
    return {
        "check": check,
        "impact": impact,
        "confidence": confidence,
        "description": desc,
        "elements": [
            {
                "type": "function",
                "name": "f",
                "source_mapping": {
                    "filename_relative": fname,
                    "filename_absolute": "/abs/" + fname,
                    "is_dependency": dep,
                    "lines": list(lines),
                },
            }
        ],
    }


def write(tmp_path, detectors, success=True, error=None):
    p = tmp_path / "out.json"
    p.write_text(json.dumps({"success": success, "error": error, "results": {"detectors": detectors}}))
    return str(p)


@pytest.fixture
def gh(tmp_path, monkeypatch):
    out, summ = tmp_path / "gh_out", tmp_path / "gh_sum"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    return out, summ


def kv(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


SAMPLE = [
    finding("amm-spot-price", "High"),
    finding("swap-deadline", "Medium"),
    finding("unsafe-downcast", "Low", desc="a | b"),
    finding("naming", "Informational"),
]


def test_counts_and_outputs(tmp_path, gh):
    rc = summarize.main(["--json", write(tmp_path, SAMPLE), "--fail-on", "none", "--sarif", "r.sarif"])
    assert rc == 0
    assert kv(gh[0]) == {"findings": "4", "high": "1", "medium": "1", "sarif": "r.sarif"}


@pytest.mark.parametrize(
    "fail_on,expected",
    [("high", 1), ("medium", 1), ("low", 1), ("none", 0)],
)
def test_threshold_with_high(tmp_path, gh, fail_on, expected):
    assert summarize.main(["--json", write(tmp_path, SAMPLE), "--fail-on", fail_on]) == expected


@pytest.mark.parametrize("fail_on,expected", [("high", 0), ("medium", 1), ("low", 1)])
def test_threshold_medium_only(tmp_path, gh, fail_on, expected):
    d = [finding("swap-deadline", "Medium")]
    assert summarize.main(["--json", write(tmp_path, d), "--fail-on", fail_on]) == expected


@pytest.mark.parametrize("fail_on,expected", [("high", 0), ("medium", 0), ("low", 1)])
def test_threshold_low_only(tmp_path, gh, fail_on, expected):
    d = [finding("x", "Low")]
    assert summarize.main(["--json", write(tmp_path, d), "--fail-on", fail_on]) == expected


def test_informational_never_fails(tmp_path, gh):
    d = [finding("x", "Informational"), finding("y", "Optimization")]
    assert summarize.main(["--json", write(tmp_path, d), "--fail-on", "low"]) == 0


def test_no_findings(tmp_path, gh):
    assert summarize.main(["--json", write(tmp_path, []), "--fail-on", "low"]) == 0
    assert kv(gh[0])["findings"] == "0"
    assert "No findings." in gh[1].read_text()


def test_summary_table(tmp_path, gh):
    summarize.main(["--json", write(tmp_path, SAMPLE), "--fail-on", "none"])
    text = gh[1].read_text()
    assert "| Detector | Impact | Confidence | Description | Location |" in text
    assert "| amm-spot-price | High | Medium | Something bad | src/A.sol:7 |" in text
    assert "second line" not in text  # first line only
    assert "a \\| b" in text  # pipes escaped
    # High sorted before Low
    assert text.index("amm-spot-price") < text.index("unsafe-downcast")
    assert text.rstrip().endswith(
        "For a triaged report of a deployed contract or a single file, see https://tanod.dev (paid per call via x402)."
    )


def test_missing_json(tmp_path, gh, capsys):
    assert summarize.main(["--json", str(tmp_path / "nope.json"), "--fail-on", "none"]) == 2
    assert "::error" in capsys.readouterr().out
    assert not gh[0].exists()


def test_success_false(tmp_path, gh, capsys):
    rc = summarize.main(["--json", write(tmp_path, [], success=False, error="Compilation failed"), "--fail-on", "none"])
    assert rc == 2
    assert "Compilation failed" in capsys.readouterr().out


def test_invalid_json(tmp_path, gh):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert summarize.main(["--json", str(p), "--fail-on", "high"]) == 2


def test_dependency_element_skipped():
    f = finding("x", "Low", dep=True)
    assert summarize.location(f) == ""


def test_location_relative_to_cwd(tmp_path):
    f = finding("x", "Low", fname="src/A.sol")
    f["elements"][0]["source_mapping"]["filename_absolute"] = str(tmp_path / "src/A.sol")
    assert summarize.location(f, cwd=str(tmp_path)) == "src/A.sol:7"


def test_first_line_strips_source_refs():
    t = "Lending.price() (src/L.sol#23-26) reads spot state (x)\nmore"
    assert summarize.first_line(t) == "Lending.price() reads spot state (x)"
