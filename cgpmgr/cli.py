"""
Raspberry Pi/Jetson Nano電源管理 拡張基板 RPZ-PowerMGR用コントロールツール
Indoor Corgi, https://www.indoorcorgielec.com
GitHub: https://github.com/IndoorCorgi/cgpmgr
Version 1.7

必要環境:
1) Raspberry Pi OS / Jetson Linux, Python3
2) I2Cインターフェース
  Raspberry PiでI2Cを有効にする方法
  https://www.indoorcorgielec.com/resources/raspberry-pi/raspberry-pi-i2c/
3) 電源管理 拡張基板 RPZ-PowerMGR
  製品ページ https://www.indoorcorgielec.com/products/rpz-powermgr/

Usage:
  cgpmgr cf [-a] [-u <sec>] [-d <sec>] [-r <num>] [-c <num>] [-z <num>] [-p <num>] [-w <num>]
  cgpmgr sc [-a] [-o] [-D <date>] <time> (on | off)
  cgpmgr sc [-a] -l <min> (on | off)
  cgpmgr sc [-a] -R <num>
  cgpmgr sc [-a] [-i] -f <file>
  cgpmgr sc [-a]
  cgpmgr me [-a] -L [-f <file>]
  cgpmgr me [-a] -s
  cgpmgr me [-a]
  cgpmgr fw -f <file>
  cgpmgr -h --help

Options:
  cf         コンフィグ情報の変更, 表示をするサブコマンド
  -u <sec>   スタートアップタイマーの秒数を 1 - 250 の範囲で指定. 
             電源ON後, 一定時間経過するまでOFF要求を受け付けなくなる. 
  -d <sec>   シャットダウンタイマーの秒数を 1 - 250 の範囲で指定, 0 で無効. 
             シャットダウン要求送信後, 一定時間が経過すると強制電源OFF. 
  -r <num>   シャットダウン要求信号に使うGPIO番号を 16, 17, 26, 27から指定, 0 で無効
  -c <num>   シャットダウン完了信号に使うGPIO番号を 16, 17, 26, 27から指定, 0 で無効
  -z <num>   タイムゾーンの世界標準時からの差分を分で指定. 日本(+9時間)の場合は540.
  -p <num>   電源自動リカバリー. 1で有効. 0で無効. 
  -w <num>   USB Type-AモバイルバッテリーWake up. 1で有効. 0で無効. 

  sc         電源ON/OFFスケジュールに関するサブコマンド. 
             オプションを何も指定しないと現在登録済みのスケジュールを表示する. 
  -o         指定すると, 登録するスケジュールがOneTime(1回のみ)になる. 
             省略するとRepeat(繰り返し). 
  -D <date>  登録するスケジュールの月/日を指定. *か**で全てに一致. 
             日はSun, Mon, Tue, Wed, Thu, Fri, Satで曜日も指定可能. 例)5/10, , 9/Sun, */15. 
  <time>     登録するスケジュールの時:分を指定. *か**で全てに一致. 
             分は*指定不可. 例)21:30, *:45
  on         電源をONするスケジュールを登録する. 
  off        電源をOFFするスケジュールを登録する. 
  -l <min>   現在からmin分後にスケジュールを登録. 秒は切り上げになる. 0-999の範囲で指定. 
             0を指定すると可能な限り早いスケジュールになる. 
             このオプションで登録するとOneTime(1回のみ)になる. 
  -R <num>   指定すると登録済みスケジュールから指定番号のものを削除. 255を指定すると全て削除. 
  -i         スケジュールをcsvファイルから読み出して追加する. 
             省略すると登録済みスケジュールをcsvファイルに保存する.

  me         Raspberry Pi/Jetson Nanoの消費電流測定, 結果ログを行うサブコマンド. 
             オプションを指定しないと直近の電流測定値を表示. 
  -L         記録されている消費電流値を読み出す. 
             電源ONから1秒ごとに最大1時間まで記録可能.  
  -s         消費電流の記録をリセットして再スタート. 1秒ごと最大1時間まで記録可能.

  fw         ファームウェアを-fで指定したものに書き換える.

  共通オプション
  -a         I2Cセカンダリアドレス0x22を使用. 
             DSW1-6がONの状態でRunモードに入るとセカンダリI2Cアドレスになる. 
  -f <file>  scサブコマンドでは保存, 読み出しをするcsvファイルを指定. 
             meサブコマンドでは電流値を保存するファイルを指定.
  -h --help  ヘルプを表示
"""

