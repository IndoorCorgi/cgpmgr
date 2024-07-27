#!/usr/bin/env python3
"""
Jetson Nano/JetPack用RPZ-PowerMGRセットアップツール
Indoor Corgi
GitHub: https://github.com/IndoorCorgi/cgpmgr
"""

import os
import re
import subprocess
import pathlib


def main():
  print("""
--- Jetson Nano用RPZ-PowerMGRセットアップツール ---
必要環境
  ハードウェア
  - Jetson Nano Developer Kit
  - Jetson Nano 2GB Developer Kit
  OS
  - JetPack4.6

ステップ1) カーネルのインストール
  RTC用のドライバーを組み込んだカーネルを/boot/Image へインストールします. 
  既存のカーネルは/boot/Image.backup へバックアップされます. 
  モジュールは/lib/modules へインストールします. 
  変更が元に戻ってしまうため, apt upgradeでカーネル(nvidia-l4t-kernelなど)を更新しないようにしてください. 
  nvidia-l4t*パッケージはapt-mark holdで自動アップデート対象から除外されます. 

ステップ2) デバイスツリー登録
  RTCやRPZ-PowerMGRとの通信に使用するピンをデバイスツリーに登録します. 
  以下の信号はRPZ-PowerMGRで使用します. 
  - 40ピンヘッダーJ6のPin#36, #37
  - I2Cアドレス0x20(0x22に切り替え可), 0x68
  変更が元に戻ってしまうため, Jetson-IOで設定を変更しないでください. 

ステップ3) シャットダウンサービスのインストール
  RPZ-PowerMGRのシャットダウン要求信号を受信するサービスを以下にインストールします. 
  - /usr/local/bin/pmgr-sdreq
  - /etc/systemd/system/pmgr-sdreq.service

-------------------------------------------------
重要なデータのバックアップを行い, インターネットに接続されている状態で実行してください. 
特に理由がない限り, 全てのステップを実行してください. 
スーパーユーザー権限が必要な操作ではパスワードが要求されるので, 入力してください.
-------------------------------------------------
  """)

  current_ver_str = subprocess.run(['uname', '-r'], encoding='utf-8',
                                   stdout=subprocess.PIPE).stdout.rstrip('\n')
  print('現在のカーネルバージョン:', current_ver_str)
  if re.search(r'-tegra-extrtc', current_ver_str):
    print('既にカスタムカーネルがインストール済みです. 次のステップに進みます. ')
  else:
    current_ver_split = current_ver_str.split('.')
    current_ver_major = int(current_ver_split[0])
    current_ver_patch = int(current_ver_split[1])
    current_ver_sub = int(re.sub(r'-.*', '', current_ver_split[2]))

    if current_ver_major == 4 and current_ver_patch == 9 and current_ver_sub == 253:
      # JetPack4.6.1 / Jetson Linux R32.7.1: 4.9.253
      source_url = 'https://developer.nvidia.com/embedded/l4t/r32_release_v7.1/sources/t210/public_sources.tbz2'
      install_version = '4.9.253-tegra-extrtc'
    elif current_ver_major == 4 and current_ver_patch == 9 and current_ver_sub == 299:
      # JetPack4.6.3 / Jetson Linux R32.7.3: 4.9.299
      source_url = 'https://developer.nvidia.com/downloads/remack-sdksjetpack-463r32releasev73sourcest210publicsourcestbz2'
      install_version = '4.9.299-tegra-extrtc'
    else:
      # JetPack4.6.5 / Jetson Linux R32.7.5: 4.9.337
      source_url = 'https://developer.nvidia.com/downloads/embedded/l4t/r32_release_v7.5/sources/t210/public_sources.tbz2'
      install_version = '4.9.337-tegra-extrtc'

      if current_ver_major == 4 and current_ver_patch == 9 and current_ver_sub >= 337:
        pass
      else:
        if not ask(message='インストールするカーネルとバージョンが異なるカーネルを使用しています. \n'
                   'セットアップを中止し, JetPack4.6をインストールし直すことを推奨します. '
                   '続行しますか？'):
          return

    if ask(message='\nステップ1) カーネルのインストール を実行しますか？\n'
           'この処理には1時間程度を要します. ', default=True):
      install_kernel(source_url, install_version)

  if ask(message='\nステップ2) デバイスツリーの登録 を実行しますか？', default=True):
    register_devicetree()

  if ask(message='\nステップ3) シャットダウンサービスのインストール を実行しますか？', default=True):
    install_sdreq()

  print('\nセットアップツールを終了します. 変更を反映するにはシステムを再起動してください.')


