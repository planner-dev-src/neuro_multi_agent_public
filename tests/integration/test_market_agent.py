"""
Smoke-тест для market_agent
Проверяет сбор и анализ рыночных данных через MarketAgent
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

# Добавляем корневую папку проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.base.models import AgentResult
from src.agents.market_agent.pipeline import MarketAgent


class TestMarketAgentSmoke(TestCase):
    def test_run_returns_expected_payload_shape(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            snapshot_root = Path(tmp_dir) / "snapshots"
            snapshot_root.mkdir(parents=True, exist_ok=True)

            # Создаем снапшоты для ВСЕХ страниц
            html_content = """
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
            """
            (snapshot_root / "example.com__catalog.html").write_text(
                html_content.strip(), encoding="utf-8"
            )

            # Снапшот для /ml-basics
            (snapshot_root / "example.com__ml-basics.html").write_text(
                """
                <html>
                  <head><title>ML Basics</title></head>
                  <body>
                    <h1>Machine Learning Basics</h1>
                    <p>12 lessons, 8 hours of content.</p>
                  </body>
                </html>
                """.strip(),
                encoding="utf-8"
            )

            # Снапшот для /dl-advanced
            (snapshot_root / "example.com__dl-advanced.html").write_text(
                """
                <html>
                  <head><title>DL Advanced</title></head>
                  <body>
                    <h1>Deep Learning Advanced</h1>
                    <p>24 lessons, 18 hours of content.</p>
                  </body>
                </html>
                """.strip(),
                encoding="utf-8"
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

            self.assertGreaterEqual(source_meta.get("snapshot_hits", 0), 3)
            self.assertEqual(source_meta.get("proxy_hits", 0), 0)
            self.assertEqual(source_meta.get("direct_hits", 0), 0)

            self.assertIn("pages_total", source_meta)
            self.assertIn("pages_ok", source_meta)
            self.assertIn("pages_failed", source_meta)

            # Все 3 страницы успешно обработаны
            self.assertEqual(source_meta["pages_total"], 3)
            self.assertEqual(source_meta["pages_ok"], 3)
            self.assertEqual(source_meta["pages_failed"], 0)

            self.assertIn("page_results", source_meta)
            self.assertIsInstance(source_meta["page_results"], list)
            self.assertEqual(len(source_meta["page_results"]), 3)

            # Проверяем первую страницу (каталог)
            page_result = source_meta["page_results"][0]
            self.assertEqual(page_result.get("status"), "ok")
            self.assertEqual(page_result.get("access_mode"), "offline_snapshot")
            self.assertEqual(page_result.get("url"), "https://example.com/catalog")
            self.assertIsNotNone(page_result.get("raw_html_path"))
            self.assertGreater(page_result.get("text_length", 0), 0)

            # Проверяем, что все URL обработаны
            urls = [p.get("url") for p in source_meta["page_results"]]
            self.assertIn("https://example.com/catalog", urls)
            self.assertIn("https://example.com/ml-basics", urls)
            self.assertIn("https://example.com/dl-advanced", urls)

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


if __name__ == "__main__":
    import unittest
    unittest.main()