import os
import time
import datetime
import re
import struct
import subprocess
import hashlib
import smbus2
import RPi.GPIO as GPIO

i2c_adr = 0x20
compatible_fw = {1: 7, 2: 4}
sig2gpio = [0, 16, 17, 26, 27]  # SIG番号とGPIO番号の対応
dow2str = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']  # スケジュールデータは日曜が1, 土曜が7
gpio_rst = 7
gpio_boot = 25
fw_ver = []

# ファームウェアハッシュ値
known_hash = [
    'cf0d1818ade696bc5b7af150ff4a085266fdc829f196f26ed2ed127b7ba12eb3',  # Ver1.0
    '1a6fdf815b5b23a6e39c79d6b734bfd3bd51ddf59b803912425bfc07504f0d1b',  # Ver1.1
    '5764c3cc8442930997fefcc048e35a8242df9bdcdf5f302ed4fb43f1a4fd8c24',  # Ver1.2
    'a37fe6f36a4e99bab07e3106cb99306d13f88d4c72c68b309a4fd9eb8e4c44e8',  # Ver1.3
    '36313403baab9d50183f17d0f9cea991455baf7b1b0478e1ef8773cee0ea91cc',  # Ver1.4
    'c3f465e5c8e2e004b23d85a6f5846931e106fd8a06715d48e54750c875cfe882',  # Ver1.5
    '6aff47c6ceb831cf48662a71dcc0090b437a6129aa8b29d5bcebb5e0cd46e98b',  # Ver1.6
    '14fcce2876dc004f5598d50d36eef4898e048197566a5de319ede510019df031',  # Ver1.7
    '0bdb41e819fcd8380a9bf1f551a6a7692bd22bcdb3734580413e4401fa613490',  # Ver2.0
    'f5aa9ab42affd8004238bf1f747d93095b5138602473660eb7965a24d03b167b',  # Ver2.1
    'a49c1fa3c1f540fcbb77d69be4d599791d3a5a88508e7519aaab2c5426f0fb0c',  # Ver2.2
    'c39cc7100644abafd3f69bc0b61304093b4a535097fd637282837ed8fe007821',  # Ver2.3
    '39498cf80856838cf9676c0e40316d1e7ae283d03179d1d538d1cca992a0e9cc',  # Ver2.4
]


