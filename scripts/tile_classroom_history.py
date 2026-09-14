#!/usr/bin/env python3
"""Tile five classroom videos synchronously in a 3x2 grid with input reference."""
import json
import subprocess
from pathlib import Path

from concat_classroom_history import ROOT, SOURCES

OUT = ROOT / 'WorldWarp_outputs/classroom_grid_2026-09-08'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin', '-n']
    filters, cells = [], []
    for index, (title, directory, strength, context) in enumerate(SOURCES):
        report = json.loads((ROOT/'WorldWarp_outputs'/directory/'report.json').read_text())
        assert report['status']=='complete' and report['written_frames']==321 and report['fps']==30
        command += ['-i', report['output_video']]
        text_file = OUT/f'label_{index+1}.txt'
        text_file.write_text(f'{index+1}/5  {title}\nstrength {strength:.2f}  ·  上下文 {context} 帧', encoding='utf-8')
        cells.append(dict(row=index//3+1, column=index%3+1, title=title,
                          source=report['output_video'], strength=strength, context_frames=context))
    reference = ROOT/'WorldWarp_outputs/classroom_pan_left_2026-09-07/input_prepared.png'
    command += ['-loop', '1', '-framerate', '30', '-i', str(reference)]
    (OUT/'label_6.txt').write_text('输入图片（静态参考）\n其余 5 格按相同时间同步播放', encoding='utf-8')
    cells.append(dict(row=2, column=3, title='输入图片（静态参考）', source=str(reference)))
    for index in range(6):
        text_file = OUT/f'label_{index+1}.txt'
        filters.append(f'[{index}:v]trim=end_frame=321,setpts=PTS-STARTPTS,'
                       'pad=iw:ih+64:0:64:color=0x171c24,'
                       f'drawtext=fontfile={font}:textfile={text_file}:fontcolor=white:'
                       f'fontsize=18:x=12:y=8:line_spacing=7,setsar=1,format=yuv420p[v{index}]')
    filters.append(''.join(f'[v{i}]' for i in range(6))+
                   'xstack=inputs=6:layout=0_0|480_0|960_0|0_672|480_672|960_672:shortest=1[out]')
    output = OUT/'classroom_all_versions_grid_10.7s.mp4'
    command += ['-filter_complex_threads', '4', '-filter_complex', ';'.join(filters),
                '-map', '[out]', '-map_metadata', '-1', '-c:v', 'libx264', '-preset', 'medium',
                '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '30', '-frames:v', '321',
                '-an', '-threads', '8', '-movflags', '+faststart', str(output)]
    (OUT/'ffmpeg_command.json').write_text(json.dumps(command, ensure_ascii=False, indent=2))
    with (OUT/'ffmpeg.log').open('w') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    probe = subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration:format=duration,size',
        '-of', 'json', str(output)], text=True)
    (OUT/'ffprobe.json').write_text(probe)
    info = json.loads(probe)
    stream = info['streams'][0]
    assert int(stream['nb_read_frames'])==321 and stream['r_frame_rate']=='30/1'
    assert (stream['width'],stream['height'])==(1440,1344)
    assert abs(float(info['format']['duration'])-10.7)<1e-6
    report = dict(status='complete', output_video=str(output), layout='3 columns x 2 rows',
                  playback='All five videos start together at frame 0 and play synchronously.',
                  frames=321, fps=30, duration_seconds=10.7, width=1440, height=1344, cells=cells)
    (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-ss','5.333333',
                    '-i',str(output),'-frames:v','1','-q:v','2',str(OUT/'preview.jpg')], check=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
