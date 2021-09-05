"""
Raspberry Pi電源管理 拡張基板 RPZ-PowerMGR用コントロールツール
Indoor Corgi, https://www.indoorcorgielec.com
Version 1.0

必要環境:
1) I2Cインターフェース
  Raspberry PiでI2Cを有効にして下さい
  https://www.indoorcorgielec.com/resources/raspberry-pi/raspberry-pi-i2c/
2) 電源管理 拡張基板 RPZ-PowerMGR
  製品ページ https://www.indoorcorgielec.com/products/rpz-powermgr/

Usage:
  cgpmgr cf [-a] [-u <sec>] [-d <sec>] [-r <num>] [-c <num>] [-z <num>]
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

  sc         電源ON/OFFスケジュールに関するサブコマンド. 
             オプションを何も指定しないと現在登録済みのスケジュールを表示する. 
  -o         指定すると, 登録するスケジュールがOneTime(1回のみ)になる. 
             省略するとRepeat(繰り返し). 
  -D <date>  登録するスケジュールの月/日を指定. *か**で全てに一致. 
             日はSun, Mon, Tue, Wed, Thu, Fri, Satで曜日も指定可能. 
             日は必ず指定する. 省略すると*/*. 例)5/10, , 9/Sun, */15. 
  <time>     登録するスケジュールの時:分を指定. *か**で全てに一致. 
             時を*にしたら月日も必ず*になる(-D 指定不可). 分は*指定不可. 例)21:30, *:45
  on         電源をONするスケジュールを登録する. 
  off        電源をOFFするスケジュールを登録する. 
  -l <min>   現在からmin分後にスケジュールを登録. 秒は切り上げになる. 1-999の範囲で指定. 
             このオプションで登録するとOneTime(1回のみ)になる. 
  -R <num>   指定すると登録済みスケジュールから指定番号のものを削除. 255を指定すると全て削除. 
  -i         スケジュールをcsvファイルから読み出して追加する. 
             省略すると登録済みスケジュールをcsvファイルに保存する.

  me         Raspberry Piの消費電流測定, 結果ログを行うサブコマンド. 
             オプションを指定しないと直近の電流測定値を表示. 
  -L         記録されているRaspberry Piの消費電流値を読み出す. 
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
import smbus
import RPi.GPIO as GPIO

i2c_adr = 0x20
compatible_fw = {1: 3}
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
]


#----------------------------
# メインルーチン
def main():
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
    i2c = smbus.SMBus(1)
  except IOError:
    print('I2Cの初期化に失敗しました. I2Cが有効になっているか確認して下さい. ')

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
      print('RPZ-PowerMGRに新しいファームウェアを確認しました. 最新版の pmgr.py をダウンロードしてください. ')
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
      print('シャットダウンタイマーを' + ('無効にしました.' if 0 == int(args['-d']) else '{}秒に設定しました. '.format(args['-d'])))

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
      print('シャットダウン要求信号を' + ('無効にしました.' if 0 == int(args['-r']) else 'GPIO{} に設定しました. '.format(args['-r'])))

    if args['-c'] != None:
      i2c_write(0x19, [c])
      print('シャットダウン完了信号を' + ('無効にしました.' if 0 == int(args['-c']) else 'GPIO{} に設定しました. '.format(args['-c'])))

    if args['-z'] != None:
      if not check_digit('-z', args['-z'], -720, 840):
        return
      i2c_write(0x1A, list(struct.pack("h", int(args['-z']))))

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
    print('  シャットダウン要求信号: ' + ('無効' if sig_sd_request == 0 else 'GPIO{}'.format(sig2gpio[sig_sd_request])))
    print('  シャットダウン完了信号: ' + ('無効' if sig_sd_complete == 0 else 'GPIO{}'.format(sig2gpio[sig_sd_complete])))
    print('  タイムゾーン設定: ' + ('{}'.format(struct.unpack("h", bytes(time_zone_min))[0])))

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
      if not check_digit('-l', args['-l'], 1, 999):
        return
      dtrtc = read_rtc()
      dt = dtrtc + datetime.timedelta(minutes=1 + int(args['-l']))
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
      print('Raspberry Pi電流値のログをリセットしました. 現在から毎秒, 最大1時間まで記録します. ')

    else:
      curr = i2c_read(0x20, 2)
      print('Raspberry Pi電流値 {}[mA]'.format((curr[1] << 8) + curr[0]))

  #----------------------------
  # ファームウェア書き換え
  if args['fw']:
    try:
      res = subprocess.run(['stm32flash'], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
    res = subprocess.run(['stm32flash', '/dev/i2c-1', '-a', '0x42', '-e 0', '-w', args['-f'], '-v', '-R'])
    if res.returncode != 0:
      print('ファームウェアの書き換え中にエラーが発生しました')
      GPIO.cleanup(gpio_rst)
      GPIO.cleanup(gpio_boot)
      return

    GPIO.cleanup(gpio_rst)
    GPIO.cleanup(gpio_boot)
    print('ファームウェアの書き換えが完了しました. ')


#----------------------------
# サブルーチン


# I2Cで指定アドレスから読み出す
#   length : 読み出すバイト数. 32バイトまで.
def i2c_read(addr, length):
  try:
    return i2c.read_i2c_block_data(i2c_adr, addr, length)
  except IOError:
    return [0 for i in range(length)]


# I2Cで指定アドレスに書き込む
#   data : バイト配列. 32バイトまで.
def i2c_write(addr, data):
  try:
    i2c.write_i2c_block_data(i2c_adr, addr, data)
  except IOError:
    return


# 文字列numがmin-maxの範囲の数値であればTrueを返す
#   option : エラーメッセージ用にオプションを指定する.
def check_digit(option, num, min, max):
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


# 文字列numがval_listに含まれる数値であればTrueを返す
#   option : エラーメッセージ用にオプションを指定する.
def check_digit_list(option, num, val_list):
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


# RTC BCDフォーマットの7バイトデータを表示
def print_time_bcd(bcd):
  print('20{}{}/{}{}/{}{} '.format(bcd[6] >> 4, bcd[6] & 0xF, bcd[5] >> 4, bcd[5] & 0xF, bcd[4] >> 4, bcd[4] & 0xF),
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
  print('{}{}:{}{}:{}{}'.format(bcd[2] >> 4, bcd[2] & 0xF, bcd[1] >> 4, bcd[1] & 0xF, bcd[0] >> 4, bcd[0] & 0xF))


def make_bcd(year, month, date, dow, hour, minute, second):
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


# RTCの時刻を読み出してdatetimeに変換
def read_rtc():
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


# スケジュールデータを文字列に変換
def sch2str(sch):
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


# スケジュールデータ4バイトをcsvフォーマットの文字列に変換
def sch2csv(sch):
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
      s += '{}, '.format((dow2str[sch[2] & 0x7 - 1]))
  else:
    s += '*, '

  if (sch[1] >> 7) == 0:
    s += '{:02}, '.format(sch[1])
  else:
    s += '*, '

  s += '{:02}'.format(sch[0] & 0x3F)
  return s


# csvファイルの1行をスケジュールデータ4バイトに変換
#   失敗した場合は空のリストを返す
def csv2sch(csv_str):
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


# Yes/No選択メッセージを表示
#   YesでTrue, NoでFalseを返す
def ask(message, default=False):
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


# ブートローダーから起動
def boot_loader():
  GPIO.output(gpio_boot, 1)
  time.sleep(0.01)
  GPIO.output(gpio_rst, 0)
  time.sleep(0.01)
  GPIO.output(gpio_rst, 1)
  time.sleep(0.01)
  GPIO.output(gpio_boot, 0)
  time.sleep(0.01)


if __name__ == '__main__':
  main()