def cli():
  """
  コマンドラインツールを実行
  """
  global i2c
  global i2c_adr
  global fw_ver

  try:
    from docopt import docopt
  except ImportError:
    print('docoptのインポートに失敗しました. sudo python3 -m pip install docopt コマンドでインストールして下さい. ')
    return

  args = docopt(__doc__)

  try:
    i2c = smbus2.SMBus(1)
  except FileNotFoundError:
    print('I2Cバスが開けませんでした. I2Cが有効になっているか確認して下さい. ')
    return

  # セカンダリI2Cアドレスを使用
  if args['-a']:
    i2c_adr = 0x22

  # ファームウェア書き換えの場合はスキップ
  if not args['fw']:
    # IDチェック
    devid = i2c_read(0x10, 4)
    if 0x52474D50 != devid[0] + (devid[1] << 8) + (devid[2] << 16) + (devid[3] << 24):
      print('RPZ-PowerMGRとの通信に失敗しました. 拡張基板が正しくセットアップされているか確認して下さい. ')
      print('DSW1-6でセカンダリI2Cアドレスを指定している場合は-aオプションを指定して下さい. ')
      return

    # ファームウェアバージョンチェック
    fw_ver = i2c_read(0x14, 2)
    r = False
    if fw_ver[1] in compatible_fw:
      if fw_ver[0] <= compatible_fw[fw_ver[1]]:
        r = True
    if not r:
      print('RPZ-PowerMGRに新しいファームウェアを確認しました. 以下のコマンドで最新版のcgpmgrをインストールしてください. ')
      print('sudo python3 -m pip install -U cgpmgr')
      return

  #----------------------------
  # コンフィグ情報の設定, 表示
  if args['cf']:
    if args['-u'] != None:
      if not check_digit('-u', args['-u'], 1, 250):
        return
      i2c_write(0x16, [int(args['-u'])])
      print('スタートアップタイマーを{}秒に設定しました. '.format(args['-u']))

    if args['-d'] != None:
      if not check_digit('-d', args['-d'], 0, 250):
        return
      i2c_write(0x17, [int(args['-d'])])
      print('シャットダウンタイマーを' +
            ('無効にしました.' if 0 == int(args['-d']) else '{}秒に設定しました. '.format(args['-d'])))

    r = i2c_read(0x18, 1)[0]
    c = i2c_read(0x19, 1)[0]
    if args['-r'] != None:
      if not check_digit_list('-r', args['-r'], sig2gpio):
        return
      r = sig2gpio.index(int(args['-r']))

    if args['-c'] != None:
      if not check_digit_list('-c', args['-c'], sig2gpio):
        return
      c = sig2gpio.index(int(args['-c']))

    if r != 0 and c != 0 and r == c:
      print('シャットダウン要求と完了信号を同じ番号に割り付けることはできません. ')
      return

    if args['-r'] != None:
      if args['-c'] != None:
        i2c_write(0x19, [0])  # 番号が重なる可能性があるので一度無効化
      i2c_write(0x18, [r])
      print('シャットダウン要求信号を' +
            ('無効にしました.' if 0 == int(args['-r']) else 'GPIO{} に設定しました. '.format(args['-r'])))

    if args['-c'] != None:
      i2c_write(0x19, [c])
      print('シャットダウン完了信号を' +
            ('無効にしました.' if 0 == int(args['-c']) else 'GPIO{} に設定しました. '.format(args['-c'])))

    if args['-z'] != None:
      if not check_digit('-z', args['-z'], -720, 840):
        return
      i2c_write(0x1A, list(struct.pack("h", int(args['-z']))))

    if args['-p'] != None:
      if not ((1 == fw_ver[1] and 4 <= fw_ver[0]) or (2 == fw_ver[1] and 1 <= fw_ver[0])):
        print('-p は現在のファームウェアで利用できません. Webサイトの説明に沿って最新のファームウェアへアップデートして下さい. ')
        return
      if not check_digit('-p', args['-p'], 0, 1):
        return
      i2c_write(0x1C, [int(args['-p'])])
      print('電源自動リカバリーを' + ('無効にしました.' if 0 == int(args['-p']) else '有効にしました. '))

    if args['-w'] != None:
      if not ((1 == fw_ver[1] and 4 <= fw_ver[0]) or (2 == fw_ver[1] and 1 <= fw_ver[0])):
        print('-w は現在のファームウェアで利用できません. Webサイトの説明に沿って最新のファームウェアへアップデートして下さい. ')
        return
      if not check_digit('-w', args['-w'], 0, 1):
        return
      i2c_write(0x1D, [int(args['-w'])])
      print('USB Type-AモバイルバッテリーWake upを' + ('無効にしました.' if 0 == int(args['-w']) else '有効にしました. '))

    # コンフィグ読み出し
    rpi_startup_timer = i2c_read(0x16, 1)[0]
    rpi_sd_timer = i2c_read(0x17, 1)[0]
    sig_sd_request = i2c_read(0x18, 1)[0]
    sig_sd_complete = i2c_read(0x19, 1)[0]
    time_zone_min = i2c_read(0x1A, 2)
    print('コンフィグ情報')
    print('  ファームウェアバージョン: {}.{}'.format(fw_ver[1], fw_ver[0]))
    print('  スタートアップタイマー: {}秒'.format(rpi_startup_timer))
    print('  シャットダウンタイマー: ' + ('無効' if rpi_sd_timer == 0 else '{}秒'.format(rpi_sd_timer)))
    print('  シャットダウン要求信号: ' +
          ('無効' if sig_sd_request == 0 else 'GPIO{}'.format(sig2gpio[sig_sd_request])))
    print('  シャットダウン完了信号: ' +
          ('無効' if sig_sd_complete == 0 else 'GPIO{}'.format(sig2gpio[sig_sd_complete])))
    print('  タイムゾーン設定: ' + ('{}'.format(struct.unpack("h", bytes(time_zone_min))[0])))

    # ファームウェアVersion1.4 / 2.1以降で追加されたオプション
    if (1 == fw_ver[1] and 4 <= fw_ver[0]) or (2 == fw_ver[1] and 1 <= fw_ver[0]):
      auto_run = i2c_read(0x1C, 1)[0]
      usba_wake_up = i2c_read(0x1D, 1)[0]
      print('  電源自動リカバリー: ' + ('無効' if auto_run == 0 else '有効'))
      print('  USB Type-Aウェイクアップ: ' + ('無効' if usba_wake_up == 0 else '有効'))

  #----------------------------
  # スケジュールの追加, 削除, 表示
  if args['sc']:
    sch = [0x80] * 4
    sch[0] = 0
    wc = False  # ワイルドカードが指定されたらTrue

    if args['<time>'] != None:
      data = args['<time>'].split(':')
      if len(data) != 2:
        print('<time>で指定した値{}が正しくありません. '.format(args['<time>']))
        return

      # 分
      if check_digit('<time>', data[1], 0, 59):
        sch[0] = int(data[1])
      else:
        return

      # 時
      if data[0] in ['*', '**']:
        wc = True
      elif check_digit('<time>', data[0], 0, 23):
        sch[1] = int(data[0])
      else:
        return

    if args['-D'] != None:
      data = args['-D'].split('/')
      if len(data) != 2:
        print('-Dで指定した値{}が正しくありません. '.format(args['-D']))
        return

      if wc and fw_ver[1] == 1 and fw_ver[0] <= 2:
        print('<time>に*を指定した場合は-Dオプションは指定できません. ')
        print('ファームウェアを更新することで指定可能になります.')
        return

      # 日
      if data[1] in ['*', '**']:
        wc = True
      elif data[1].capitalize() in dow2str:
        sch[2] = 0x40 | (dow2str.index(data[1].capitalize()) + 1)
      elif check_digit('-D', data[1], 1, 31):
        sch[2] = int(data[1])
      else:
        print('-Dで指定した値{}が正しくありません. '.format(args['-D']))
        return

      # 月
      if data[0] in ['*', '**']:
        pass
      elif check_digit('-D', data[0], 1, 12) and not (wc and fw_ver[1] == 1 and fw_ver[0] <= 2):
        sch[3] = int(data[0])
      else:
        print('-Dで指定した値{}が正しくありません. '.format(args['-D']))
        return

    if args['on']:
      sch[0] &= 0xBF

    if args['off']:
      sch[0] |= 0x40

    if args['-o']:
      sch[0] |= 0x80

    if args['-l'] != None:
      if not check_digit('-l', args['-l'], 0, 999):
        return

      # -l 0 offかつファームウェアが対応している場合, すぐにシャットダウンリクエスト
      if 0 == int(args['-l']):
        if (fw_ver[1] == 1 and fw_ver[0] >= 6) or (fw_ver[1] == 2 and fw_ver[0] >= 3):
          print('シャットダウン要求を開始します')
          i2c_write(0x40, [0xFF])
          return

      dtrtc = read_rtc()
      delay = int(args['-l'])
      if delay == 0:
        dt = dtrtc + datetime.timedelta(seconds=75)  # 通信, 計算マージン15秒 + 桁繰り上げ用60秒
      else:
        dt = dtrtc + datetime.timedelta(minutes=1 + delay)
      sch[0] |= dt.minute | 0x80
      sch[1] = dt.hour
      sch[2] = dt.day
      sch[3] = dt.month

    if args['on'] or args['off']:
      sch_count = i2c_read(0x30, 1)[0]  # 登録済みスケジュールの数
      if sch_count >= 250:
        print('スケジュール登録数の上限に達しています. これ以上登録できません')
        return
      i2c_write(0x32, sch)
      print('スケジュールを登録しました')

    # 削除オプション
    sch_count = i2c_read(0x30, 1)[0]  # 登録済みスケジュールの数
    numbers = list(range(1, sch_count + 1))  # 登録済みスケジュール番号のリスト
    numbers.append(0xFF)  # 全スケジュール削除用の特殊番号
    if args['-R'] != None:
      if not check_digit_list('-R', args['-R'], numbers):
        return

      i2c_write(0x36, [int(args['-R'])])
      if int(args['-R']) == 0xFF:
        print('全てのスケジュールを削除しました. ')
      else:
        print('スケジュール#{:03}を削除しました. '.format(int(args['-R'])))

    # csvファイルから登録
    sch_list = []
    if (args['-f'] != None) and args['-i']:
      try:
        with open(args['-f'], 'r') as f:
          line_num = 0
          for line in f:
            line_num += 1

            # 1行目, 空白行は無視
            if line_num == 1 or line == '\n':
              continue

            sch = csv2sch(line.rstrip('\n'))

            # 失敗
            if len(sch) == 0:
              print('csvファイル{}行目の構文にエラーがあります. 登録できませんでした. '.format(line_num))
              print(line.rstrip('\n'))
              return
            else:
              sch_list.append(sch)
      except:
        print('ファイル {} の読み込みに失敗しました.'.format(args['-f']))
        return

      sch_count = i2c_read(0x30, 1)[0]  # 登録済みスケジュールの数
      if sch_count + len(sch_list) > 250:
        print('スケジュールは合計250個を超えて登録できません. ')
        return

      for sch in sch_list:
        i2c_write(0x32, sch)

      print('ファイル {} からスケジュールを{}個登録しました.'.format(args['-f'], len(sch_list)))

    # 登録済みスケジュールの読み出し
    sch_count = i2c_read(0x30, 1)[0]  # 登録済みスケジュールの数
    if sch_count == 0:
      print('登録さているスケジュールはありません. ')
      return

    print('登録されているスケジュールが{}個あります. '.format(sch_count))

    for i in range(sch_count):
      i2c_write(0x31, [i + 1])
      sch = i2c_read(0x32, 4)
      print('  #{:03} '.format(i + 1), end='')
      print(sch2str(sch))

    # csvファイルに保存
    if (args['-f'] != None) and not args['-i']:
      if os.path.exists(args['-f']):
        if not ask('ファイル {} は存在します. 上書きしてよいですか？'.format(args['-f'])):
          return
      try:
        # サブディレクトリが指定されている場合は作成
        if len(os.path.dirname(args['-f'])) > 0:
          os.makedirs(os.path.dirname(args['-f']), exist_ok=True)
        with open(args['-f'], 'w') as f:
          f.write('ON/OFF, Repeat/OneTime, Month, Day, Hour, Minute\n')
          for i in range(sch_count):
            i2c_write(0x31, [i + 1])
            sch = i2c_read(0x32, 4)
            f.write(sch2csv(sch) + '\n')

          print('ファイル {} へ保存しました.'.format(args['-f']))
      except:
        print('ファイル {} へ保存に失敗しました.'.format(args['-f']))

  #----------------------------
  # 電流測定
  if args['me']:
    if args['-L']:
      count = i2c_read(0x22, 2)
      count = count[0] + (count[1] << 8)
      if count > 3600:
        print('データの読み出しに失敗しました.')
        return
      print('{}秒分の電流値の記録データがあります.'.format(count))

      # ファイルに保存
      if (args['-f'] != None):
        if os.path.exists(args['-f']):
          if not ask('ファイル {} は存在します. 上書きしてよいですか？'.format(args['-f'])):
            return
        try:
          # サブディレクトリが指定されている場合は作成
          if len(os.path.dirname(args['-f'])) > 0:
            os.makedirs(os.path.dirname(args['-f']), exist_ok=True)
          with open(args['-f'], 'w') as f:
            f.write('時間[s], 電流[mA]\n')
            for i in range(count):
              i2c_write(0x24, [i & 0xFF, i >> 8])
              curr = i2c_read(0x26, 2)
              f.write('{}, {}\n'.format(i, (curr[1] << 8) + curr[0]))

            print('ファイル {} へ保存しました.'.format(args['-f']))
        except:
          print('ファイル {} へ保存に失敗しました.'.format(args['-f']))
      else:
        # 画面に表示
        print('時間[s], 電流[mA]')
        for i in range(count):
          i2c_write(0x24, [i & 0xFF, i >> 8])
          curr = i2c_read(0x26, 2)
          print('{}, {}'.format(i, (curr[1] << 8) + curr[0]))

    elif args['-s']:
      i2c_write(0x24, [0xFF, 0xFF])
      print('電流値のログをリセットしました. 現在から毎秒, 最大1時間まで記録します. ')

    else:
      curr = i2c_read(0x20, 2)
      print('電流値 {}[mA]'.format((curr[1] << 8) + curr[0]))

  #----------------------------
  # ファームウェア書き換え
  if args['fw']:
    try:
      res = subprocess.run(['stm32flash'],
                           encoding='utf-8',
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
    except:
      print('stm32flashが見つかりませんでした. sudo apt install stm32flash コマンドでインストールして下さい. ')
      return

    try:
      with open(args['-f'], 'rb') as f:
        hash = hashlib.sha256(f.read()).hexdigest()
      if not hash in known_hash:
        if not ask('ファイル {} は既知のファームウェアではありません. 続行しますか？'.format(args['-f'])):
          return
    except:
      print('ファイル {} の読み込みに失敗しました.'.format(args['-f']))
      return

    print('RPZ-PowerMGRのスイッチDSW1-1, 3, 4がONになっていることを確認してください. ')
    if not ask('ファームウェア書き換えを開始してよろしいですか？'):
      return

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(gpio_rst, GPIO.OUT)
    GPIO.setup(gpio_boot, GPIO.OUT)

    boot_loader()
    res = subprocess.run(['stm32flash', '/dev/i2c-1', '-a', '0x42', '-j'],
                         encoding='utf-8',
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    if re.search(r'Fail', res.stdout):
      print('ファームウェアの書き換え中にエラーが発生しました')
      GPIO.cleanup(gpio_rst)
      GPIO.cleanup(gpio_boot)
      return

    boot_loader()
    res = subprocess.run(['stm32flash', '/dev/i2c-1', '-a', '0x42', '-k'],
                         encoding='utf-8',
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    if re.search(r'Fail', res.stdout):
      print('ファームウェアの書き換え中にエラーが発生しました')
      GPIO.cleanup(gpio_rst)
      GPIO.cleanup(gpio_boot)
      return

    boot_loader()
    res = subprocess.run(
        ['stm32flash', '/dev/i2c-1', '-a', '0x42', '-e 0', '-w', args['-f'], '-v', '-R'])
    if res.returncode != 0:
      print('ファームウェアの書き換え中にエラーが発生しました')
      GPIO.cleanup(gpio_rst)
      GPIO.cleanup(gpio_boot)
      return

    GPIO.cleanup(gpio_rst)
    GPIO.cleanup(gpio_boot)
    print('ファームウェアの書き換えが完了しました. ')


def i2c_read(addr, length):
  """
  I2Cで指定アドレスから読み出す

  Args:
    addr: 読み出しアドレス. 8bit. 
    length: 読み出しデータの長さ. バイト数.
  
  Returns:
    list: 読み出しデータのリスト. 通信失敗で全て0を返す. 
  """
  try:
    return i2c.read_i2c_block_data(i2c_adr, addr, length)
  except IOError:
    return [0 for i in range(length)]


def i2c_write(addr, data):
  """
  I2Cで指定アドレスに書き込む

  Args:
    addr: 書き込みアドレス. 8bit. 
    data(list): 書き込みデータのリスト. [1バイト目, 2バイト目, ...]
  """
  try:
    i2c.write_i2c_block_data(i2c_adr, addr, data)
  except IOError:
    return


def check_digit(option, num, min, max):
  """
  文字列numが整数かチェックし, min-maxの範囲の数値であればTrueを返す

  Args:
    option: エラーメッセージに表示する文字列を指定. ''の場合はエラーメッセージを表示しない. 
    num: チェックする文字列
    min: 数値の範囲の下限
    max: 数値の範囲の上限
  
  Returns:
    bool: Trueなら問題なし. Falseなら整数でないか範囲外. 
  """
  val = False

  try:
    num_int = int(num)
    if num_int >= min and num_int <= max:
      val = True
  except ValueError:
    pass

  if not val and len(option) > 0:
    print('{} で指定した値 {} が正しくありません. {} - {} の範囲の数値を指定してください. '.format(option, num, min, max))
  return val


def check_digit_list(option, num, val_list):
  """
  文字列numが整数で, val_listのいずれかに一致すればTrueを返す

  Args:
    option: エラーメッセージに表示する文字列を指定. ''の場合はエラーメッセージを表示しない. 
    num: チェックする文字列
    val_list: 候補が入った整数のリスト. 
  
  Returns:
    bool: Trueなら問題なし. Falseなら整数でないか候補にない値. 
  """
  val = False
  try:
    num_int = int(num)
    if num_int in val_list:
      val = True
  except ValueError:
    pass

  if not val and len(option) > 0:
    print('{} で指定した値 {} が正しくありません. {} のいずれかの数値を指定してください. '.format(option, num, val_list))
  return val


def print_time_bcd(bcd):
  """
  BCDフォーマットの7バイトの時刻データを画面に表示
  bcd[0]: 秒
  bcd[1]: 分
  bcd[2]: 時
  bcd[3]: 曜日
  bcd[4]: 日
  bcd[5]: 月
  bcd[6]: 年
  
  Args:
    bcd: BCDフォーマットの7バイトデータのリスト
  """
  print('20{}{}/{}{}/{}{} '.format(bcd[6] >> 4, bcd[6] & 0xF, bcd[5] >> 4, bcd[5] & 0xF,
                                   bcd[4] >> 4, bcd[4] & 0xF),
        end='')
  if bcd[3] == 1:
    print('日 ', end='')
  elif bcd[3] == 2:
    print('月 ', end='')
  elif bcd[3] == 3:
    print('火 ', end='')
  elif bcd[3] == 4:
    print('水 ', end='')
  elif bcd[3] == 5:
    print('木 ', end='')
  elif bcd[3] == 6:
    print('金 ', end='')
  elif bcd[3] == 7:
    print('土 ', end='')
  print('{}{}:{}{}:{}{}'.format(bcd[2] >> 4, bcd[2] & 0xF, bcd[1] >> 4, bcd[1] & 0xF, bcd[0] >> 4,
                                bcd[0] & 0xF))


def make_bcd(year, month, date, dow, hour, minute, second):
  """
  指定日時から, BCDフォーマットの7バイトのデータを生成

  Args:
    year: 年
    month: 月
    date: 日
    dow: 曜日. 日曜日が1, 土曜日が7
    hour: 時
    minute: 分
    second: 秒
  
  Returns:
    list: BCDフォーマットの7バイトデータのリスト
  """
  bcd = [0] * 7
  bcd[0] = second % 10 + (second // 10 << 4)
  bcd[1] = minute % 10 + (minute // 10 << 4)
  bcd[2] = hour % 10 + (hour // 10 << 4)
  bcd[3] = dow
  bcd[4] = date % 10 + (date // 10 << 4)
  bcd[5] = month % 10 + (month // 10 << 4)
  year %= 100
  bcd[6] = year % 10 + (year // 10 << 4)
  return bcd


def read_rtc():
  """
  RTCの時刻を読み出してdatetimeに変換. タイムゾーンはRPZ-PowerMGRの設定値を読み出して計算. 

  Returns:
    datetime: タイムゾーン補正後のRTC時刻 
  """
  bcd = i2c_read(0x0, 7)
  year = (bcd[6] & 0xF) + (bcd[6] >> 4) * 10 + 2000
  month = (bcd[5] & 0xF) + (bcd[5] >> 4) * 10
  day = (bcd[4] & 0xF) + (bcd[4] >> 4) * 10
  hour = (bcd[2] & 0xF) + (bcd[2] >> 4) * 10
  minute = (bcd[1] & 0xF) + (bcd[1] >> 4) * 10
  second = (bcd[0] & 0xF) + (bcd[0] >> 4) * 10
  dt = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)

  # RTCはUTCなのでタイムゾーン設定を読み出して補正
  time_zone_min = i2c_read(0x1A, 2)
  return dt + datetime.timedelta(minutes=struct.unpack("h", bytes(time_zone_min))[0])


def sch2str(sch):
  """
  スケジュールデータを文字列に変換

  Args:
    sch: RPZ-PowerMGRの4バイトのスケジュールデータのリスト. ファームウェア仕様書参照. 
  
  Returns:
    str: 文字列に直したスケジュール
  """
  s = ''
  if (sch[0] & 0x40) == 0:
    s += 'ON  '
  else:
    s += 'OFF '

  if (sch[0] >> 7) == 0:
    s += 'Repeat  '
  else:
    s += 'OneTime '

  if (sch[3] >> 7) == 0:
    s += '{:02}/'.format(sch[3])
  else:
    s += '**/'

  if (sch[2] >> 7) == 0:
    if (sch[2] & 0x40) == 0:
      s += '{:02}  '.format(sch[2])
    else:
      s += '{} '.format(dow2str[(sch[2] & 0x7) - 1])
  else:
    s += '**  '

  if (sch[1] >> 7) == 0:
    s += '{:02}:'.format(sch[1])
  else:
    s += '**:'

  s += '{:02}'.format(sch[0] & 0x3F)
  return s


def sch2csv(sch):
  """
  スケジュールデータをcsvフォーマットの文字列に変換

  Args:
    sch: RPZ-PowerMGRの4バイトのスケジュールデータのリスト. ファームウェア仕様書参照. 
  
  Returns:
    str: csvフォーマットの文字列に直したスケジュール
  """
  s = ''
  if (sch[0] & 0x40) == 0:
    s += 'ON, '
  else:
    s += 'OFF, '

  if (sch[0] >> 7) == 0:
    s += 'Repeat, '
  else:
    s += 'OneTime, '

  if (sch[3] >> 7) == 0:
    s += '{:02}, '.format(sch[3])
  else:
    s += '*, '

  if (sch[2] >> 7) == 0:
    if (sch[2] & 0x40) == 0:
      s += '{:02}, '.format(sch[2])
    else:
      s += '{}, '.format(dow2str[(sch[2] & 0x7) - 1])
  else:
    s += '*, '

  if (sch[1] >> 7) == 0:
    s += '{:02}, '.format(sch[1])
  else:
    s += '*, '

  s += '{:02}'.format(sch[0] & 0x3F)
  return s


def csv2sch(csv_str):
  """
  csvファイルの1行をスケジュールデータ4バイトに変換

  Args:
    csv_str: csvフォーマットの文字列
    sch: RPZ-PowerMGRの4バイトのスケジュールデータのリスト. ファームウェア仕様書参照. 
  
  Returns:
    list: RPZ-PowerMGRの4バイトのスケジュールデータのリスト. 失敗したら空のリストを返す. 
  """
  global fw_ver
  data = re.split(r'\s*,\s*', csv_str)

  # 数が不足
  if len(data) < 6:
    return []

  sch = [0] * 4
  wc = False

  # ON/OFF
  if data[0].lower() in ['on']:
    pass
  elif data[0].lower() in ['off']:
    sch[0] |= 0x40
  else:
    return []

  # Repeat/OneTime
  if data[1].lower() in ['repeat', 'r']:
    pass
  elif data[1].lower() in ['onetime', 'o']:
    sch[0] |= 0x80
  else:
    return []

  # 分
  if check_digit('', data[5], 0, 59):
    sch[0] |= int(data[5])
  else:
    return []

  # 時
  if data[4] in ['*', '**']:
    sch[1] = 0x80
    wc = True
  elif check_digit('', data[4], 0, 23):
    sch[1] = int(data[4])
  else:
    return []

  # 日
  if data[3] in ['*', '**']:
    sch[2] = 0x80
    wc = True
  elif check_digit('', data[3], 1, 31) and not (wc and fw_ver[1] == 1 and fw_ver[0] <= 2):
    sch[2] = int(data[3])
  elif data[3].capitalize() in dow2str:
    sch[2] = 0x40 | (dow2str.index(data[3].capitalize()) + 1)
  else:
    return []

  # 月
  if data[2] in ['*', '**']:
    sch[3] = 0x80
    wc = True
  elif check_digit('', data[2], 1, 12) and not (wc and fw_ver[1] == 1 and fw_ver[0] <= 2):
    sch[3] = int(data[2])
  else:
    return []

  return sch


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


def boot_loader():
  """
  RPZ-PowerMGRのコントローラーをブートローダーから起動する. 
  DSW1-1, 3, 4をONにしておく必要がある. 
  """
  GPIO.output(gpio_boot, 1)
  time.sleep(0.01)
  GPIO.output(gpio_rst, 0)
  time.sleep(0.01)
  GPIO.output(gpio_rst, 1)
  time.sleep(0.01)
  GPIO.output(gpio_boot, 0)
  time.sleep(0.01)