def install_kernel(source_url, install_ver_str):
  """
  カスタムカーネルをコンパイルしてインストール
  """
  source_archive = pathlib.Path(pathlib.Path(source_url).name)
  kernel_archive = pathlib.Path('Linux_for_Tegra/source/public/kernel_src.tbz2')
  build_dir = pathlib.Path('build')
  kernel_dir = build_dir / 'kernel' / 'kernel-4.9'

  if not (source_archive.exists() or kernel_archive.exists() or kernel_dir.exists()):
    print('ソースコードをダウンロードしています')
    run_check(['wget', source_url])

  if not (kernel_archive.exists() or kernel_dir.exists()):
    print('ソースコードを展開しています')
    run_check(['tar', 'xf', source_archive])

  if not kernel_dir.exists():
    print('カーネルソースを{}に展開しています'.format(build_dir))
    build_dir.mkdir(exist_ok=True)
    run_check(['tar', 'xf', kernel_archive, '-C', build_dir])

  print('{}に移動します'.format(kernel_dir))
  os.chdir(kernel_dir)

  make_ver_str = subprocess.run(['make', 'kernelversion'], encoding='utf-8',
                                stdout=subprocess.PIPE).stdout.rstrip('\n')
  if make_ver_str == install_ver_str:
    print('Makefile設定済み')
  else:
    make_backup = pathlib.Path('Makefile.backup')
    print('Makefileを{}にバックアップしています'.format(make_backup))
    run_check(['cp', 'Makefile', make_backup])
    print('Makefileを設定しています')
    with open('Makefile', 'w') as f:
      run_check(['sed', '-e', 's/EXTRAVERSION =$/EXTRAVERSION = -tegra-extrtc/g', make_backup],
                stdout=f)
    make_ver_str = subprocess.run(['make', 'kernelversion'],
                                  encoding='utf-8',
                                  stdout=subprocess.PIPE).stdout.rstrip('\n')
    if make_ver_str != install_ver_str:
      raise ValueError('意図しないMakefileバージョン: {}'.format(make_ver_str))

  config = pathlib.Path('.config')
  if not config.exists():
    print('コンフィグファイルを設定しています')
    config_contents = subprocess.run(['zcat', '/proc/config.gz'],
                                     encoding='utf-8',
                                     stdout=subprocess.PIPE).stdout
    if not re.search('CONFIG_RTC_DRV_DS1307', config_contents):
      raise ValueError('プロセスのコンフィグ取得失敗. ')

    config_contents = config_contents.splitlines()
    with open('.config', 'w') as f:
      ds1307done = False
      for line in config_contents:
        if re.search('CONFIG_DEBUG_INFO=', line):
          f.write('# CONFIG_DEBUG_INFO is not set\n')
        elif re.search('CONFIG_RTC_HCTOSYS_DEVICE', line):
          f.write('CONFIG_RTC_HCTOSYS_DEVICE="rtc2"\n')
        elif re.search('CONFIG_RTC_SYSTOHC_DEVICE', line):
          f.write('CONFIG_RTC_SYSTOHC_DEVICE="rtc2"\n')
        elif re.search('CONFIG_RTC_DRV_DS1307', line):
          if not ds1307done:
            ds1307done = True
          f.write('CONFIG_RTC_DRV_DS1307=y\n')
          f.write('CONFIG_RTC_DRV_DS1307_HWMON=y\n')
          f.write('# CONFIG_RTC_DRV_DS1307_CENTURY is not set\n')
        else:
          f.write(line)
          f.write('\n')
    run_check(['make', 'olddefconfig'])

  print('カーネルをコンパイルしています')
  run_check(['make', '-j8'])

  if not pathlib.Path('/boot/Image.backup').exists():
    print('現在のカーネルを/boot/Image.backupにバックアップしています')
    run_check(['sudo', 'cp', '/boot/Image', '/boot/Image.backup'])

  print('カーネルを/boot/Imageにインストールしています')
  run_check(['sudo', 'cp', 'arch/arm64/boot/Image', '/boot/Image'])

  module_dir = pathlib.Path('/lib/modules/{}'.format(make_ver_str))
  print('モジュールを{}にインストールしています'.format(module_dir))
  if module_dir.exists():
    run_check(['sudo', 'rm', '-r', module_dir])
  run_check(['sudo', 'make', 'modules_install'])

  print('カーネル関連パッケージをaptの自動アップデート対象から外しています')
  run_check(['sudo', 'apt-mark', 'hold', 'nvidia-l4t-*'])

  print('元のディレクトリに戻ります')
  os.chdir('../../..')
  print('カーネルのインストールが完了しました')


