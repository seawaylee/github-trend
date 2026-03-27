from src.skill_watch import fetch_skill_snapshot, summarize_changes


SAMPLE_HTML = """
<html>
  <head>
    <title>Using Superpowers — ClawHub</title>
    <link rel="canonical" href="https://clawhub.ai/zlc000190/using-superpowers"/>
  </head>
  <body>
    <div class="pending-banner-content">
      <strong>Skill flagged — suspicious patterns detected</strong>
      <p>ClawHub Security flagged this skill as suspicious. Review the scan results before using.</p>
    </div>
    <div class="skill-hero-title-row"><h1 class="section-title">Using Superpowers</h1></div>
    <p class="section-subtitle">Use when starting any conversation - establishes how to find and use skills.</p>
    <div class="skill-version-pill"><span class="skill-version-label">Current version</span><strong>v<!-- -->0.1.0</strong></div>
    <div class="skill-tag-row"><span class="tag">latest<span class="tag-meta">v<!-- -->k979</span></span></div>
    <div class="tag tag-accent">MIT-0</div>
    <div class="tab-body"><div><h2 class="section-title">SKILL.md</h2><div class="markdown">line1<p>line2</p></div></div></div>
    <div class="dimension-row"><div class="dimension-label">Instruction Scope</div><div class="dimension-detail">Very broad.</div></div>
    <a class="btn btn-primary" href="https://example.com/api/v1/download?slug=using-superpowers">Download zip</a>
    <script>
      owner:$R[30]={displayName:"zlc000190"},
      latestVersion:$R[16]={createdAt:1770691943217,createdBy:"user",changelog:"Initial release: 使用超能力",files:$R[17]=[$R[18]={contentType:"text/markdown",path:"SKILL.md",sha256:"abc123",size:3798}],fingerprint:"f00baa"},
      moderationInfo:$R[28]={isSuspicious:!0,reasonCodes:$R[29]=["suspicious.llm_suspicious","suspicious.vt_suspicious"],summary:"Detected: suspicious.llm_suspicious, suspicious.vt_suspicious",updatedAt:1774496641683,verdict:"suspicious"},
      skill:$R[31]={latestVersionId:"k979",stats:$R[33]={comments:0,downloads:16914,installsAllTime:271,installsCurrent:257,stars:36,versions:1}}
    </script>
  </body>
</html>
"""


class DummyResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.url = "https://clawhub.ai/zlc000190/using-superpowers"

    def raise_for_status(self):
        return None


def test_fetch_skill_snapshot_extracts_core_fields(monkeypatch):
    monkeypatch.setattr("src.skill_watch.requests.get", lambda *args, **kwargs: DummyResponse(SAMPLE_HTML))

    snapshot = fetch_skill_snapshot("https://clawhub.ai/skills/using-superpowers")

    assert snapshot["title"] == "Using Superpowers"
    assert snapshot["current_version"] == "v0.1.0"
    assert snapshot["latest_version_id"] == "k979"
    assert snapshot["owner"] == "zlc000190"
    assert snapshot["stats"]["downloads"] == 16914
    assert snapshot["moderation"]["verdict"] == "suspicious"
    assert snapshot["moderation"]["reason_codes"] == ["suspicious.llm_suspicious", "suspicious.vt_suspicious"]
    assert snapshot["skill_text"] == "line1\nline2"
    assert snapshot["scan_dimensions"][0]["label"] == "Instruction Scope"


def test_summarize_changes_reports_key_deltas():
    previous = {
        "current_version": "v0.1.0",
        "latest_version_id": "k979",
        "changelog": "Initial release",
        "fingerprint": "aaa",
        "skill_sha256": "111",
        "skill_text_sha256": "222",
        "stats": {"downloads": 10, "installs_current": 3, "installs_all_time": 4, "stars": 5, "versions": 1, "comments": 0},
        "moderation": {"verdict": "suspicious", "summary": "Detected A", "reason_codes": ["a"]},
    }
    current = {
        "current_version": "v0.1.1",
        "latest_version_id": "k980",
        "changelog": "Patch",
        "fingerprint": "bbb",
        "skill_sha256": "333",
        "skill_text_sha256": "444",
        "stats": {"downloads": 13, "installs_current": 5, "installs_all_time": 6, "stars": 8, "versions": 2, "comments": 1},
        "moderation": {"verdict": "review", "summary": "Detected B", "reason_codes": ["b"]},
    }

    diff = summarize_changes(previous, current)

    assert diff["status"] == "changed"
    assert any("版本变化" in item for item in diff["changes"])
    assert any("下载量变化" in item for item in diff["changes"])
    assert any("安全判定变化" in item for item in diff["changes"])
