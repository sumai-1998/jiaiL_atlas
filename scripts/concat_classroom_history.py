#!/usr/bin/env python3
"""Join all five completed classroom versions with labels and chapter markers."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'WorldWarp_outputs/classroom_history_2026-09-08'
SOURCES = [
    ('WorldWarp 单独生成', 'classroom_pan_left_2026-09-07', 0.6, 1),
    ('MapAnything + GaME + WorldWarp', 'classroom_hybrid_pan_left_2026-09-07/video', 0.6, 1),
    ('三项目串联：strength 0.50', 'classroom_hybrid_tuning_2026-09-08/strength_050', 0.5, 1),
    ('三项目串联：strength 0.65', 'classroom_hybrid_tuning_2026-09-08/strength_065', 0.65, 1),
    ('三项目串联：5 帧上下文', 'classroom_hybrid_tuning_2026-09-08/context_5', 0.6, 5),
]


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc')
    assert font.exists()
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin', '-n']
    filters, chapters, segments = [], [';FFMETADATA1'], []
    for index, (title, directory, strength, context) in enumerate(SOURCES):
        report = json.loads((ROOT/'WorldWarp_outputs'/directory/'report.json').read_text())
        source = Path(report['output_video'])
        assert report['status'] == 'complete' and report['written_frames'] == 321
        assert report['fps'] == 30 and report['strength'] == strength
        assert report.get('context_frames_2nd', 1) == context
        command += ['-i', str(source)]
        text_file = OUT/f'label_{index+1}.txt'
        text_file.write_text(f'{index+1}/5  {title}\nstrength {strength:.2f}  ·  上下文 {context} 帧', encoding='utf-8')
        filters.append(f'[{index}:v]setpts=PTS-STARTPTS,pad=iw:ih+64:0:64:color=0x171c24,'
                       f'drawtext=fontfile={font}:textfile={text_file}:fontcolor=white:'
                       f'fontsize=18:x=12:y=8:line_spacing=7,setsar=1[v{index}]')
        chapters.extend(['[CHAPTER]', 'TIMEBASE=1/1000', f'START={index*10700}',
                         f'END={(index+1)*10700}', f'title={index+1}. {title}'])
        segments.append(dict(index=index+1, title=title, source=str(source), strength=strength,
                             context_frames=context, start_seconds=index*10.7,
                             end_seconds=(index+1)*10.7, frames=321,
                             source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    metadata = OUT/'chapters.ffmetadata'
    metadata.write_text('\n'.join(chapters)+'\n', encoding='utf-8')
    command += ['-f', 'ffmetadata', '-i', str(metadata)]
    filters.append(''.join(f'[v{i}]' for i in range(5))+'concat=n=5:v=1:a=0[out]')
    output = OUT/'classroom_all_versions_53.5s.mp4'
    command += ['-filter_complex_threads', '4', '-filter_complex', ';'.join(filters),
                '-map', '[out]', '-map_metadata', '5', '-map_chapters', '5',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p',
                '-r', '30', '-an', '-threads', '4', '-movflags', '+faststart', str(output)]
    (OUT/'ffmpeg_command.json').write_text(json.dumps(command, ensure_ascii=False, indent=2))
    with (OUT/'ffmpeg.log').open('w') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    probe = subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames,duration:format=duration,size:chapter',
        '-of', 'json', str(output)], text=True)
    (OUT/'ffprobe.json').write_text(probe)
    info = json.loads(probe)
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    assert int(video['nb_read_frames']) == 1605 and video['r_frame_rate']=='30/1'
    assert abs(float(info['format']['duration'])-53.5)<1e-6
    assert (video['width'],video['height']) == (480,672)
    assert len(info['chapters']) == 5
    report = dict(status='complete', output_video=str(output), duration_seconds=53.5,
                  frames=1605, fps=30, width=480, height=672, segments=segments,
                  note='Chronological concatenation. All 321 frames of each source are retained; a 64-pixel header is added above the original 480x608 image.')
    (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (OUT/'README.md').write_text('# 教室历次视频合集\n\n'
        '[播放合集](classroom_all_versions_53.5s.mp4)\n\n'
        '共 5 个版本，1605 帧、30 fps、53.5 秒。画面上方标注版本与参数，播放器支持时可按章节跳转。\n\n'
        + '\n'.join(f"- {s['start_seconds']:.1f}–{s['end_seconds']:.1f} 秒：{s['title']}（strength {s['strength']:.2f}，上下文 {s['context_frames']} 帧）。" for s in segments)
        + '\n\n原始 480×608 画面完整保留，上方新增 64 像素标题栏，合集为 480×672。\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
