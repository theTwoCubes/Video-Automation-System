with open('pipelines/full_video_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '    pipeline = build_pipeline()\n    final_state = pipeline.invoke(initial_state)\n    return final_state\n'

new = (
    '    pipeline = build_pipeline()\n'
    '    failed_marker = Path(output_dir) / "FAILED.txt"\n'
    '    try:\n'
    '        final_state = pipeline.invoke(initial_state)\n'
    '        if final_state.get("error"):\n'
    '            failed_marker.write_text(\n'
    '                "Pipeline error:\\n" + str(final_state["error"]), encoding="utf-8"\n'
    '            )\n'
    '        elif failed_marker.exists():\n'
    '            failed_marker.unlink()\n'
    '        return final_state\n'
    '    except Exception as exc:\n'
    '        import traceback\n'
    '        failed_marker.write_text(\n'
    '            "Unhandled exception:\\n" + str(exc) + "\\n\\n" + traceback.format_exc(),\n'
    '            encoding="utf-8",\n'
    '        )\n'
    '        raise\n'
)

if old in content:
    content = content.replace(old, new)
    with open('pipelines/full_video_pipeline.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK')
else:
    print('NOT FOUND')