def register_devicetree():
  """
  デバイスツリー登録
  """

  dts = pathlib.Path('rpz_powermgr.dts')
  if not dts.exists():
    print('デバイスツリーソースをダウンロードしています')
    run_check([
        'wget',
        'https://raw.githubusercontent.com/IndoorCorgi/cgpmgr/master/jetson_nano/rpz_powermgr.dts'
    ])

  print('デバイスツリーを登録しています')
  run_check(['sudo', 'dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', '/boot/rpz_powermgr.dtbo', dts])
  run_check(['sudo', '/opt/nvidia/jetson-io/config-by-hardware.py', '-n', 'RPZ-PowerMGR'])
  print('デバイスツリーの登録が完了しました')


def install_sdreq():
  """
  シャットダウンサービスのインストール
  """
  print('シャットダウンサービスをインストールしています')
  run_check([
      'sudo', 'wget', '-P', '/usr/local/bin',
      'https://raw.githubusercontent.com/IndoorCorgi/cgpmgr/master/pmgr-sdreq/pmgr-sdreq'
  ])
  run_check(['sudo', 'chmod', '755', '/usr/local/bin/pmgr-sdreq'])
  run_check([
      'sudo', 'wget', '-P', '/etc/systemd/system',
      'https://raw.githubusercontent.com/IndoorCorgi/cgpmgr/dev/pmgr-sdreq/pmgr-sdreq.service'
  ])
  run_check(['sudo', 'systemctl', 'daemon-reload'])
  run_check(['sudo', 'systemctl', 'enable', 'pmgr-sdreq'])
  run_check(['sudo', 'systemctl', 'start', 'pmgr-sdreq'])
  print('シャットダウンサービスのインストールが完了しました')


def install_control_tool():
  """
  コントロールツールのインストール
  """
  print('コントロールツールをインストールしています')
  run_check(['sudo', 'apt', 'install', 'python3-pip'])
  run_check(['sudo', 'python3', '-m'
             'pip', 'install', 'cgpmgr'])
  print('コントロールツールをインストールが完了しました')


def setup_board_signal():
  """
  コントロールツールでRPZ-PowerMGRの信号を設定
  """
  print('RPZ-PowerMGRと通信に使用する信号を設定しています')
  args = ['cgpmgr', 'cf', '-r', '16', '-c', '26']
  if not ask(message='\n----------------------\n'
             'RPZ-PowerMGRのI2Cアドレスを選択してください. \n'
             '  y :デフォルトのI2Cアドレス0x20 \n'
             '  n :代替I2Cアドレス0x22(基板スイッチで切り替えている場合)\n',
             default=True):
    args.append('-a')
  run_check(args)


def run_check(args, stdout=None):
  """
  コマンドを実行し, 戻り値が0以外ならエラー表示して停止
  """
  comp = subprocess.run(args=args, stdout=stdout)
  if comp.returncode != 0:
    raise ValueError('エラー戻り値: {}'.format(comp.returncode))


def ask(message, default=False):
  """
  メッセージを表示し, ユーザーにYes/Noを選択してもらう

  Args:
    message: 表示するメッセージ
    default: デフォルトの選択. TrueだとYes, FalseだとNoがデフォルトになる. 
  
  Returns:
    bool: Yes選択でTrue, No選択でFalse
  """
  if (default):
    add_str = ' [Y/n]: '
  else:
    add_str = ' [y/N]: '

  while True:
    choice = input(message + add_str).lower()
    if choice in ['y', 'yes']:
      return True
    elif choice in ['n', 'no']:
      return False
    elif choice in ['']:
      return default


if __name__ == '__main__':
  main()
