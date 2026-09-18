import unittest
import shutil
import subprocess
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class AvatarFrontendTests(unittest.TestCase):
    def test_classroom_assets_have_cache_busting_versions(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")

        self.assertRegex(html, r'href="/styles\.css\?v=[^"]+"')
        self.assertRegex(html, r'src="/app\.js\?v=[^"]+"')

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for animation runtime checks")
    def test_animation_runtime(self) -> None:
        subprocess.run(
            ["node", "tests/avatar_runtime.cjs"],
            cwd=STATIC.parents[1], check=True, capture_output=True, text=True,
        )

    def test_avatar_has_gait_canvas_without_whole_body_bobbing(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertEqual(html.count('class="avatar-frame'), 2)
        self.assertIn('id="avatarGait"', html)
        self.assertNotIn("idle-step-bob", css)
        self.assertNotIn("avatar-breathe", css)

    def test_idle_action_contract_contains_every_supported_action(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")

        for action in ("glance", "sway", "wave", "sidestep", "nod"):
            self.assertIn(f'name: "{action}"', script)
        self.assertIn('dataset.idleAction = "none"', script)

    def test_speech_bubble_tracks_avatar_gait(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('function applyAvatarOffset()', script)
        self.assertIn('stage.style.setProperty("--avatar-offset-x"', script)
        self.assertIn(".avatar-wrap", css)
        self.assertIn("translate3d(var(--avatar-offset-x, 0px), var(--avatar-offset-y, 0px), 0)", css)

    def test_avatar_supports_pointer_drag_and_natural_settle(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('addEventListener("pointerdown", beginAvatarDrag)', script)
        self.assertIn('addEventListener("pointermove", moveAvatarDrag)', script)
        self.assertIn('addEventListener("pointerup", endAvatarDrag)', script)
        self.assertIn('touch-action: none', css)
        self.assertIn('data-dragging="true"', css)
        self.assertIn('@keyframes avatar-settle', css)

    def test_avatar_has_pet_like_attention_and_tap_reactions(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('addEventListener("pointerenter", beginAvatarAttention)', script)
        self.assertIn('addEventListener("pointerleave", clearAvatarAttention)', script)
        self.assertIn('data-pet-reaction="hop"', css)
        self.assertIn('@keyframes avatar-pet-hop', css)
        self.assertIn('data-attentive="true"', css)


if __name__ == "__main__":
    unittest.main()
