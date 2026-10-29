import asyncio
import unittest

from dotlife.dashboard.server import FAVICON, favicon


class FaviconTest(unittest.TestCase):
    """The server answers the browser's favicon requests with dotlife's icon."""

    def test_serves_the_dotlife_icon(self):
        """The route returns the PNG in the dashboard's assets."""
        response = asyncio.run(favicon(None))  # type: ignore[arg-type]
        self.assertEqual(response.path, FAVICON)
        self.assertEqual(response.media_type, "image/png")
        self.assertTrue(FAVICON.is_file())


if __name__ == "__main__":
    unittest.main()
