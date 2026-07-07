import json
from pathlib import Path
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are a diagram designer for theTwoCubes Learning.
Generate self-contained HTML+CSS animated diagrams for technical concepts.

DIAGRAM REQUIREMENTS:
- Must be exactly 1920x1080 pixels (width/height on <body> and .slide)
- Background: #080b10 (dark), accent color: #00c896 (green), secondary: #ff6b35 (orange)
- Font: 'Outfit' from Google Fonts (include @import)
- Use CSS @keyframes animations ONLY — no JavaScript
- Animation duration: 3-5 seconds, loop with animation-iteration-count: infinite or once
- Must clearly teach the concept visually

TYPES OF ANIMATIONS TO USE:
- fadeIn + slideIn for elements appearing in sequence
- Color highlights sweeping across elements
- Arrows growing/moving to show data flow
- Box borders appearing to show memory allocation
- Text appearing line by line

EXAMPLE CONCEPTS:
- Stack memory: boxes stacking up from bottom with addresses
- Heap allocation: boxes appearing with arrows from stack pointers
- Compilation pipeline: source → preprocessor → compiler → linker → exe (with arrows)
- Call stack: function frames pushing/popping
- Pointer: box with value + arrow pointing to another box

RULES:
- Include ALL CSS inline in <style> tags
- No external dependencies except Google Fonts
- The animation must loop cleanly
- Left side: 8px gradient bar (green to orange)
- Top-right: channel tag "theTwoCubes"
- Title at top-left of the diagram area

Output strictly valid JSON:
{
  "id": "diagram_id",
  "title": "short title",
  "html": "complete self-contained HTML string with all CSS inline"
}"""

USER_TEMPLATE = """
Concept: {concept}
Lesson: {lesson_title}
Diagram type: {diagram_type}

Generate an animated HTML diagram that visualizes this concept clearly for a YouTube video.
The animation should run for 4 seconds and loop.
Output JSON with the full HTML string.
"""

# Fallback static HTML diagram templates for common concepts
_FALLBACK_TEMPLATES = {
    "memory": """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;900&family=JetBrains+Mono:wght@400;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;background:#080b10;font-family:'Outfit',sans-serif;overflow:hidden;position:relative}
