import pickle
import gzip
import os

# 最新の.splotファイルを探す
splot_files = [f for f in os.listdir('.') if f.endswith('.splot')]
if splot_files:
    latest_file = max(splot_files, key=lambda f: os.path.getmtime(f))
    print(f'Loading: {latest_file}')
    
    with gzip.open(latest_file, 'rb') as f:
        state = pickle.load(f)
    
    # legend_cfgsを確認
    if 'pages' in state:
        for i, page in enumerate(state['pages']):
            print(f'\nPage {i}:')
            if 'legend_cfgs' in page:
                print('  legend_cfgs:', page['legend_cfgs'])
            if 'axes_info' in page:
                print('  axes_info keys:', list(page['axes_info'].keys()))
                for ax_idx, info in page['axes_info'].items():
                    print(f'    Axis {ax_idx}: font_name={info.get("font_name")}, font_size={info.get("font_size")}')
else:
    print('No .splot files found')
