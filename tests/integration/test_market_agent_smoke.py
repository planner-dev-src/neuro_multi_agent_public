from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.agents.base.models import AgentResult
from src.agents.market_agent.pipeline import MarketAgent


class TestMarketAgentSmoke(TestCase):
    def test_run_returns_expected_payload_shape(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            snapshot_root = Path(tmp_dir) / "snapshots"
            snapshot_root.mkdir(parents=True, exist_ok=True)

            html_path = snapshot_root / "example.com__catalog.html"
            html_path.write_text(
                """
                <html>
                  <head><title>Platform One</title></head>
                  <body>
                    <main>
                      <h1>AI Courses</h1>
                      <section>
                        <article>
                          <h2>Machine Learning Basics</h2>
                          <p>Beginner course with 12 lessons and 8 hours of content.</p>
                          <a href="https://example.com/ml-basics">Open course</a>
                        </article>
                        <article>
                          <h2>Deep Learning Advanced</h2>
                          <p>Advanced specialization with 24 lessons and 18 hours.</p>
                          <a href="https://example.com/dl-advanced">Open program</a>
                        </article>
                      </section>
                    </main>
                  </body>
                </html>
                """.strip(),
                encoding="utf-8",
            )

            agent = MarketAgent()
            result = agent.run(
                platforms=[
                    {
                        "name": "Platform One",
                        "category": "education",
                        "priority": "high",
                        "notes": "offline snapshot smoke",
                        "urls": ["https://example.com/catalog"],
                    }
                ],
                crawler_config_overrides={
                    "access_mode": "offline_snapshot",
                    "snapshot_root": snapshot_root,
                },
            )

            self.assertIsInstance(result, AgentResult)
            self.assertIsInstance(result.payload, dict)

            payload = result.payload
            self.assertIn("platform_reports", payload)
            self.assertIn("files", payload)

            platform_reports = payload["platform_reports"]
            self.assertIsInstance(platform_reports, list)
            self.assertEqual(len(platform_reports), 1)

            report = platform_reports[0]
            self.assertIsInstance(report, dict)
            self.assertIn("platform_name", report)
            self.assertIn("source_meta", report)
            self.assertIn("analytics", report)
            self.assertIn("catalog_items", report)

            self.assertEqual(report["platform_name"], "Platform One")
            self.assertIsInstance(report["catalog_items"], list)

            source_meta = report["source_meta"]
            self.assertIsInstance(source_meta, dict)
            self.assertEqual(
                source_meta.get("crawler_access_mode"),
                "offline_snapshot",
            )
            self.assertIn("access_modes_used", source_meta)
            self.assertIn("snapshot_hits", source_meta)
            self.assertIn("proxy_hits", source_meta)
            self.assertIn("direct_hits", source_meta)

            self.assertGreaterEqual(source_meta.get("snapshot_hits", 0), 1)
            self.assertEqual(source_meta.get("proxy_hits", 0), 0)
            self.assertEqual(source_meta.get("direct_hits", 0), 0)

            self.assertIn("pages_total", source_meta)
            self.assertIn("pages_ok", source_meta)
            self.assertIn("pages_failed", source_meta)

            self.assertEqual(source_meta["pages_total"], 1)
            self.assertEqual(source_meta["pages_ok"], 1)
            self.assertEqual(source_meta["pages_failed"], 0)

            self.assertIn("page_results", source_meta)
            self.assertIsInstance(source_meta["page_results"], list)
            self.assertEqual(len(source_meta["page_results"]), 1)

            page_result = source_meta["page_results"][0]
            self.assertEqual(page_result.get("status"), "ok")
            self.assertEqual(page_result.get("access_mode"), "offline_snapshot")
            self.assertEqual(page_result.get("url"), "https://example.com/catalog")
            self.assertIsNotNone(page_result.get("raw_html_path"))
            self.assertGreater(page_result.get("text_length", 0), 0)

            files = payload["files"]
            self.assertIsInstance(files, dict)
            self.assertIn("markdown", files)
            self.assertIn("json", files)
            self.assertIn("csv", files)

            markdown_path = Path(files["markdown"])
            json_path = Path(files["json"])
            csv_path = Path(files["csv"])

            self.assertTrue(markdown_path.exists())
            self.assertTrue(markdown_path.is_file())
            self.assertTrue(json_path.exists())
            self.assertTrue(json_path.is_file())
            self.assertTrue(csv_path.exists())
            self.assertTrue(csv_path.is_file())