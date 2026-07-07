from collections import OrderedDict
from pathlib import Path
from agents.base_agent import BaseAgent
from services.video_composer.composer import compose_video_aligned


class VideoAgent(BaseAgent):
    def run(self, state: dict) -> dict:
        print("[VideoAgent] Composing final video...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        audio_paths = state.get("audio_paths", [])
        slide_id_to_path = state.get("slide_id_to_path") or {}
        slide_contents = state.get("slide_contents", []) or []
        slide_paths = state.get("slide_image_paths", []) or []
        output_dir = state["output_dir"]
        lesson_id = state["lesson_id"]

        # always rebuild mapping from slide_contents + slide_image_paths
        # this is the authoritative source — immune to schema/state-drop issues
        if slide_contents and slide_paths:
            slide_id_to_path = {}
            for slide_data, img_path in zip(slide_contents, slide_paths):
                sid = slide_data.get("id", "")
                if sid:
                    slide_id_to_path[sid] = img_path
            print(f"  Slide mapping: {len(slide_id_to_path)} entries")

        if not slide_paths:
            state["error"] = "No slides to render."
            return state
        if not audio_paths:
            state["error"] = "No audio segments."
            return state

        # filter to only narration-type segments (same filter as VoiceAgent)
        narration_segs = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]

        # group audio paths by slide_id (preserving order)
        slide_audio_map = OrderedDict()
        for i, seg in enumerate(narration_segs):
            if i >= len(audio_paths):
                break
            slide_id = seg.get("slide_id", "slide_001")
            if slide_id not in slide_audio_map:
                slide_audio_map[slide_id] = []
            slide_audio_map[slide_id].append(audio_paths[i])

        if not slide_audio_map:
            state["error"] = "Could not map audio to slides."
            return state

        # build ordered (slide_image, [audio_files]) pairs
        fallback_img = slide_paths[-1]
        aligned_pairs = []
        for slide_id, audios in slide_audio_map.items():
            img = slide_id_to_path.get(slide_id, fallback_img)
            if not Path(img).exists():
                img = fallback_img
            aligned_pairs.append((img, audios))

        print(f"  {len(aligned_pairs)} slide groups, {len(audio_paths)} total audio segments")

        output_path = str(Path(output_dir) / f"{lesson_id}_final.mp4")
        try:
            compose_video_aligned(aligned_pairs, output_path)
            state["video_path"] = output_path
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"  Video: {output_path} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  Video composition failed: {e}")
            state["error"] = str(e)

        return state