.bar{position:absolute;left:0;top:0;bottom:0;width:8px;background:linear-gradient(180deg,#00c896,#ff6b35)}
.title{position:absolute;top:60px;left:80px;font-size:42px;font-weight:700;color:#fff}
.tag{position:absolute;top:36px;right:48px;font-size:15px;font-weight:700;color:#00c896;opacity:.8}
.diagram{position:absolute;top:160px;left:80px;right:80px;bottom:80px;display:flex;gap:80px;align-items:flex-end}
.col{flex:1;display:flex;flex-direction:column-reverse;gap:4px;align-items:center}
.col-label{font-size:20px;font-weight:700;color:#00c896;margin-top:16px;letter-spacing:.08em;text-transform:uppercase}
.mem-box{width:100%;height:64px;border:1px solid #1e1e1e;border-left:3px solid #00c896;background:#0d1117;display:flex;align-items:center;padding:0 20px;font-family:'JetBrains Mono',monospace;font-size:18px;color:#e2e2e2;position:relative;animation:fadeIn 0.5s ease forwards;opacity:0}
.mem-box.orange{border-left-color:#ff6b35}
.mem-box .addr{color:#4a6070;font-size:14px;margin-left:auto}
@keyframes fadeIn{to{opacity:1}}
.b1{animation-delay:.2s}.b2{animation-delay:.5s}.b3{animation-delay:.8s}.b4{animation-delay:1.1s}
.b5{animation-delay:.2s}.b6{animation-delay:.5s}
</style></head>
<body>
<div class="bar"></div>
<div class="tag">theTwoCubes</div>
<div class="title">Memory Layout: Stack vs Heap</div>
<div class="diagram">
  <div class="col">
    <div class="mem-box b1"><span>int x = 42</span><span class="addr">0x7ffe…a4</span></div>
    <div class="mem-box b2"><span>int y = 10</span><span class="addr">0x7ffe…a0</span></div>
    <div class="mem-box b3"><span>char c = 'A'</span><span class="addr">0x7ffe…9f</span></div>
    <div class="mem-box b4"><span>return addr</span><span class="addr">0x7ffe…9b</span></div>
    <div class="col-label">Stack</div>
  </div>
  <div class="col">
    <div class="mem-box orange b5"><span>new int[100]</span><span class="addr">0x55f3…c0</span></div>
    <div class="mem-box orange b6"><span>new Node()</span><span class="addr">0x55f3…e8</span></div>
    <div class="col-label">Heap</div>
  </div>
</div>
</body></html>""",

    "compilation": """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;background:#080b10;font-family:'Outfit',sans-serif;overflow:hidden;position:relative}
.bar{position:absolute;left:0;top:0;bottom:0;width:8px;background:linear-gradient(180deg,#00c896,#ff6b35)}
.title{position:absolute;top:60px;left:80px;font-size:42px;font-weight:700;color:#fff}
.tag{position:absolute;top:36px;right:48px;font-size:15px;font-weight:700;color:#00c896;opacity:.8}
.pipeline{position:absolute;top:200px;left:80px;right:80px;display:flex;align-items:center;gap:0}
.step{flex:1;background:#0d1117;border:1px solid #1e1e1e;border-left:3px solid #00c896;border-radius:10px;padding:30px 20px;text-align:center;animation:popIn .4s cubic-bezier(.34,1.56,.64,1) both;opacity:0}
.step-num{font-size:13px;color:#00c896;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px}
.step-name{font-size:26px;font-weight:700;color:#fff}
.step-file{font-size:16px;color:#4a6070;margin-top:6px}
.arrow{font-size:32px;color:#00c896;padding:0 16px;opacity:0;animation:fadeIn .3s ease forwards}
@keyframes popIn{0%{opacity:0;transform:scale(.8)}100%{opacity:1;transform:scale(1)}}
@keyframes fadeIn{to{opacity:1}}
.s1{animation-delay:.2s}.s2{animation-delay:.6s}.s3{animation-delay:1.0s}.s4{animation-delay:1.4s}.s5{animation-delay:1.8s}
.a1{animation-delay:.5s}.a2{animation-delay:.9s}.a3{animation-delay:1.3s}.a4{animation-delay:1.7s}
</style></head>
<body>
<div class="bar"></div>
<div class="tag">theTwoCubes</div>
<div class="title">C++ Compilation Pipeline</div>
<div class="pipeline">
  <div class="step s1"><div class="step-num">1</div><div class="step-name">Source</div><div class="step-file">main.cpp</div></div>
  <div class="arrow a1">→</div>
  <div class="step s2"><div class="step-num">2</div><div class="step-name">Preprocessor</div><div class="step-file">main.i</div></div>
  <div class="arrow a2">→</div>
  <div class="step s3"><div class="step-num">3</div><div class="step-name">Compiler</div><div class="step-file">main.s</div></div>
  <div class="arrow a3">→</div>
  <div class="step s4"><div class="step-num">4</div><div class="step-name">Assembler</div><div class="step-file">main.o</div></div>
  <div class="arrow a4">→</div>
  <div class="step s5" style="border-left-color:#ff6b35"><div class="step-num">5</div><div class="step-name">Linker</div><div class="step-file">program.exe</div></div>
</div>
</body></html>""",
}


class DiagramAgent(BaseAgent):
    def run(self, state: dict) -> dict:
        print("[DiagramAgent] Generating diagrams...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        lesson_title = state["lesson_title"]
        lesson_plan = state.get("lesson_plan", {})

        # collect diagram refs from script
        diagram_refs = {}
        for seg in segments:
            if seg.get("type") == "diagram" and seg.get("diagram_ref"):
                diagram_refs[seg["diagram_ref"]] = seg.get("text", seg["diagram_ref"])

        # also check lesson plan
        for section in lesson_plan.get("sections", []):
            if section.get("needs_diagram"):
                did = f"diag_{section['id']}"
                if did not in diagram_refs:
                    diagram_refs[did] = section.get("title", lesson_title)

        output_dir = Path(state["output_dir"]) / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        diagrams = []
        diagram_paths = {}

        try:
            from services.video_composer.composer import _get_ffmpeg
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            ffmpeg_exe = None

        for diag_id, concept in diagram_refs.items():
            print(f"  Generating {diag_id}: {concept[:60]}")
            out_video = str(output_dir / f"{diag_id}.mp4")
            out_png = str(output_dir / f"{diag_id}.png")

            # generate animated HTML via LLM
            html_content = self._generate_diagram_html(diag_id, lesson_title, concept)

            if html_content and ffmpeg_exe:
                from services.diagram_renderer.html_animator import render_animated_diagram
                video_path = render_animated_diagram(
                    html_content, out_video, ffmpeg_exe, duration_sec=4.0
                )
                if video_path:
                    diagrams.append({"id": diag_id, "title": concept[:60], "type": "animated", "path": video_path})
                    diagram_paths[diag_id] = video_path
                    print(f"  Animated diagram: {diag_id}")
                    continue

            # fallback: render static PNG via Playwright
            static_html = self._get_fallback_html(concept)
            if static_html:
                try:
                    from services.diagram_renderer.html_animator import capture_animation_frames, assemble_diagram_video
                    frames_dir = output_dir / f"frames_{diag_id}"
                    frames = capture_animation_frames(static_html, frames_dir, capture_fps=5, duration_sec=2.0)
                    if frames and ffmpeg_exe:
                        video_path = assemble_diagram_video(frames, out_video, ffmpeg_exe, capture_fps=5)
                        if video_path:
                            diagrams.append({"id": diag_id, "title": concept[:60], "type": "fallback", "path": video_path})
                            diagram_paths[diag_id] = video_path
                            continue
                except Exception as e:
                    print(f"  Fallback diagram error: {e}")

            print(f"  Skipped diagram {diag_id}")

        state["diagrams"] = diagrams
        state["diagram_image_paths"] = diagram_paths
        print(f"  Generated {len(diagrams)} diagrams.")
        return state

    def _generate_diagram_html(self, diag_id: str, lesson_title: str, concept: str) -> str:
        """Ask LLM to generate animated HTML diagram. Returns HTML string or empty."""
        concept_lower = concept.lower()
        diagram_type = "flow"
        if any(w in concept_lower for w in ["stack", "heap", "memory", "pointer", "array"]):
            diagram_type = "memory_layout"
        elif any(w in concept_lower for w in ["compil", "link", "preprocess", "build"]):
            diagram_type = "pipeline"
        elif any(w in concept_lower for w in ["call", "function", "recursi"]):
            diagram_type = "call_stack"
        elif any(w in concept_lower for w in ["loop", "iteration", "for", "while"]):
            diagram_type = "iteration"

        user_msg = USER_TEMPLATE.format(
            diagram_id=diag_id,
            concept=concept[:300],
            lesson_title=lesson_title,
            diagram_type=diagram_type,
        )
        try:
            result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
            return result.get("html", "")
        except Exception as e:
            print(f"  Diagram LLM error: {e}")
            return ""

    def _get_fallback_html(self, concept: str) -> str:
        """Return a hardcoded fallback HTML animation based on concept keywords."""
        concept_lower = concept.lower()
        if any(w in concept_lower for w in ["stack", "heap", "memory", "pointer"]):
            return _FALLBACK_TEMPLATES["memory"]
        if any(w in concept_lower for w in ["compil", "link", "preprocess", "build", "pipeline"]):
            return _FALLBACK_TEMPLATES["compilation"]
        return _FALLBACK_TEMPLATES["memory"]  # most generic fallback
