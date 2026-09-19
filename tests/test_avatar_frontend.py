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

    def test_idle_action_contract_uses_restrained_teacher_gestures(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")

        for action in ("glance", "posture", "nod"):
            self.assertIn(f'name: "{action}"', script)
        self.assertNotIn('name: "sidestep"', script)
        self.assertNotIn('name: "wave"', script)
        self.assertIn('randomBetween(14000, 24000)', script)
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

    def test_avatar_has_teacher_like_attention_and_tap_reactions(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('addEventListener("pointerenter", beginAvatarAttention)', script)
        self.assertIn('addEventListener("pointerleave", clearAvatarAttention)', script)
        self.assertIn('playTeacherAcknowledgement()', script)
        self.assertIn('data-teacher-reaction="acknowledge"', css)
        self.assertIn('@keyframes avatar-teacher-acknowledge', css)
        self.assertNotIn('avatar-pet-hop', css)
        self.assertIn('data-attentive="true"', css)

    def test_speaking_and_feedback_motion_is_restrained(self) -> None:
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('animation: avatar-talk 1.2s', css)
        self.assertIn('animation: avatar-celebrate 1.05s', css)
        self.assertIn('animation: avatar-correct 1.15s', css)
        self.assertNotIn('translateY(-5px)', css)

    def test_avatar_has_state_driven_teacher_expressions(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertEqual(html.count('class="brow '), 2)
        self.assertEqual(html.count('class="cheek '), 2)
        self.assertIn('data-expression="warm"', html)
        self.assertIn('const avatarExpressionMap = {', script)
        self.assertIn('function syncAvatarExpression()', script)
        for expression in ("warm", "curious", "focused", "explaining", "concerned", "celebrate"):
            self.assertIn(f'data-expression="{expression}"', css)
        self.assertIn('.face-overlay .brow', css)
        self.assertIn('.face-overlay .cheek', css)

    def test_key_knowledge_uses_a_brief_serious_expression(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('function isKeyKnowledgeSegment(', script)
        self.assertIn('function speechEmphasisSegments(', script)
        self.assertIn('function speechSegmentAtProgress(', script)
        self.assertIn('function setKnowledgeEmphasis(', script)
        self.assertIn('data-knowledge-emphasis="false"', (STATIC / "index.html").read_text(encoding="utf-8"))
        self.assertIn('data-expression="emphasis"', css)
        self.assertIn('knowledgeEmphasis === "true"', script)

    def test_avatar_uses_layered_depth_and_pointer_parallax(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="avatarShadow"', html)
        self.assertIn('class="avatar-shadow"', html)
        self.assertIn('function depthTiltForPointer(', script)
        self.assertIn('perspective:', css)
        self.assertIn('radial-gradient(', css)
        self.assertIn('rotateX(var(--avatar-depth-tilt-x', css)
        self.assertIn('rotateY(var(--avatar-depth-tilt-y', css)

    def test_workspace_divider_is_user_resizable(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="workspaceResizer"', html)
        self.assertIn('role="separator"', html)
        self.assertIn('aria-orientation="vertical"', html)
        self.assertIn('addEventListener("pointerdown", beginWorkspaceResize)', script)
        self.assertIn('addEventListener("keydown", resizeWorkspaceByKeyboard)', script)
        self.assertIn('xixi-stage-width', script)
        self.assertIn('--stage-panel-width', css)
        self.assertIn('cursor: col-resize', css)
        self.assertIn('.workspace-resizer { display: none;', css)


if __name__ == "__main__":
    unittest.main()
